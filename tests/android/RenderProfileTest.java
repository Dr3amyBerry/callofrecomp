package org.callofrecomp;

public final class RenderProfileTest {
    public static void main(String[] args) {
        int[][] screens = {{1920,1080}, {2400,1080}, {1280,720}, {800,480}, {1080,2400}};
        for (int[] screen : screens) {
            int w = Math.max(screen[0], screen[1]), h = Math.min(screen[0], screen[1]);
            for (int mode = 0; mode < 3; mode++) {
                int[] result = RenderProfile.size(screen[0], screen[1], mode);
                if (result[0] > w || result[1] > h || result[0] <= 0 || result[1] <= 0)
                    throw new AssertionError("Profiles must not upscale the surface");
                if (Math.abs((double)result[0] / result[1] / ((double)w / h) - 1) > .004)
                    throw new AssertionError("Render budget must preserve the panoramic aspect");
                if (mode == 0 && (result[0] > 1280 || result[1] > 720)) throw new AssertionError("Balanced budget");
                if (mode == 1 && (result[0] > 960 || result[1] > 540)) throw new AssertionError("Light budget");
                if (mode == 2 && (result[0] != w || result[1] != h)) throw new AssertionError("Native size");
            }
        }
        int[] balanced = RenderProfile.size(1920,1080,0), light = RenderProfile.size(1920,1080,1);
        if (balanced[0] != 1280 || balanced[1] != 720 || light[0] != 960 || light[1] != 540)
            throw new AssertionError("Expected full-screen buffer budgets");
        System.out.println("Android render budgets and panoramic proportions passed");
    }
}
