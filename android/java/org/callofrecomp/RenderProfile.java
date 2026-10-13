package org.callofrecomp;

/** Render-buffer budget; the Android view and touch overlay remain full size. */
final class RenderProfile {
    static int[] size(int width, int height, int mode) {
        if (width <= 0 || height <= 0) { width = 1280; height = 720; }
        int longSide = Math.max(width, height), shortSide = Math.min(width, height);
        if (mode == 2) return new int[]{longSide, shortSide};
        int maxWidth = mode == 1 ? 960 : 1280, maxHeight = mode == 1 ? 540 : 720;
        double scale = Math.min(1, Math.min((double)maxWidth / longSide, (double)maxHeight / shortSide));
        return new int[]{Math.max(2, (int)(longSide * scale) / 2 * 2),
            Math.max(2, (int)(shortSide * scale) / 2 * 2)};
    }
    static String[] graphicsArguments(int mode) {
        int mip = mode == 2 ? 0 : mode == 1 ? 2 : 1;
        return new String[]{"+set", "r_picmip", Integer.toString(mip),
            "+set", "r_lodbias", Integer.toString(mip),
            "+set", "r_dynamiclight", mode == 2 ? "1" : "0",
            "+set", "cg_shadows", mode == 2 ? "1" : "0",
            "+set", "r_detailtextures", mode == 1 ? "0" : "1",
            "+set", "r_fastsky", mode == 1 ? "1" : "0",
            "+set", "r_drawSun", mode == 2 ? "1" : "0"};
    }
}
