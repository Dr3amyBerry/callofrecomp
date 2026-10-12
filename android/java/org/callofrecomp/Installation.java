package org.callofrecomp;
import java.io.File;
import java.io.FileInputStream;
import java.security.MessageDigest;
import java.util.Locale;

final class Installation {
    static String language(File dir) {
        File main = new File(dir, "main");
        String preferred = Locale.getDefault().getLanguage();
        // cl_language takes numeric indices from the verified original table:
        // analysis/localization_searchpath.md (VA 0x00564B08), not language names.
        String[][] languages = {{"es", "spanish", "4"}, {"fr", "french", "1"}, {"de", "german", "2"},
            {"it", "italian", "3"}, {"en", "english", "0"}};
        for (String[] entry : languages)
            if (entry[0].equals(preferred) && new File(main, "localized_" + entry[1] + "_pak0.pk3").isFile()) return entry[2];
        for (String[] entry : languages)
            if (new File(main, "localized_" + entry[1] + "_pak0.pk3").isFile()) return entry[2];
        return "0";
    }
    static boolean valid(File dir) {
        String[][] baseline = {
            {"CoDSP.exe", "c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47"},
            {"gamex86.dll", "27930aa3f663d0af39a90e6956c980be1e599e0f0c98191a9fb7eaba61481577"},
            {"cgamex86.dll", "6e51c61f3780654cbaecdef149810ccf3ab665aaeafa5ae75a13f714abc0f29b"},
            {"uix86.dll", "dd0738043c287a923357afe53bf2084fda8dd121ece20fcd57828bf5d8c68a4e"}
        };
        for (String[] entry : baseline) {
            try (FileInputStream in = new FileInputStream(new File(dir, entry[0]))) {
                MessageDigest digest = MessageDigest.getInstance("SHA-256");
                byte[] buffer = new byte[65536]; int count;
                while ((count = in.read(buffer)) != -1) digest.update(buffer, 0, count);
                StringBuilder hash = new StringBuilder();
                for (byte b : digest.digest()) hash.append(String.format(Locale.ROOT, "%02x", b & 255));
                if (!hash.toString().equals(entry[1])) return false;
            } catch (Exception e) { return false; }
        }
        File[] packs = new File(dir, "main").listFiles((f, n) -> n.toLowerCase(Locale.ROOT).endsWith(".pk3"));
        return packs != null && packs.length > 0;
    }
}
