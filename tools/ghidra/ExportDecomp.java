// Ghidra headless post-script: exports decompiled C, a function index and
// defined strings for the current program.
// Usage: analyzeHeadless ... -postScript ExportDecomp.java <out_dir>
// Output is derived from proprietary binaries: keep it under decomp/ (ignored).
//@category codrecomp

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileOptions;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.DataIterator;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;

import java.io.File;
import java.io.PrintWriter;

public class ExportDecomp extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        File out = new File(args.length > 0 ? args[0] : "decomp", currentProgram.getName());
        out.mkdirs();

        DecompInterface ifc = new DecompInterface();
        ifc.setOptions(new DecompileOptions());
        ifc.openProgram(currentProgram);

        int ok = 0, failed = 0;
        try (PrintWriter c = new PrintWriter(new File(out, "decomp.c"), "UTF-8");
             PrintWriter idx = new PrintWriter(new File(out, "functions.tsv"), "UTF-8")) {
            idx.println("entry\tname\tsize\tthunk\tdecompiled");
            FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
            while (it.hasNext() && !monitor.isCancelled()) {
                Function f = it.next();
                boolean good = false;
                if (!f.isThunk() && !f.isExternal()) {
                    DecompileResults r = ifc.decompileFunction(f, 60, monitor);
                    if (r != null && r.decompileCompleted()) {
                        c.println("// " + f.getEntryPoint() + " " + f.getName());
                        c.println(r.getDecompiledFunction().getC());
                        good = true;
                        ok++;
                    } else {
                        c.println("// " + f.getEntryPoint() + " " + f.getName() + " : DECOMPILE FAILED");
                        failed++;
                    }
                }
                idx.println(f.getEntryPoint() + "\t" + f.getName() + "\t" + f.getBody().getNumAddresses()
                        + "\t" + f.isThunk() + "\t" + good);
            }
        } finally {
            ifc.dispose();
        }

        int strings = 0;
        try (PrintWriter s = new PrintWriter(new File(out, "strings.tsv"), "UTF-8")) {
            s.println("address\tvalue");
            DataIterator di = currentProgram.getListing().getDefinedData(true);
            while (di.hasNext()) {
                Data d = di.next();
                if (d.hasStringValue()) {
                    String v = String.valueOf(d.getValue()).replace("\\", "\\\\")
                            .replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r");
                    s.println(d.getAddress() + "\t" + v);
                    strings++;
                }
            }
        }
        println("codrecomp: " + currentProgram.getName() + " decompiled=" + ok + " failed=" + failed
                + " strings=" + strings);
    }
}
