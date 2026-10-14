package org.callofrecomp;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

/** Pure Java test: no proprietary assets, Android runtime, or special fonts. */
public final class HudWidescreenSmoke {
    private static void check(boolean value, String what) {
        if (!value) throw new AssertionError(what);
    }
    private static String syntheticMenu() {
        StringBuilder s = new StringBuilder("#include \"ui/menudef.h\"\n"
                + "menuDef { name \"Cursorhints\" rect 300 325 40 40 "
                + "itemDef { rect 0 0 40 40 } }\n"
                + "menuDef { name \"stance\" rect 100 434.375 40 40 "
                + "itemDef { rect 0 0 40 40 } }\n"
                + "menuDef { name \"tankstatus\" rect 100 434.375 40 40 "
                + "itemDef { rect 0 0 40 40 } "
                + "itemDef { rect 20 20 40 40 } }\n"
                + "menuDef { name \"Health\" rect 488 460 0 0 "
                + "itemDef { name \"healthbarback\" rect 13 0 130 12 } "
                + "itemDef { name \"healthbar\" rect 14 1 128 10 } "
                + "itemDef { name \"healthbarcross\" rect 0 0 12 12 } }\n"
                + "menuDef { name \"Compass\" "
                + "rect COMPASS_X COMPASS_Y COMPASS_SIZE COMPASS_SIZE ");
        s.append("itemDef { name \"compassback\" "
                + "rect 0 0 COMPASS_SIZE COMPASS_SIZE }\n");
        for (int i = 0; i < 5; i++)
            s.append("itemDef { rect 0 0 COMPASS_SIZE COMPASS_SIZE }\n");
        s.append("itemDef { name \"compassneedle\" "
                + "rect COMPASS_NEEDLE_XOFF COMPASS_NEEDLE_YOFF "
                + "COMPASS_NEEDLE_WIDTH COMPASS_NEEDLE_HEIGHT } }\n");
        return s.toString();
    }
    private static int count(String s, String needle) {
        int n = 0, at = 0;
        while ((at = s.indexOf(needle, at)) >= 0) {
            n++;
            at += needle.length();
        }
        return n;
    }
    public static void main(String[] args) throws Exception {
        String source = syntheticMenu();
        String wide = HudWidescreen.patchMenu(source, 1280, 574);
        check(wide != null, "wide HUD must be supported");
        check(wide.contains("rect 7.166667 COMPASS_Y 95.666667 COMPASS_SIZE"),
                "compass should maintain center and circular physical dimensions");
        check(wide.contains("rect 35.875000 COMPASS_NEEDLE_YOFF 23.916667 COMPASS_NEEDLE_HEIGHT"),
                "needle offset and width need matching X compensation");
        check(count(wide, "rect 0 0 95.666667 COMPASS_SIZE") == 6,
                "six compass layers must share the correction");
        check(wide.contains("rect 308.041667 325 23.916667 40"),
                "cursor icon centered without horizontal stretching");
        check(wide.contains("rect 108.041667 434.375 23.916667 40"),
                "stance and tank icon should preserve their centers");
        check(wide.contains("rect 11.958333 20 23.916667 40"),
                "tank secondary icon must preserve relative X");
        check(wide.contains("rect 545.497917 460 0 0"),
                "health strip stays anchored at the original right edge");
        check(wide.contains("rect 7.772917 0 77.729167 12"),
                "health backdrop must preserve its original proportions");
        check(wide.contains("rect 8.370833 1 76.533333 10"),
                "the filled health bar must remain aligned with its backdrop");
        check(wide.contains("rect 0 0 7.175000 12"),
                "medical cross must be physically square");
        check(source.contains("rect 13 0 130 12"),
                "original health HUD remains unmodified");
        String incompatible = source.replace("rect 14 1 128 10", "rect 14 1 127 10");
        String fallback = HudWidescreen.patchMenu(incompatible, 1280, 576);
        check(fallback != null && fallback.contains("rect 488 460 0 0") &&
                fallback.contains("rect 14 1 127 10"),
                "unsupported customized health strips must be left alone");
        check(source.contains("rect 300 325 40 40"),
                "source must be left unchanged");
        check(HudWidescreen.patchMenu(source, 640, 480) == null,
                "no correction for original 4:3");
        check(HudWidescreen.patchMenu(source.replace("name \"compassneedle\"", "name \"unknown\""),
                1280, 574) == null,
                "fail closed on unknown HUD layout");
        check(HudWidescreen.patchMenu(source, 1920, 1080)
                .contains("rect -5.000000 COMPASS_Y 120.000000 COMPASS_SIZE"),
                "16:9 ratios must also use real aspect");
        File root = Files.createTempDirectory("hud-widescreen-smoke").toFile();
        File main = new File(root, "game/main");
        File profile = new File(root, "profile");
        check(main.mkdirs(), "create test game directory");
        File originalPak = new File(main, "localized_spanish_pak0.pk3");
        try (ZipOutputStream zip = new ZipOutputStream(new FileOutputStream(originalPak))) {
            zip.putNextEntry(new ZipEntry("ui/hud.menu"));
            zip.write(source.getBytes(StandardCharsets.ISO_8859_1));
            zip.closeEntry();
        }
        // Reproduce the strict Android ZipFile rejecting one original PK3
        // while the valid localized HUD lives in a different archive.
        // Duplicate central directory names occur in original 2003 PK3s:
        // strict Android ZipFile rejects them before inspecting ui/hud.menu.
        // Build an entirely synthetic duplicate index from our one-entry ZIP.
        byte[] valid = Files.readAllBytes(originalPak.toPath());
        int endIndex = valid.length - 22;
        int cdPosition = (int) ((valid[endIndex + 16] & 255) |
                ((valid[endIndex + 17] & 255) << 8) |
                ((valid[endIndex + 18] & 255) << 16) |
                ((valid[endIndex + 19] & 255) << 24));
        int cdLength = endIndex - cdPosition;
        check(cdLength > 0, "synthetic central directory");
        byte[] duplicate = new byte[valid.length + cdLength];
        System.arraycopy(valid, 0, duplicate, 0, endIndex);
        System.arraycopy(valid, cdPosition, duplicate, endIndex, cdLength);
        System.arraycopy(valid, endIndex, duplicate, endIndex + cdLength, 22);
        int newEnd = endIndex + cdLength;
        duplicate[newEnd + 8] = 2; // central records on this disk
        duplicate[newEnd + 10] = 2; // total central records
        int doubleSize = cdLength * 2;
        for (int i = 0; i < 4; i++)
            duplicate[newEnd + 12 + i] = (byte)(doubleSize >>> (8 * i));
        File duplicates = new File(main, "zzzz_original_with_duplicate_entries.pk3");
        Files.write(duplicates.toPath(), duplicate);
        check(HudWidescreen.prepare(new File(root, "game"), profile, 1280, 574),
                "prepare a private override from a valid duplicated-central-entry PK3");
        check(HudWidescreen.lastDiagnostic.contains("zzzz_original_with_duplicate_entries.pk3"),
                "our ZIP32 reader must accept a duplicated directory entry");
        File overlay = new File(profile, "main/zzzz_codrecomp_hud_fix.pk3");
        check(overlay.isFile(), "overlay exists");
        try (ZipFile zip = new ZipFile(overlay)) {
            check(zip.size() == 1, "only original user's HUD script copied");
            check(zip.getEntry("ui/hud.menu") != null, "HUD path in override");
            String text = new String(zip.getInputStream(zip.getEntry("ui/hud.menu")).readAllBytes(),
                    StandardCharsets.ISO_8859_1);
            check(text.equals(wide), "overlay contents match the dynamic patch");
        }
        try (ZipFile untouched = new ZipFile(originalPak)) {
            String original = new String(untouched.getInputStream(untouched.getEntry("ui/hud.menu"))
                    .readAllBytes(), StandardCharsets.ISO_8859_1);
            check(original.equals(source), "never edit the original PK3");
        }
        check(!HudWidescreen.prepare(new File(root, "game"), profile, 640, 480),
                "4:3 must disable the fix");
        check(!overlay.exists(), "stale overlay must be removed for 4:3");
        check(HudWidescreen.prepare(new File(root, "game"), profile, 1280, 574),
                "regenerate when widescreen returns");
        check(duplicates.delete(), "remove duplicate synthetic archive");
        check(originalPak.delete(), "remove test source");
        check(!HudWidescreen.prepare(new File(root, "game"), profile, 1280, 574),
                "absent script must not keep a stale override");
        check(!overlay.exists(), "no stale file with missing original");
        System.out.println("HUD widescreen synthetic ZIP/geometry: PASS");
    }
}
