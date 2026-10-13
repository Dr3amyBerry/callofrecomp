"""Offline control-flow proofs for dead architectural flag writes."""
import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/recomp'))
from flag_liveness import dead_flag_writes


def r(offset=0x200, size=1):
    return ('r', offset, size)


def c(value=0, size=1):
    return ('c', value, size)


def write(offset=0x200, mnemonic='COPY', inputs=None, size=1):
    return (mnemonic, r(offset, size), [c()] if inputs is None else inputs)


def branch(target, conditional=False):
    return ('CBRANCH' if conditional else 'BRANCH', None,
            [target, r(0x10)] if conditional else [target])


def chunk(*ops):
    return [(0x1000, 1, list(ops))]


class FlagLivenessTests(unittest.TestCase):
    def test_overwrite_and_exit(self):
        self.assertEqual(dead_flag_writes(chunk(write(), write())), {(0, 0)})
        self.assertEqual(dead_flag_writes(chunk(write())), set())

    def test_read_and_read_modify_write(self):
        self.assertEqual(dead_flag_writes(chunk(write(), write(inputs=[r()]), write())), {(0, 1)})
        self.assertEqual(dead_flag_writes(chunk(write(), ('COPY', r(0x10), [r()]), write())), set())

    def test_all_conditional_paths_must_overwrite(self):
        code = chunk(write(), branch(c(3), True), write(), branch(c(2)), write(), write(0x202))
        self.assertEqual(dead_flag_writes(code), {(0, 0)})
        code[0][2][4] = ('COPY', r(0x10), [c()])
        self.assertNotIn((0, 0), dead_flag_writes(code))

    def test_loop_fixed_point(self):
        code = chunk(write(), branch(c(2), True), branch(c((1 << 64) - 1)), write())
        self.assertEqual(dead_flag_writes(code), {(0, 0)})
        code[0][2][1] = ('CBRANCH', None, [c(2), r()])
        self.assertEqual(dead_flag_writes(code), set())

    def test_contiguous_and_gap(self):
        code = [(0x1000, 1, [write()]), (0x1001, 1, [write()])]
        self.assertEqual(dead_flag_writes(code), {(0, 0)})
        code[1] = (0x1002, 1, [write()])
        self.assertEqual(dead_flag_writes(code), set())

    def test_direct_call_is_jump_into_callee(self):
        code = [(0x1000, 1, [write(), ('CALL', None, [('m', 0x2000, 4)])]),
                (0x2000, 1, [write(), ('RETURN', None, [r(0x10, 4)])])]
        self.assertEqual(dead_flag_writes(code), {(0, 0)})

    def test_relative_past_end_maps_to_next_address(self):
        code = [(0x1000, 1, [write(), branch(c(20))]), (0x1001, 1, [write()])]
        self.assertEqual(dead_flag_writes(code), {(0, 0)})
        code[0][2][1] = branch(c((1 << 64) - 20))
        self.assertEqual(dead_flag_writes(code), set())

    def test_external_and_indirect_observe_flags(self):
        for mnemonic in ('BRANCHIND', 'CALLIND', 'RETURN'):
            self.assertEqual(dead_flag_writes(chunk(write(), (mnemonic, None, [r(0x10)]), write())), set())
        self.assertEqual(dead_flag_writes(chunk(write(), branch(('m', 0x2000, 4)), write())), set())
        self.assertEqual(dead_flag_writes(chunk(write(), branch(('m', 0x2000, 4), True), write())), set())

    def test_barriers(self):
        for mnemonic in ('CALLOTHER', 'UNKNOWN_OP'):
            self.assertEqual(dead_flag_writes(chunk(write(), (mnemonic, None, [c()]), write())), set())

    def test_byte_overlap_reads_and_writes(self):
        self.assertEqual(dead_flag_writes(chunk(write(0x206), ('COPY', r(0x10), [r(0x205, 3)]), write(0x206))), set())
        self.assertEqual(dead_flag_writes(chunk(write(0x206), write(0x205, size=3))), {(0, 0)})
        self.assertEqual(dead_flag_writes(chunk(write(0x206, size=2), write(0x206), write(0x207))), {(0, 0)})
        self.assertEqual(dead_flag_writes(chunk(write(0x200, size=2), write())), set())

    def test_faulting_or_float_operations_never_eliminated(self):
        for mnemonic in ('LOAD', 'INT_DIV', 'INT_REM', 'INT_SDIV', 'FLOAT_EQUAL', 'CALLOTHER'):
            self.assertNotIn((0, 0), dead_flag_writes(chunk(write(mnemonic=mnemonic), write())))
        self.assertNotIn((0, 0), dead_flag_writes(chunk(
            write(inputs=[('m', 0x1234, 1)]), write())))

    def test_memory_addresses_read_register_flags(self):
        for op in [('LOAD', r(0x10), [c(), r()]), ('STORE', None, [c(), r(), c()])]:
            self.assertEqual(dead_flag_writes(chunk(write(), op, write())), set())

    def test_empty_and_no_mutation(self):
        self.assertEqual(dead_flag_writes([]), set())
        code = [(0x1000, 1, [write()]), (0x1001, 1, []), (0x1002, 1, [write()])]
        original = copy.deepcopy(code)
        self.assertEqual(dead_flag_writes(code), {(0, 0)})
        self.assertEqual(code, original)

    def test_empty_target_with_unsorted_physical_fallthrough_exits(self):
        code = [(0x1000, 1, [write(), branch(('m', 0x1002, 4))]),
                (0x1003, 1, [write()]), (0x1002, 1, [])]
        self.assertEqual(dead_flag_writes(code), set())


if __name__ == '__main__':
    unittest.main()
