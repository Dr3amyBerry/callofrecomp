import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {collectFiles, writePackage, crc32} from '../web/dist/package.mjs';

assert.equal(crc32(new TextEncoder().encode('123456789')), 0xcbf43926);
const names = ['CoDSP.exe', 'gamex86.dll', 'cgamex86.dll', 'uix86.dll', 'main/pak0.pk3'];
function fake(path) {
  const file = new Blob(['synthetic:' + path]);
  return Object.assign(file, {name:path.split('/').at(-1), webkitRelativePath:'Call of Duty/' + path});
}
const files = collectFiles([...names.map(fake), fake('CoDMP.exe'), fake('main/config.cfg')]);
assert.equal(files.length, 5);
assert.equal(collectFiles(names.map(n => fake(n.toUpperCase()))).length, 5);
assert.throws(() => collectFiles(names.filter(n => n !== 'uix86.dll').map(fake)), /Falta/);
assert.throws(() => collectFiles([...names.map(fake), fake('main/PAK0.pk3')]), /duplicado/);
assert.throws(() => collectFiles([...names.map(fake), fake('main/../escape.pk3')]), /Nombre/);
assert.throws(() => collectFiles([...names.map(fake), fake('other/main/pak1.pk3')]), /instalación/);
const parts = [];
await writePackage(files, {write: async b => parts.push(b.slice())}, () => {});
const data = new Uint8Array(await new Blob(parts).arrayBuffer());
assert.equal(new TextDecoder().decode(data.slice(0, 8)), 'CODPACK1');
assert.equal(new DataView(data.buffer).getUint32(8), 5);
let offset = 12;
for (const {path, file} of files) {
  const view = new DataView(data.buffer);
  const size = view.getUint16(offset); offset += 2;
  assert.equal(new TextDecoder().decode(data.slice(offset, offset + size)), path); offset += size;
  const length = Number(view.getBigUint64(offset)); offset += 8;
  assert.equal(length, file.size);
  const bytes = data.slice(offset, offset + length); offset += length;
  assert.equal(view.getUint32(offset), crc32(bytes)); offset += 4;
}
assert.equal(offset, data.length);
const controller = new AbortController(); controller.abort();
await assert.rejects(writePackage(files, {write: async () => {}}, () => {}, controller.signal), /cancelada/);
if (process.argv[2]) await writeFile(process.argv[2], data);
console.log('CODPACK web: selection, exclusions, CRC, wire format, cancellation OK');
