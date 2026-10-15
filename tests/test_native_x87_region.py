import ctypes
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools/recomp'))
from native_x87_region import decode_region,emit_region

# Owned synthetic program: load position, add matrix scalar, store, return.
OWNED=bytes.fromhex('d902d800d91fc3')
class NativeRegionTests(unittest.TestCase):
    def test_decode_order_and_bounds(self):
        instructions,ret=decode_region(OWNED,0x1000)
        self.assertEqual([i['pc'] for i in instructions],[0x1000,0x1002,0x1004])
        self.assertEqual(ret,0x1006)
        self.assertEqual(instructions[-1]['opcode'],0x11f)
    def test_reject_unsupported_or_truncated(self):
        for raw in (b'\xc3',OWNED[:-1],b'\x90\xc3',b'\xeb\x00\xc3',b'\xd9\x04\x24\xc3'):
            with self.assertRaises(ValueError):decode_region(raw,0x1000)
    @unittest.skipUnless(os.environ.get('RECOMP_TEST_CC'),'host compiler supplied by CTest')
    def test_execute_generated_region_and_closed_guards(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);source=folder/'region.c';library=folder/('region.dll' if os.name=='nt' else 'region.so')
            source.write_text(emit_region(OWNED,0x1000)+'\nint guest_committed(uint32_t a){(void)a;return 1;}\n',encoding='utf-8')
            command=[os.environ['RECOMP_TEST_CC'],'-O2','-shared','-fPIC','-I',str(ROOT/'tools/recomp'),str(source),str(ROOT/'tools/recomp/runtime/native_x87_bridge.c'),'-o',str(library)]
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            lib=ctypes.CDLL(str(library));run=lib.codsp_native_x87_region_try
            run.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint16,ctypes.c_uint16];run.restype=ctypes.c_int
            regs=bytearray(0x2000);memory=bytearray(0x8000)
            for offset,value in ((0,0x2000),(8,0x3000),(28,0x5000),(16,0x7000)):
                struct.pack_into('<I',regs,offset,value)
            struct.pack_into('<H',regs,0x10a0,0x37f);struct.pack_into('<H',regs,0x10a4,0xffff)
            memory[0x1000:0x1007]=OWNED;struct.pack_into('<f',memory,0x2000,1.25);struct.pack_into('<f',memory,0x3000,2.5)
            struct.pack_into('<I',memory,0x7000,0x12345678)
            r=ctypes.create_string_buffer(bytes(regs));m=ctypes.create_string_buffer(bytes(memory));pc=ctypes.c_uint32(0x1000)
            self.assertEqual(run(r,m,ctypes.byref(pc),0x23,0x2b),1)
            self.assertEqual(struct.unpack_from('<f',m.raw,0x5000)[0],3.75)
            self.assertEqual(pc.value,0x12345678)
            self.assertEqual(struct.unpack_from('<I',r.raw,16)[0],0x7004)
            self.assertEqual(struct.unpack_from('<I',r.raw,0x10ac)[0],0x1004)
            for bad_cw in (0x37e,0x17f,0x837f):
                r=ctypes.create_string_buffer(bytes(regs));struct.pack_into('<H',r,0x10a0,bad_cw)
                before=r.raw;m=ctypes.create_string_buffer(bytes(memory));pc.value=0x1000
                self.assertEqual(run(r,m,ctypes.byref(pc),0x23,0x2b),0)
                self.assertEqual(r.raw,before);self.assertEqual(m.raw[:len(memory)],bytes(memory));self.assertEqual(pc.value,0x1000)
            for alias in (0x23f,0x33f):
                r=ctypes.create_string_buffer(bytes(regs));struct.pack_into('<H',r,0x10a0,alias)
                m=ctypes.create_string_buffer(bytes(memory));pc.value=0x1000
                self.assertEqual(run(r,m,ctypes.byref(pc),0x23,0x2b),1)
                self.assertEqual(struct.unpack_from('<H',r.raw,0x10a0)[0],alias|0x40)
                self.assertEqual(struct.unpack_from('<f',m.raw,0x5000)[0],3.75)
            r=ctypes.create_string_buffer(bytes(regs));m=ctypes.create_string_buffer(bytes(memory));m[0x1000]=b'\x90'
            before=m.raw;self.assertEqual(run(r,m,ctypes.byref(pc),0x23,0x2b),0)
            self.assertEqual(m.raw,before);self.assertEqual(r.raw[:len(regs)],bytes(regs))
            if os.name=='nt':
                import _ctypes
                _ctypes.FreeLibrary(lib._handle)

if __name__=='__main__':unittest.main()
