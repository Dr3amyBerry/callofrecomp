package org.callofrecomp;
import java.io.*;
import java.nio.file.*;

public final class InstallationTest {
    public static void main(String[] args) throws Exception {
        Path dir = Files.createTempDirectory("cod-install-check");
        try {
            for (String name : new String[]{"CoDSP.exe", "gamex86.dll", "cgamex86.dll", "uix86.dll"})
                Files.write(dir.resolve(name), new byte[]{1, 2, 3});
            Files.createDirectory(dir.resolve("main"));
            Files.write(dir.resolve("main/pak0.pk3"), new byte[]{4});
            if (Installation.valid(dir.toFile())) throw new AssertionError("An incompatible installation must not enable Play");
            if (!Installation.language(dir.toFile()).equals("0")) throw new AssertionError("Unlocalized packs use English index 0");
            Files.write(dir.resolve("main/localized_spanish_pak0.pk3"), new byte[]{4});
            if (!Installation.language(dir.toFile()).equals("4")) throw new AssertionError("Spanish resources need cl_language index 4");
            if (args.length == 1 && !Installation.valid(new File(args[0]))) throw new AssertionError("The verified local baseline must be accepted");
            System.out.println("Android installation validation passed");
        } finally {
            try (java.util.stream.Stream<Path> paths = Files.walk(dir)) {
                paths.sorted(java.util.Comparator.reverseOrder()).forEach(p -> { try { Files.delete(p); } catch (IOException e) { throw new UncheckedIOException(e); } });
            }
        }
    }
}
