// Ghidra headless post-script: dumps raw p-code for every instruction of the
// current program, as input for tools/recomp/pcode2c.py.
// Usage: analyzeHeadless ... -postScript ExportPcode.java <out_file>
//   [--discover-data-code-pointers] [--code-entry 0xADDRESS ...]
// Explicit entries require prior verification against the original instructions.
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
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.Varnode;

import java.io.File;
import java.io.PrintWriter;
import java.util.TreeSet;

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
        for (int i = 1; i < args.length; i++) {
            if (args[i].equals("--discover-data-code-pointers")) continue;
            if (!args[i].equals("--code-entry") || i + 1 >= args.length)
                throw new IllegalArgumentException("unknown or incomplete option: " + args[i]);
            Address entry = toAddr(Long.decode(args[++i]));
            MemoryBlock block = currentProgram.getMemory().getBlock(entry);
            if (block == null || !block.isInitialized() || !block.isExecute())
                throw new IllegalArgumentException("code entry outside executable memory: " + entry);
            if (currentProgram.getListing().getInstructionContaining(entry) == null) {
                // A verified entry can be mislabeled as data by automatic analysis.
                clearListing(entry, entry);
                if (!disassemble(entry))
                    throw new IllegalArgumentException("cannot disassemble verified entry: " + entry);
            }
            println("codrecomp: verified code entry=" + entry);
        }
        // Optional discovery for indirect callbacks held in static data tables.
        // Never clear existing instructions/data or sweep arbitrary code bytes.
        if (java.util.Arrays.asList(args).contains("--discover-data-code-pointers")) {
            TreeSet<Address> candidates = new TreeSet<>();
            for (MemoryBlock block : currentProgram.getMemory().getBlocks()) {
                if (!block.isInitialized() || block.isExecute()) continue;
                for (long offset = 0; offset + 4 <= block.getSize() && !monitor.isCancelled(); offset += 4) {
                    Address source = block.getStart().add(offset);
                    Address target = toAddr(Integer.toUnsignedLong(getInt(source)));
                    MemoryBlock destination = currentProgram.getMemory().getBlock(target);
                    if (destination != null && destination.isExecute()
                            && currentProgram.getListing().getInstructionContaining(target) == null
                            && currentProgram.getListing().getDefinedDataContaining(target) == null)
                        candidates.add(target);
                }
            }
            int discovered = 0;
            for (Address target : candidates) {
                if (monitor.isCancelled()) break;
                if (currentProgram.getListing().getInstructionContaining(target) == null && disassemble(target))
                    discovered++;
            }
            println("codrecomp: data-code-pointer candidates=" + candidates.size() + " disassembled=" + discovered);
        }
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
