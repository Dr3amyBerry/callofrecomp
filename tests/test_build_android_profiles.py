"""Diagnostic APK flags must be available without changing default builds."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / 'tools/recomp/build_android.py'

class ProfileBuildFlagsTest(unittest.TestCase):
    def test_narrow_right_shift_is_arm64_only(self):
        proc=subprocess.run([sys.executable,str(BUILDER),'--abi','x86_64',
                             '--arm64-narrow-right-shift'],capture_output=True,text=True)
        self.assertNotEqual(proc.returncode,0)
        self.assertIn('requires arm64-v8a',proc.stderr)

    def test_narrow_sar_is_arm64_only(self):
        proc = subprocess.run(
            [sys.executable, str(BUILDER), '--abi', 'x86_64',
             '--arm64-narrow-sar'], capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('--arm64-narrow-sar requires arm64-v8a', proc.stderr)

    def test_entry_dispatch_is_arm64_only_and_excludes_last_hint(self):
        for options,message in (
            (['--abi','x86_64','--arm64-dispatch-entry-cache'], 'requires arm64-v8a'),
            (['--arm64-dispatch-entry-cache','--dispatch-last-cache'], 'choose one dispatch cache'),
        ):
            proc=subprocess.run([sys.executable,str(BUILDER),*options],capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn(message,proc.stderr)

    def test_safe_icf_is_arm64_only(self):
        for flag in ('--arm64-safe-icf','--arm64-icf-metadata'):
            proc=subprocess.run([sys.executable,str(BUILDER),'--abi','x86_64',flag],capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn(flag+' requires arm64-v8a',proc.stderr)

    def test_code_layout_flags_plumbing(self):
        proc=subprocess.run([sys.executable,str(BUILDER),'--abi','x86_64','--arm64-code-layout'],capture_output=True,text=True)
        self.assertIn('--arm64-code-layout requires arm64-v8a',proc.stderr)
        proc=subprocess.run([sys.executable,str(BUILDER),'--abi','arm64-v8a','--arm64-symbol-order','x.txt'],capture_output=True,text=True)
        self.assertIn('requires --arm64-code-layout',proc.stderr)
        text=BUILDER.read_text(encoding='utf-8')
        cm=(ROOT/'android/CMakeLists.txt').read_text(encoding='utf-8')
        self.assertIn('CODRECOMP_ARM64_CODE_LAYOUT',text)
        self.assertIn('-ffunction-sections -mtune=cortex-a55',cm)
        blk=cm[cm.index('if(CODRECOMP_ARM64_CODE_LAYOUT)'):cm.index('option(CODRECOMP_LOCAL_GUEST_STATE')]
        self.assertNotIn('-ffast-math',blk)
        self.assertNotIn('-ffp-contract',blk)
        self.assertNotIn('-ffp-contract=fast',cm)
        self.assertIn('-ffp-contract=off',cm)

    def test_release_defaults_require_wsa_and_original_pe(self):
        for options in (['--wsa-release'],['--abi','x86_64','--wsa-release']):
            proc=subprocess.run([sys.executable,str(BUILDER),*options],capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn('--wsa-release requires',proc.stderr)

    def test_cumulative_bundle_requires_wsa_and_verified_pe_argument(self):
        for options in (['--wsa-cumulative'],
                        ['--abi','x86_64','--wsa-cumulative'],
                        ['--abi','arm64-v8a','--wsa-cumulative','--native-x87-region','unused.exe']):
            proc=subprocess.run([sys.executable,str(BUILDER),*options],capture_output=True,text=True)
            self.assertNotEqual(proc.returncode,0)
            self.assertIn('--wsa-cumulative requires',proc.stderr)

    def test_legacy_transform_cannot_bypass_original_x87_precision_gate(self):
        for abi in ('arm64-v8a', 'x86_64'):
            with self.subTest(abi=abi):
                result = subprocess.run([
                    sys.executable, str(BUILDER), '--abi', abi,
                    '--sdk', str(ROOT / '.local/nonexistent-oracle-sdk'),
                    '--java', str(ROOT / '.local/nonexistent-oracle-java'),
                    '--hot-x87-transform'], capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('ORIGINAL_X87_PRECISION_UNSAFE', result.stderr)

    def test_help_offers_opt_in_cpu_and_gl_diagnostics(self):
        proc = subprocess.run([sys.executable, str(BUILDER), '--help'],
                              capture_output=True, text=True, check=True)
        self.assertIn('--cpu-profile', proc.stdout)
        self.assertIn('--gl-profile', proc.stdout)
        self.assertIn('--gl-time-profile', proc.stdout)
        self.assertIn('--gl-vk-state-capture', proc.stdout)
        self.assertIn('--wsa-uncap-bench', proc.stdout)
        self.assertIn('--core-hot-o2', proc.stdout)
        self.assertIn('--core-hot-o2-parts', proc.stdout)
        self.assertIn('--arm64-narrow-sar', proc.stdout)
        self.assertIn('--render-o2', proc.stdout)
        self.assertIn('--hot-x87-transform', proc.stdout)
        self.assertIn('--fast-copy32', proc.stdout)
        self.assertIn('--visibility-o2', proc.stdout)
        self.assertIn('--x87-nan-bits', proc.stdout)
        self.assertIn('--x87-normal-f2d', proc.stdout)
        self.assertIn('--x87-normal-f2d-p4', proc.stdout)
        self.assertIn('--x87-normal-f2d-p4-selective', proc.stdout)
        self.assertIn('--x87-normal-f2d-p4-profiled', proc.stdout)
        self.assertIn('--x87-stack-shift-outline', proc.stdout)
        self.assertIn('--dispatch-last-cache', proc.stdout)
        self.assertIn('--x87-fcom-fastpath', proc.stdout)

    def test_p4_requires_verified_arm64_baseline_flags(self):
        import subprocess
        for args,expected in [
            (['--abi','arm64-v8a','--x87-normal-f2d-p4'],
             'requires --x87-normal-f2d'),
            (['--abi','x86_64','--x87-normal-f2d','--x87-normal-f2d-p4'],
             'only supported for ARM64'),
        ]:
            with self.subTest(args=args):
                cmd=[sys.executable,str(BUILDER),*args]
                result=subprocess.run(cmd,capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(expected,result.stderr)

    def test_selective_p4_flags_require_arm64_baseline_and_exclude_whole_p4(self):
        cases = [
            (['--x87-normal-f2d-p4-selective'],
             'requires --x87-normal-f2d'),
            (['--abi','x86_64','--x87-normal-f2d',
              '--x87-normal-f2d-p4-selective'], 'ARM64-only'),
            (['--x87-normal-f2d','--x87-normal-f2d-p4',
              '--x87-normal-f2d-p4-selective'],
             'not both'),
        ]
        for argv, phrase in cases:
            with self.subTest(args=argv):
                result = subprocess.run([sys.executable, str(BUILDER), *argv],
                                        text=True, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(phrase, result.stderr)

    def test_sample_guided_p4_flags_are_constrained(self):
        for argv, error in [
            (['--x87-normal-f2d-p4-profiled'], 'requires --x87-normal-f2d'),
            (['--abi','x86_64','--x87-normal-f2d',
              '--x87-normal-f2d-p4-profiled'], 'ARM64-only'),
            (['--x87-normal-f2d','--x87-normal-f2d-p4-selective',
              '--x87-normal-f2d-p4-profiled'], 'mutually exclusive'),
            (['--x87-normal-f2d','--x87-normal-f2d-p4',
              '--x87-normal-f2d-p4-profiled'], 'mutually exclusive'),
        ]:
            with self.subTest(args=argv):
                result = subprocess.run([sys.executable, str(BUILDER), *argv],
                                        capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(error, result.stderr)

    def test_x87_stack_outline_requires_arm64_and_disjoint_p4_mode(self):
        cases = [
            (['--abi','x86_64','--x87-stack-shift-outline'], 'ARM64-only'),
            (['--x87-normal-f2d','--x87-stack-shift-outline','--x87-normal-f2d-p4'],
             'cannot combine with p4 x87 conversion'),
            (['--x87-normal-f2d','--x87-stack-shift-outline','--x87-normal-f2d-p4-profiled'],
             'cannot combine with p4 x87 conversion'),
        ]
        for argv, phrase in cases:
            with self.subTest(argv=argv):
                process=subprocess.run([sys.executable,str(BUILDER),*argv],
                                       text=True,capture_output=True)
                self.assertNotEqual(process.returncode,0)
                self.assertIn(phrase,process.stderr)

    def test_core_hot_o2_requires_arm64_and_optimized_generated_code(self):
        for flags,phrase in [
            (['--abi','x86_64','--core-hot-o2'], 'ARM64-only'),
            (['--core-hot-o2','--recomp-opt','0'], 'requires --recomp-opt 1'),
        ]:
            with self.subTest(flags=flags):
                result=subprocess.run([sys.executable,str(BUILDER),*flags],
                                      capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(phrase,result.stderr)

    def test_core_hot_o2_subset_rejects_invalid_inputs_before_build(self):
        cases = [
            (['--core-hot-o2-parts', 'p0'], 'requires --core-hot-o2'),
            (['--core-hot-o2', '--core-hot-o2-parts', 'p8'],
             'requires distinct p0,p1,p4'),
            (['--core-hot-o2', '--core-hot-o2-parts', 'p1,p1'],
             'requires distinct p0,p1,p4'),
            (['--core-hot-o2', '--core-hot-o2-parts', 'p0,,p4'],
             'requires distinct p0,p1,p4'),
            (['--core-hot-o2', '--core-hot-o2-parts', 'p0, p1'],
             'requires distinct p0,p1,p4'),
            (['--abi', 'x86_64', '--core-hot-o2', '--core-hot-o2-parts', 'p1'],
             'ARM64-only'),
            (['--core-hot-o2', '--core-hot-o2-parts', 'p1', '--recomp-opt', '0'],
             'requires --recomp-opt 1'),
        ]
        for args, expected in cases:
            with self.subTest(args=args):
                result = subprocess.run(
                    [sys.executable, str(BUILDER), *args],
                    capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)

    def test_wsa_uncap_is_rejected_for_arm64(self):
        proc = subprocess.run(
            [sys.executable, str(BUILDER), '--abi', 'arm64-v8a',
             '--wsa-uncap-bench'],
            capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('for --abi x86_64 WSA only', proc.stderr)

if __name__ == '__main__':
    unittest.main()
