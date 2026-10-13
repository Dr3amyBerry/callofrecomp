import {collectFiles, validateBinaries, writePackage} from './package.mjs';
const $ = id => document.getElementById(id);
let entries = [], busy = false, selectionGeneration = 0, controller;
const describe = size => (size / 1024 ** 3).toFixed(2) + ' GiB';
function status(message,error=false){$('status').textContent=message;$('status').classList.toggle('error',error);}
$('folder').addEventListener('change', async event => {
  if (busy) return;
  const generation = ++selectionGeneration;
  entries=[];$('prepare').disabled=true;$('selection').hidden=true;
  try {
    const candidate=collectFiles(event.target.files);
    status('Comprobando los cuatro binarios compatibles…');
    await validateBinaries(candidate);
    if (generation !== selectionGeneration) return;
    entries=candidate;const size=entries.reduce((n,e)=>n+e.file.size,0);
    $('selection').textContent=entries.length+' archivos · '+describe(size)+' · Call of Duty 1.5 compatible';
    $('selection').hidden=false;
    if (!window.showSaveFilePicker && size > 512 * 1024 ** 2)
      throw new Error('Esta instalación necesita escritura directa en disco. Abre esta web en Chrome o Edge en PC para crear el paquete sin cargarlo en memoria.');
    $('prepare').disabled=false;status('Todo listo. El paquete incluirá los binarios y los PK3.');
  } catch(error){if(generation===selectionGeneration)status(error.message,true);}
});
$('cancel').addEventListener('click',()=>controller?.abort());
$('prepare').addEventListener('click',async()=>{
  if(busy||!entries.length)return;
  busy=true;controller=new AbortController();$('prepare').disabled=true;$('folder').disabled=true;
  $('cancel').hidden=false;$('progress').hidden=false;$('progress').value=0;
  let writer, handle;
  try {
    // Invoke save picker during the click's user activation, before asynchronous work.
    if(window.showSaveFilePicker){
      handle=await window.showSaveFilePicker({suggestedName:'callofrecomp.codpack',types:[{description:'Instalación CallofRecomp',accept:{'application/octet-stream':['.codpack']}}]});
      if(controller.signal.aborted)throw new Error('Preparación cancelada.');
      writer=await handle.createWritable();
    } else {
      const parts=[];let url;
      writer={write:async data=>parts.push(data),close:async()=>{
        url=URL.createObjectURL(new Blob(parts,{type:'application/octet-stream'}));
        const link=document.createElement('a');link.href=url;link.download='callofrecomp.codpack';link.click();
        setTimeout(()=>URL.revokeObjectURL(url),60000);
      },abort:async()=>{parts.length=0;}};
    }
    status('Preparando el paquete…');let lastUpdate=0;
    await writePackage(entries,writer,({path,done,total})=>{
      if(performance.now()-lastUpdate<100&&done!==total)return;lastUpdate=performance.now();
      $('progress').value=done/total*100;status(path+' · '+Math.floor(done/total*100)+'%');
    },controller.signal);
    await writer.close();writer=null;
    status(handle?'Paquete guardado. Cópialo al teléfono e impórtalo en CallofRecomp.':'Descarga preparada. Cópiala al teléfono cuando termine e impórtala en CallofRecomp.');
  } catch(error){
    if(writer)try{await writer.abort();}catch{}
    status(error.name==='AbortError'?'Preparación cancelada.':error.message,error.name!=='AbortError'&&!controller.signal.aborted);
  } finally{busy=false;$('folder').disabled=false;$('prepare').disabled=false;$('cancel').hidden=true;}
});
