package org.callofrecomp;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.CRC32;

/** Streaming CODPACK1 decoder. Only writes into an empty staging directory. */
final class GamePackage {
    interface Progress { void file(String name); }
    static final long MAX_FILE = 2L * 1024 * 1024 * 1024;
    static final long MAX_TOTAL = 8L * 1024 * 1024 * 1024;
    static void unpack(InputStream source, File stage, Progress progress) throws IOException {
        String[] existing = stage.list();
        if (existing == null || existing.length != 0) throw new IOException("La carpeta temporal no está vacía");
        DataInputStream in = new DataInputStream(new BufferedInputStream(source, 65536));
        byte[] magic = new byte[8]; in.readFully(magic);
        if (!Arrays.equals(magic, "CODPACK1".getBytes(StandardCharsets.US_ASCII)))
            throw new IOException("Formato no compatible: elige un archivo .codpack");
        int count = in.readInt();
        if (count < 5 || count > 1024) throw new IOException("Cantidad de archivos inválida");
        Set<String> names = new HashSet<>();
        byte[] buffer = new byte[1024 * 1024];
        long total = 0; boolean hasPack = false;
        for (int i = 0; i < count; i++) {
            int nameLength = in.readUnsignedShort();
            if (nameLength < 1 || nameLength > 200) throw new IOException("Nombre demasiado largo");
            byte[] nameBytes = new byte[nameLength]; in.readFully(nameBytes);
            String name = new String(nameBytes, StandardCharsets.US_ASCII);
            boolean pack = name.matches("main/[a-z0-9_.-]+\\.pk3") && !name.contains("..");
            boolean binary = name.equals("CoDSP.exe") || name.equals("gamex86.dll")
                || name.equals("cgamex86.dll") || name.equals("uix86.dll");
            if ((!pack && !binary) || !names.add(name)) throw new IOException("Archivo no permitido o duplicado: " + name);
            long size = in.readLong();
            if (size <= 0 || size > MAX_FILE || total > MAX_TOTAL - size) throw new IOException("Tamaño inválido: " + name);
            total += size;
            if (stage.getUsableSpace() < size + 32L * 1024 * 1024) throw new IOException("No hay espacio suficiente para " + name);
            File output = new File(stage, name);
            if (!output.getCanonicalPath().startsWith(stage.getCanonicalPath() + File.separator))
                throw new IOException("Ruta no permitida");
            File parent = output.getParentFile();
            if (!parent.isDirectory() && !parent.mkdirs()) throw new IOException("No se pudo crear main");
            progress.file(name); CRC32 crc = new CRC32();
            try (OutputStream dest = new BufferedOutputStream(new FileOutputStream(output), 65536)) {
                long remaining = size;
                while (remaining > 0) {
                    int read = in.read(buffer, 0, (int)Math.min(buffer.length, remaining));
                    if (read < 0) throw new EOFException("Paquete incompleto: " + name);
                    if (read == 0) continue;
                    dest.write(buffer, 0, read); crc.update(buffer, 0, read); remaining -= read;
                }
            }
            if (Integer.toUnsignedLong(in.readInt()) != crc.getValue()) throw new IOException("Archivo dañado: " + name);
            hasPack |= pack;
        }
        if (!hasPack || !names.containsAll(Arrays.asList("CoDSP.exe", "gamex86.dll", "cgamex86.dll", "uix86.dll")))
            throw new IOException("Faltan archivos de la instalación");
        if (in.read() != -1) throw new IOException("Contenido inesperado al final del paquete");
    }
}
