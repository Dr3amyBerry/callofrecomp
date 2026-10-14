package org.callofrecomp;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.Arrays;
import java.util.Comparator;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.CRC32;
import java.util.zip.Inflater;
import java.util.zip.DataFormatException;
import java.util.zip.ZipOutputStream;

/**
 * Fix the original 4:3 HUD artwork without touching 3D projection/FOV.
 *
 * The original single-player Compass and selected square HUD icons use
 * ui/hud.menu's 640x480 coordinates, which the 1.5 engine scales by different
 * physical X/Y factors on a widescreen display. Derive a tiny *private*
 * override PK3 from the user's installed script and patch only those widths
 * and relative positions, preserving the original Y dimensions/owner-draw IDs.
 *
 * No copyrighted menu content or PK3 ships with the application. The original
 * archives remain unmodified; the override is regenerated for the EGL buffer
 * aspect before the guest file-system starts and can be safely removed.
 */
final class HudWidescreen {
    private HudWidescreen() {}

    private static final String OVERLAY_NAME = "zzzz_codrecomp_hud_fix.pk3";
    private static final String MENU_FILE = "ui/hud.menu";
    private static final int MAX_MENU_BYTES = 512 * 1024;
    static String lastDiagnostic = "not run";

    private static String number(double v) {
        return String.format(Locale.ROOT, "%.6f", v);
    }

    private static int count(String s, String needle) {
        int found = 0;
        for (int from = 0, i; (i = s.indexOf(needle, from)) >= 0; from = i + needle.length())
            found++;
        return found;
    }

    private static String replaceOnce(String s, String needle, String replacement) {
        return count(s, needle) == 1 ? s.replace(needle, replacement) : null;
    }

    private static int blockEnd(String s, int open) {
        int depth = 0;
        for (int i = open; i < s.length(); i++) {
            if (s.charAt(i) == '{') depth++;
            if (s.charAt(i) == '}' && --depth == 0) return i + 1;
        }
        return -1;
    }

    private static String findAndPatchCompass(String menu, double correction) {
        final String name = "name \"Compass\"";
        if (count(menu, name) != 1) return null;
        int nameAt = menu.indexOf(name);
        int start = menu.lastIndexOf("menuDef", nameAt);
        if (start < 0) return null;
        int open = menu.indexOf('{', start);
        if (open < 0 || open > nameAt) return null;
        int end = blockEnd(menu, open);
        if (end < 0) return null;
        String block = menu.substring(start, end);
        if (count(block, "rect 0 0 COMPASS_SIZE COMPASS_SIZE") != 6 ||
                !block.contains("name \"compassback\"") ||
                !block.contains("name \"compassneedle\"")) return null;

        final double width = 160.0 * correction;
        // Keep the original center despite narrowing the virtual X axis.
        final double x = -25.0 + (160.0 - width) * 0.5;
        block = replaceOnce(block, "rect COMPASS_X COMPASS_Y COMPASS_SIZE COMPASS_SIZE",
                "rect " + number(x) + " COMPASS_Y " + number(width) + " COMPASS_SIZE");
        if (block == null) return null;
        block = replaceOnce(block,
                "rect COMPASS_NEEDLE_XOFF COMPASS_NEEDLE_YOFF COMPASS_NEEDLE_WIDTH COMPASS_NEEDLE_HEIGHT",
                "rect " + number(60.0 * correction) +
                        " COMPASS_NEEDLE_YOFF " + number(40.0 * correction) +
                        " COMPASS_NEEDLE_HEIGHT");
        if (block == null) return null;
        block = block.replace("rect 0 0 COMPASS_SIZE COMPASS_SIZE",
                "rect 0 0 " + number(width) + " COMPASS_SIZE");
        return menu.substring(0, start) + block + menu.substring(end);
    }

    // These are square HUD decorations; skip other menus (health/ammo bars
    // contain genuinely non-square artwork and must not be compressed).
    private static String patchSquareMenu(String script, String name,
                                          String originalParent, double x,
                                          double width, double correction,
                                          boolean extraTankIcon) {
        String needle = "name \"" + name + "\"";
        if (count(script, needle) != 1) return script; // optional localized menu
        int at = script.indexOf(needle);
        int start = script.lastIndexOf("menuDef", at);
        if (start < 0) return script;
        int open = script.indexOf('{', start);
        int end = open >= 0 ? blockEnd(script, open) : -1;
        if (end < 0) return script;
        String block = script.substring(start, end);
        String parent = replaceOnce(block, originalParent, "rect " + number(x) +
                (name.equals("Cursorhints") ? " 325 " : " 434.375 ") + number(width) + " 40");
        if (parent == null) return script;
        block = replaceOnce(parent, "rect 0 0 40 40", "rect 0 0 " + number(width) + " 40");
        if (block == null) return script;
        if (extraTankIcon) {
            block = replaceOnce(block, "rect 20 20 40 40",
                    "rect " + number(20.0 * correction) + " 20 " +
                            number(width) + " 40");
            if (block == null) return script;
        }
        return script.substring(0, start) + block + script.substring(end);
    }

