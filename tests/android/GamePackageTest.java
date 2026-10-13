package org.callofrecomp;

import java.io.*;
import java.nio.file.*;
import java.util.zip.CRC32;

public final class GamePackageTest {
    static byte[] pack(String[] names, boolean corrupt) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        DataOutputStream out = new DataOutputStream(bytes);
        out.writeBytes("CODPACK1"); out.writeInt(names.length);
        for (String name : names) {
            byte[] data = ("synthetic:" + name).getBytes("UTF-8");
            CRC32 crc = new CRC32(); crc.update(data);
            out.writeShort(name.length()); out.writeBytes(name); out.writeLong(data.length);
            out.write(data); out.writeInt((int)crc.getValue() ^ (corrupt ? 1 : 0));
        }
        return bytes.toByteArray();
    }
    static final String[] GOOD = {"CoDSP.exe", "gamex86.dll", "cgamex86.dll", "uix86.dll", "main/pak0.pk3"};
    static void reject(byte[] data) throws Exception {
        Path dir = Files.createTempDirectory("codpack-reject");
        try {
            try { GamePackage.unpack(new ByteArrayInputStream(data), dir.toFile(), n -> {}); }
            catch (IOException expected) { return; }
            throw new AssertionError("Invalid package accepted");
        } finally { clean(dir); }
    }
    static void clean(Path dir) throws Exception {
        try (java.util.stream.Stream<Path> paths = Files.walk(dir)) {
            for (Path p : (Iterable<Path>)paths.sorted(java.util.Comparator.reverseOrder())::iterator) Files.delete(p);
        }
    }
    public static void main(String[] args) throws Exception {
        Path dir = Files.createTempDirectory("codpack-good");
        try {
            byte[] data = args.length > 0 ? Files.readAllBytes(Paths.get(args[0])) : pack(GOOD, false);
            GamePackage.unpack(new ByteArrayInputStream(data), dir.toFile(), n -> {});
            for (String name : GOOD) if (!Files.isRegularFile(dir.resolve(name))) throw new AssertionError(name);
        } finally { clean(dir); }
        reject(pack(GOOD, true));
        byte[] good = pack(GOOD, false);
        reject(java.util.Arrays.copyOf(good, good.length - 1));
        reject(java.util.Arrays.copyOf(good, good.length + 1));
        reject(pack(new String[]{"CoDSP.exe", "gamex86.dll", "cgamex86.dll", "uix86.dll", "../escape.pk3"}, false));
        reject(pack(new String[]{"CoDSP.exe", "gamex86.dll", "cgamex86.dll", "uix86.dll", "main/../escape.pk3"}, false));
        reject(pack(new String[]{"CoDSP.exe", "gamex86.dll", "cgamex86.dll", "uix86.dll", "main/pak0.pk3", "main/pak0.pk3"}, false));
        reject(pack(new String[]{"CoDSP.exe", "gamex86.dll", "cgamex86.dll", "uix86.dll", "main/PAK0.pk3"}, false));
        reject(pack(new String[]{"CoDSP.exe", "gamex86.dll", "cgamex86.dll", "main/pak0.pk3", "main/pak1.pk3"}, false));
        byte[] oversized = good.clone();
        // First entry's uint64 length begins after 12 + 2 + 9 bytes.
        oversized[23] = 0x7f; reject(oversized);
        System.out.println("GamePackage: round-trip, CRC, truncation, traversal, duplicates, limits OK");
    }
}
