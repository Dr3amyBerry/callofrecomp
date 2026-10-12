// Ghidra headless post-script: dumps raw p-code for every instruction of the
// current program, as input for tools/recomp/pcode2c.py.
// Usage: analyzeHeadless ... -postScript ExportPcode.java <out_file>
// Output is derived from proprietary code: keep it under recomp_out/ (ignored).
//
// Line format:
//   I <addr> <len>                        instruction header
//   P <opcode> <out|-> <in>...            p-code op; varnode = space:offset:size
//   F <addr>                              function entry
//   U <index> <name>                      user-defined (CALLOTHER) op name
//@category codrecomp

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.Varnode;

import java.io.File;
import java.io.PrintWriter;

public class ExportPcode extends GhidraScript {
    private static String vn(Varnode v) {
        if (v == null) return "-";
        AddressSpace s = v.getAddress().getAddressSpace();
        String sp;
        if (v.isConstant()) sp = "c";
        else if (v.isRegister()) sp = "r";
        else if (v.isUnique()) sp = "u";
        else if (s.isMemorySpace()) sp = "m";
        else sp = "x" + s.getName();
        return sp + ":" + Long.toHexString(v.getOffset()) + ":" + v.getSize();
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        File out = new File(args.length > 0 ? args[0] : "pcode.txt");
        out.getParentFile().mkdirs();
        int count = 0;
        try (PrintWriter w = new PrintWriter(out, "UTF-8")) {
            int n = currentProgram.getLanguage().getNumberOfUserDefinedOpNames();
            for (int i = 0; i < n; i++) {
                w.println("U " + i + " " + currentProgram.getLanguage().getUserDefinedOpName(i));
            }
            for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
                if (!f.isExternal()) w.println("F " + f.getEntryPoint().getOffset());
            }
            InstructionIterator it = currentProgram.getListing().getInstructions(true);
            while (it.hasNext() && !monitor.isCancelled()) {
                Instruction ins = it.next();
                w.println("I " + ins.getAddress().getOffset() + " " + ins.getLength());
                for (PcodeOp op : ins.getPcode()) {
                    StringBuilder sb = new StringBuilder("P ").append(op.getMnemonic()).append(' ')
                            .append(vn(op.getOutput()));
                    for (Varnode in : op.getInputs()) sb.append(' ').append(vn(in));
                    w.println(sb);
                }
                count++;
            }
        }
        println("codrecomp: pcode instructions=" + count);
    }
}
