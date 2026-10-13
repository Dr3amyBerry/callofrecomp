// CODPACK1: no dependencies, no requests, bounded-memory sequential writing.
export const BASELINE = Object.freeze({
  'CoDSP.exe':'c755c7da411c87039ade462a2299402c3c4ca5c4fc4f1ae5cea6e25b05c69f47',
  'gamex86.dll':'27930aa3f663d0af39a90e6956c980be1e599e0f0c98191a9fb7eaba61481577',
  'cgamex86.dll':'6e51c61f3780654cbaecdef149810ccf3ab665aaeafa5ae75a13f714abc0f29b',
  'uix86.dll':'dd0738043c287a923357afe53bf2084fda8dd121ece20fcd57828bf5d8c68a4e'
});
const table = new Uint32Array(256);
for (let n = 0; n < 256; n++) {
  let c = n;
  for (let k = 0; k < 8; k++) c = (c & 1) ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  table[n] = c >>> 0;
}
export function crc32(bytes, previous = 0) {
  let crc = previous ^ 0xffffffff;
  for (let i = 0; i < bytes.length; i++) crc = table[(crc ^ bytes[i]) & 255] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}
export function collectFiles(input) {
  const selected = new Map(); let root = null; let total = 0;
  for (const file of input) {
    const full = file.webkitRelativePath || file.name;
    const parts = full.split('/');
    if (parts.length < 2) throw new Error('Selecciona la carpeta de instalación, no archivos sueltos.');
    if (root === null) root = parts[0];
    if (parts[0] !== root) throw new Error('Selecciona una sola instalación.');
    const relative = parts.slice(1).join('/').toLowerCase();
    const binary = Object.keys(BASELINE).find(n => n.toLowerCase() === relative);
    const pack = relative.startsWith('main/') && relative.endsWith('.pk3');
    if (!binary && !pack) {
      if (/\/(codsp\.exe|gamex86\.dll|cgamex86\.dll|uix86\.dll|main\/[^/]+\.pk3)$/.test(relative))
        throw new Error('Selecciona la carpeta de instalación que contiene CoDSP.exe y main, no su carpeta superior.');
      continue;
    }
    const path = binary || relative;
    if (path.length > 200 || (pack && (!/^main\/[a-z0-9_.-]+\.pk3$/.test(path) || path.includes('..'))))
      throw new Error('Nombre de archivo no compatible: ' + path);
    if (selected.has(path)) throw new Error('Archivo duplicado: ' + path);
    if (file.size <= 0 || file.size > 2 * 1024 ** 3) throw new Error('Tamaño no compatible: ' + path);
    total += file.size;
    if (total > 8 * 1024 ** 3 || selected.size >= 1024) throw new Error('La instalación supera los límites del paquete.');
    selected.set(path, {path, file});
  }
  for (const name of Object.keys(BASELINE)) if (!selected.has(name)) throw new Error('Falta ' + name + ' en la carpeta elegida.');
  if (![...selected.keys()].some(n => n.startsWith('main/'))) throw new Error('Faltan los archivos main/*.pk3.');
  return [...selected.values()].sort((a,b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0);
}
export async function validateBinaries(entries) {
  for (const [name, expected] of Object.entries(BASELINE)) {
    const file = entries.find(e => e.path === name).file;
    if (file.size > 32 * 1024 ** 2) throw new Error(name + ' no coincide con la versión compatible.');
    const digest = await crypto.subtle.digest('SHA-256', await file.arrayBuffer());
    const actual = [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2,'0')).join('');
    if (actual !== expected) throw new Error(name + ' no coincide con Call of Duty 1.5 compatible. Comprueba el parche y los binarios originales.');
  }
}
export async function writePackage(entries, writer, progress, signal) {
  const check = () => { if (signal?.aborted) throw new Error('Preparación cancelada.'); };
  check();
  const header = new Uint8Array(12); header.set(new TextEncoder().encode('CODPACK1'));
  new DataView(header.buffer).setUint32(8, entries.length); await writer.write(header);
  const total = entries.reduce((n,e) => n + e.file.size, 0); let done = 0;
  for (const {path, file} of entries) {
    check(); const name = new TextEncoder().encode(path);
    const meta = new Uint8Array(2 + name.length + 8); const view = new DataView(meta.buffer);
    view.setUint16(0,name.length); meta.set(name,2); view.setBigUint64(2+name.length,BigInt(file.size));
    await writer.write(meta); let crc = 0;
    for (let offset = 0; offset < file.size; offset += 1024 ** 2) {
      check(); const bytes = new Uint8Array(await file.slice(offset, offset + 1024 ** 2).arrayBuffer());
      crc = crc32(bytes,crc); await writer.write(bytes); done += bytes.length;
      progress({path,done,total});
      // Allow controls and cancellation to respond on slower devices.
      await new Promise(resolve => setTimeout(resolve,0));
    }
    const footer = new Uint8Array(4); new DataView(footer.buffer).setUint32(0,crc); await writer.write(footer);
  }
  check();
}
