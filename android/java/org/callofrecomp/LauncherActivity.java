package org.callofrecomp;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.DocumentsContract;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

public final class LauncherActivity extends Activity {
    private TextView status;
    private Button play, choose;
    private boolean importing;
    public static File originals(Context c) { return new File(c.getExternalFilesDir(null), "originals"); }
    public static File profile(Context c) { return new File(c.getFilesDir(), "profile"); }
    private static boolean valid(File dir) {
        return Installation.valid(dir);
    }
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL); layout.setPadding(32, 32, 32, 32);
        TextView title = new TextView(this); title.setText("CALLOFRECOMP"); title.setTextSize(30); layout.addView(title);
        TextView description = new TextView(this);
        description.setText("Call of Duty 1.5\n\nImporta tu instalación de PC. La carpeta debe contener CoDSP.exe, las tres DLL y main con los archivos PK3. Las partidas se guardan por separado.\n");
        layout.addView(description);
        status = new TextView(this); layout.addView(status);
        choose = new Button(this); choose.setText("Elegir carpeta del juego"); layout.addView(choose);
        choose.setOnClickListener(v -> startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION), 1));
        play = new Button(this); play.setText("Jugar"); layout.addView(play);
        play.setOnClickListener(v -> { if (!importing && valid(originals(this))) startActivity(new Intent(this, GameActivity.class)); });
        Button log = new Button(this); log.setText("Ver registro"); layout.addView(log);
        log.setOnClickListener(v -> showLog());
        setContentView(layout); refresh();
    }
    @Override protected void onResume() { super.onResume(); if (status != null && !importing) refresh(); }
    private void refresh() {
        boolean ready = valid(originals(this)); play.setEnabled(ready && !importing);
        choose.setEnabled(!importing); status.setText(ready ? "Instalación lista.\n" : "Faltan archivos o la instalación no coincide con la versión 1.5 compatible.\n");
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != 1 || result != RESULT_OK || data == null || data.getData() == null) return;
        Uri tree = data.getData();
        importing = true; play.setEnabled(false); choose.setEnabled(false); status.setText("Importando…");
        new Thread(() -> {
            String message;
            File stage = new File(getExternalFilesDir(null), "import-pending");
            try {
                erase(stage); if (!stage.mkdirs()) throw new IOException("No se pudo crear la carpeta de importación");
                copyTree(tree, DocumentsContract.getTreeDocumentId(tree), stage, false);
                if (!valid(stage)) throw new IOException("Carpeta incompleta o binarios incompatibles: selecciona la instalación 1.5 compatible");
                File previous = new File(getExternalFilesDir(null), "originals-previous");
                erase(previous);
                File target = originals(this);
                if (target.exists() && !target.renameTo(previous)) throw new IOException("No se pudo conservar la instalación anterior");
                if (!stage.renameTo(target)) {
                    previous.renameTo(target);
                    throw new IOException("No se pudo activar la instalación importada");
                }
                erase(previous); message = "Importación terminada.";
            } catch (Exception e) { message = "No se pudo importar: " + e.getMessage(); }
            final String resultMessage = message;
            runOnUiThread(() -> { importing = false; refresh(); status.setText(resultMessage + "\n"); });
        }, "original-import").start();
    }
    private void copyTree(Uri tree, String id, File out, boolean main) throws IOException {
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, id);
        String[] columns = {DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE};
        try (Cursor cursor = getContentResolver().query(children, columns, null, null, null)) {
            if (cursor == null) throw new IOException("El proveedor no respondió");
            while (cursor.moveToNext()) {
                String child = cursor.getString(0), name = cursor.getString(1), mime = cursor.getString(2);
                String lower = name.toLowerCase(Locale.ROOT);
                if (!main && lower.equals("main") && DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                    File folder = new File(out, "main"); folder.mkdirs(); copyTree(tree, child, folder, true);
                } else if (main ? lower.endsWith(".pk3") : lower.equals("codsp.exe") || lower.equals("gamex86.dll")
                        || lower.equals("cgamex86.dll") || lower.equals("uix86.dll")) {
                    if (name.contains("/") || name.contains("\\") || name.equals("..")) throw new IOException("Nombre de archivo inválido");
                    String canonical = lower.equals("codsp.exe") ? "CoDSP.exe" : lower;
                    runOnUiThread(() -> status.setText("Importando " + name + "…"));
                    try (InputStream in = getContentResolver().openInputStream(DocumentsContract.buildDocumentUriUsingTree(tree, child));
                         OutputStream dest = new FileOutputStream(new File(out, canonical))) {
                        if (in == null) throw new IOException("No se pudo abrir " + name);
                        byte[] buffer = new byte[1024 * 1024]; int count;
                        while ((count = in.read(buffer)) != -1) dest.write(buffer, 0, count);
                    }
                }
            }
        }
    }
    private static void erase(File file) throws IOException {
        if (!file.exists()) return;
        if (file.isDirectory()) {
            File[] children = file.listFiles(); if (children == null) throw new IOException("No se pudo leer " + file.getName());
            for (File child : children) erase(child);
        }
        if (!file.delete()) throw new IOException("No se pudo borrar " + file.getName());
    }
    private void showLog() {
        String text;
        File log = new File(profile(this), "codrecomp.log");
        try (RandomAccessFile in = new RandomAccessFile(log, "r")) {
            long offset = Math.max(0, in.length() - 32000); in.seek(offset);
            byte[] data = new byte[(int)(in.length() - offset)]; in.readFully(data); text = new String(data, StandardCharsets.UTF_8);
        } catch (IOException e) { text = "Todavía no hay registro del juego."; }
        new AlertDialog.Builder(this).setTitle("Registro").setMessage(text).setPositiveButton("Cerrar", null).show();
    }
}