    /** Null means no safe changes can be made; caller must remove stale overlay. */
    static String patchMenu(String original, int width, int height) {
        if (width <= 0 || height <= 0 || (double) width / height <= 4.0 / 3.0 + 0.0001)
            return null;
        double correction = (4.0 / 3.0) * height / width;
        if (correction <= 0 || correction >= 1) return null;
        String result = findAndPatchCompass(original, correction);
        if (result == null) return null;
        double size = 40.0 * correction;
        double move = (40.0 - size) * 0.5;
        result = patchSquareMenu(result, "Cursorhints", "rect 300 325 40 40",
                300.0 + move, size, correction, false);
        result = patchSquareMenu(result, "stance", "rect 100 434.375 40 40",
                100.0 + move, size, correction, false);
        result = patchSquareMenu(result, "tankstatus", "rect 100 434.375 40 40",
                100.0 + move, size, correction, true);
        return result;
    }

    private static int little16(byte[] buffer, int offset) {
        return (buffer[offset] & 255) | ((buffer[offset + 1] & 255) << 8);
    }
    private static long little32(byte[] buffer, int offset) {
        return ((long) little16(buffer, offset) |
                ((long) little16(buffer, offset + 2) << 16)) & 0xffffffffL;
    }

    /**
     * Find ONE named entry by its central-directory record, without calling
     * Android ZipFile. Original 2003 PK3s can contain duplicate ZIP directory
     * names, which Android ZipFile rejects outright even for unrelated files.
     * Random access avoids inflating thousands of unrelated game assets.
     *
     * Only basic ZIP32 STORE/DEFLATE are required for the original CoD 1.5
     * .pk3 format; corrupt or ZIP64 files are skipped, not altered.
     */
    private static byte[] readArchiveEntry(File file, String requested)
            throws IOException {
        try (RandomAccessFile input = new RandomAccessFile(file, "r")) {
            long length = input.length();
            if (length < 22) throw new IOException("PK3 too short");
            int tailLength = (int) Math.min(length, 65557L);
            byte[] tail = new byte[tailLength];
            input.seek(length - tailLength);
            input.readFully(tail);
            int eocd = -1;
            for (int i = tailLength - 22; i >= 0; i--) {
                if (little32(tail, i) == 0x06054b50L &&
                        i + 22 + little16(tail, i + 20) == tailLength) {
                    eocd = i;
                    break;
                }
            }
            if (eocd < 0) throw new IOException("PK3 central directory missing");
            if (little16(tail, eocd + 4) != 0 ||
                    little16(tail, eocd + 6) != 0 ||
                    little16(tail, eocd + 8) != little16(tail, eocd + 10)) {
                throw new IOException("Multipart PK3 unsupported");
            }
            int entries = little16(tail, eocd + 10);
            long cdSize = little32(tail, eocd + 12);
            long cdOffset = little32(tail, eocd + 16);
            if (entries == 65535 || cdSize == 0xffffffffL ||
                    cdOffset == 0xffffffffL ||
                    cdOffset > length || cdSize > length - cdOffset) {
                throw new IOException("Invalid or ZIP64 PK3 index");
            }
            long cursor = cdOffset, end = cdOffset + cdSize;
            long localOffset = -1, expectedSize = -1, packedSize = -1, crc = -1;
            int method = -1;
            for (int entry = 0; entry < entries; entry++) {
                if (cursor > end || end - cursor < 46)
                    throw new IOException("PK3 central record outside index");
                input.seek(cursor);
                byte[] header = new byte[46];
                input.readFully(header);
                if (little32(header, 0) != 0x02014b50L)
                    throw new IOException("Bad PK3 central entry");
                int nameLength = little16(header, 28);
                int extraLength = little16(header, 30);
                int commentLength = little16(header, 32);
                long next = cursor + 46L + nameLength + extraLength + commentLength;
                if (next > end) throw new IOException("Invalid PK3 entry length");
                byte[] name = new byte[nameLength];
                input.readFully(name);
                if (requested.equalsIgnoreCase(
                        new String(name, StandardCharsets.ISO_8859_1))) {
                    method = little16(header, 10);
                    crc = little32(header, 16);
                    packedSize = little32(header, 20);
                    expectedSize = little32(header, 24);
                    localOffset = little32(header, 42);
                }
                cursor = next;
            }
            if (localOffset < 0) return null;
            if (expectedSize > MAX_MENU_BYTES || packedSize > MAX_MENU_BYTES ||
                    localOffset > length || length - localOffset < 30 ||
                    expectedSize == 0xffffffffL || packedSize == 0xffffffffL)
                throw new IOException("Invalid HUD entry sizes");
            input.seek(localOffset);
            byte[] local = new byte[30];
            input.readFully(local);
            if (little32(local, 0) != 0x04034b50L)
                throw new IOException("Bad PK3 local header");
            long data = localOffset + 30L + little16(local, 26) +
                    little16(local, 28);
            if (data > length || packedSize > length - data)
                throw new IOException("Truncated HUD entry");
            byte[] compressed = new byte[(int) packedSize];
            input.seek(data);
            input.readFully(compressed);
            byte[] output = new byte[(int) expectedSize];
            if (method == 0) {
                if (packedSize != expectedSize) throw new IOException("Bad stored HUD size");
                System.arraycopy(compressed, 0, output, 0, output.length);
            } else if (method == 8) {
                Inflater inflater = new Inflater(true);
                try {
                    inflater.setInput(compressed);
                    int count = 0;
                    while (count < output.length) {
                        int n = inflater.inflate(output, count, output.length - count);
                        if (n > 0) { count += n; continue; }
                        if (inflater.finished() || inflater.needsInput() ||
                                inflater.needsDictionary()) break;
                        throw new IOException("Invalid deflate progress");
                    }
                    if (count != output.length || !inflater.finished())
                        throw new IOException("Incomplete deflated HUD");
                } catch (DataFormatException invalid) {
                    throw new IOException("Corrupt deflated HUD", invalid);
                } finally {
                    inflater.end();
                }
            } else {
                throw new IOException("Unsupported HUD compression");
            }
            CRC32 sum = new CRC32();
            sum.update(output);
            if (sum.getValue() != crc)
                throw new IOException("HUD checksum mismatch");
            return output;
        }
    }

