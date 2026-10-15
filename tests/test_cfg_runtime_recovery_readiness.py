"""Synthetic-only Android guest-fault recovery safety-gate tests.

The source-level audit checks *retention of blocking conditions*, not a
signal-safe implementation or compatibility with ART/JNI/Android runtime.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools/recomp/diagnostics"))
from audit_cfg_runtime_recovery import audit_runtime_sources


def fake_sources():
    guest="""
uint8_t *MEM;
uint8_t R[0x2000];
uint32_t PC;
static void on_fault(int sig, siginfo_t *info, void *ctx) {
  (void)sig;
  (void)ctx;
  on_fault_report(info->si_addr);
  _exit(3);
}
void guest_init(void) {
    MEM = mmap(NULL, 1ull << 32, PROT_NONE, MAP_PRIVATE, -1, 0);
#ifndef __ANDROID__
    sigaction(SIGSEGV, &sa, NULL);
    sigaction(SIGBUS, &sa, NULL);
#endif
}
void guest_commit(void) {
    mprotect(MEM + 0x1000, 0x1000, PROT_READ | PROT_WRITE);
}
void guest_decommit(void) {
    mprotect(MEM + 0x1000, 0x1000, PROT_NONE);
}
void guest_run(void) {
    int found = dispatch_index_find(&code_index, chunks, count, PC);
    all_chunks[found].fn();
}
"""
    cmake="""
option(CODRECOMP_CFG14_GEOM_REGION "CFG14 OFF" OFF)
if(CODRECOMP_CFG14_GEOM_REGION)
  message(FATAL_ERROR "CFG14 FAULT_STATE_UNSAFE: do not deploy")
endif()
"""
    builder="""
if args.cfg14_geom_region:
    parser.error("--cfg14-geom-region BLOCKED: source invalid")
"""
    return guest,cmake,builder


class AndroidRuntimeRecoveryGate(unittest.TestCase):
    def test_current_runtime_gates_are_intact_but_not_product_ready(self):
        guest=(ROOT/"tools/recomp/runtime/guest.c").read_text(encoding="utf-8")
        cmake=(ROOT/"android/CMakeLists.txt").read_text(encoding="utf-8")
        builder=(ROOT/"tools/recomp/build_android.py").read_text(encoding="utf-8")
        audit=audit_runtime_sources(guest,cmake,builder)
        self.assertTrue(audit["safety_build_gates_intact"])
        self.assertFalse(audit["ready_to_enable_CFG14_on_Android"])
        self.assertTrue(audit["facts"]["R_is_global_not_tls"])
        self.assertTrue(audit["facts"]["PC_is_global_not_tls"])
        self.assertTrue(audit["facts"]["desktop_sigsegv_sigbus_intentionally_excluded_on_android"])
        self.assertTrue(audit["facts"]["existing_unix_fault_handler_is_terminating"])
        self.assertGreaterEqual(len(audit["blocked_by"]),6)

    def test_removing_direct_cmake_guard_fails_closed(self):
        g,c,b=fake_sources()
        self.assertTrue(audit_runtime_sources(g,c,b)["safety_build_gates_intact"])
        weakened=c.replace("message(FATAL_ERROR", "message(STATUS")
        a=audit_runtime_sources(g,weakened,b)
        self.assertFalse(a["safety_build_gates_intact"])
        self.assertFalse(a["facts"]["direct_CMake_CFG14_ON_fail_closed"])

    def test_removing_builder_guard_fails_closed(self):
        g,c,b=fake_sources()
        a=audit_runtime_sources(g,c,b.replace("parser.error(","print("))
        self.assertFalse(a["safety_build_gates_intact"])
        self.assertFalse(a["facts"]["build_android_CFG14_ON_fail_closed"])

    def test_do_not_install_art_wide_sigsegv_in_earlier_scoped_block(self):
        g,c,b=fake_sources()
        a=audit_runtime_sources(g.replace("#ifndef __ANDROID__",
                                          "#ifdef __ANDROID__"),c,b)
        self.assertFalse(a["facts"]["desktop_sigsegv_sigbus_intentionally_excluded_on_android"])
        self.assertFalse(a["safety_build_gates_intact"])

    def test_architectural_state_global_and_4g_memory_are_not_a_deopt(self):
        g,c,b=fake_sources()
        a=audit_runtime_sources(g,c,b)
        self.assertTrue(a["facts"]["guest_mem_reservation_4GiB"])
        self.assertTrue(a["facts"]["guest_page_decommit_protects_none"])
        self.assertTrue(a["facts"]["guest_data_commit_uses_mprotect"])
        self.assertTrue(a["facts"]["PC_is_global_not_tls"])
        self.assertFalse(a["ready_to_enable_CFG14_on_Android"])

    def test_missing_dispatcher_fallback_is_not_allowed(self):
        g,c,b=fake_sources()
        a=audit_runtime_sources(g.replace("all_chunks[found].fn();",
                                          "no_original_code();"),c,b)
        self.assertFalse(a["facts"]["original_dispatcher_chunk_fallback_present"])
        self.assertFalse(a["safety_build_gates_intact"])


if __name__=="__main__":
    unittest.main()