    private static String findInstalledMenu(File originals) throws IOException {
        File main = new File(originals, "main");
        File[] archives = main.listFiles((dir, name) ->
                name.toLowerCase(Locale.ROOT).endsWith(".pk3"));
        if (archives == null) return null;
        // Prefer the highest-named localization archive where the user-supplied
        // HUD actually exists. Never read from our generated overlay.
        Arrays.sort(archives, Comparator.comparing(File::getName).reversed());
        int unreadable = 0, withMenu = 0;
        for (File archive : archives) {
            try {
                byte[] data = readArchiveEntry(archive, MENU_FILE);
                if (data == null) continue;
                withMenu++;
                String script = new String(data, StandardCharsets.ISO_8859_1);
                if (script.contains("name \"Compass\"")) {
                    lastDiagnostic = "source=" + archive.getName() + ", badZip=" + unreadable;
                    return script;
                }
            } catch (IOException unreadablePak) {
                unreadable++;
                // Skip unsupported or corrupt archives. The original 1.5
                // game PK3 format is read-only and never edited.
                continue;
            }
        }
        lastDiagnostic = "no compatible ui/hud.menu, badZip=" + unreadable +
                ", hudCandidates=" + withMenu;
        return null;
    }

    static boolean prepare(File originals, File profile, int width, int height)
            throws IOException {
        File main = new File(profile, "main");
        if (!main.isDirectory() && !main.mkdirs()) throw new IOException("HUD profile directory");
        File overlay = new File(main, OVERLAY_NAME);
        String source = findInstalledMenu(originals);
        String patched = source != null ? patchMenu(source, width, height) : null;
        if (patched == null) {
            if (source != null) lastDiagnostic += ", menu layout not recognized";
            Files.deleteIfExists(overlay.toPath()); // only our own generated overlay
            return false;
        }
        File temporary = File.createTempFile(".widescreen-hud-", ".pk3", main);
        try {
            try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(temporary))) {
                zip.putNextEntry(new ZipEntry(MENU_FILE));
                zip.write(patched.getBytes(StandardCharsets.ISO_8859_1));
                zip.closeEntry();
            }
            try {
                Files.move(temporary.toPath(), overlay.toPath(),
                        StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
            } catch (AtomicMoveNotSupportedException unsupported) {
                Files.move(temporary.toPath(), overlay.toPath(),
                        StandardCopyOption.REPLACE_EXISTING);
            }
            return true;
        } finally {
            Files.deleteIfExists(temporary.toPath());
        }
    }
}
