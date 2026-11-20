import { loadPDF, renderPage, validateMiddle, MM } from './renderer.js';
import { listStamps, putStamp, removeStamp } from './library.js';
import { zip, strToU8 } from './vendor/fflate.mjs';

const $ = id => document.getElementById(id);
const state = { files: [], bytes: null, original: null, stamp: null, page: 1, zoom: 1, busy: false,
  pageWidth: 0, pageHeight: 0, scale: 1, saved: [], urls: [], previewId: 0, run: 0 };
let worker, nextId = 0;
const waiting = new Map();
function message(text, type = '') { $('notice').textContent = text; $('notice').className = `notice ${type}`; }
function friendly(error) {
  if (error?.name === 'PasswordException') return 'Este PDF está protegido. Usa una copia autorizada sin contraseña.';
  if (error?.name === 'InvalidPDFException') return 'El archivo no es un PDF válido o está dañado.';
  return error?.message || 'No se pudo completar la operación. Prueba con otro archivo.';
}
function terminateWorker(reason = 'Proceso cancelado.') {
  worker?.terminate(); worker = null;
  for (const request of waiting.values()) { clearTimeout(request.timeout); request.reject(new Error(reason)); }
  waiting.clear();
}
function request(data) {
  if (!worker) {
    worker = new Worker(new URL('./pdf-worker.js', import.meta.url), { type: 'module' });
    worker.onmessage = ({ data: response }) => {
      if (response.type === 'status') { $('preview-status').textContent = response.message; return; }
      const job = waiting.get(response.id);
      if (!job) return;
      clearTimeout(job.timeout); waiting.delete(response.id);
      response.error ? job.reject(new Error(response.error)) : job.resolve(response);
    };
    worker.onerror = () => terminateWorker('El motor no pudo iniciarse. Actualiza Chrome, Edge o Firefox y vuelve a intentarlo.');
  }
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => terminateWorker('El documento tardó demasiado. Prueba con un PDF más pequeño.'), 180000);
    waiting.set(id, { resolve, reject, timeout });
    worker.postMessage({ ...data, id });
  });
}
function options() {
  const result = { width: Number($('width').value), top: Number($('top').value), right: Number($('right').value), layer: $('layer').value };
  if (!$('width').value || !$('top').value || !$('right').value || ![result.width, result.top, result.right].every(Number.isFinite) || result.width <= 0 || result.top < 0 || result.right < 0) {
    throw new Error('Introduce un ancho mayor que cero y márgenes iguales o mayores que cero.');
  }
  return result;
}
function updateControls() {
  const hasFile = !!state.original;
  $('export').disabled = state.busy || !state.files.length || !state.stamp;
  $('save-stamp').disabled = state.busy || !state.stamp;
  $('delete-stamp').disabled = state.busy || !$('saved-stamps').value;
  $('file-list').disabled = state.busy || !state.files.length;
  for (const id of ['zoom-in', 'zoom-out', 'fit']) $(id).disabled = state.busy || !hasFile;
  $('previous').disabled = state.busy || !hasFile || state.page <= 1;
  $('next').disabled = state.busy || !hasFile || state.page >= state.original.numPages;
  $('page-label').textContent = hasFile ? `${state.page} / ${state.original.numPages}` : '— / —';
  $('export').textContent = state.files.length > 1 ? `Sellar ${state.files.length} PDF` : 'Descargar PDF sellado';
  if (!state.busy) $('export-hint').textContent = state.files.length && state.stamp ? 'Se aplicará a todas las páginas.' : 'Selecciona un PDF y una imagen para empezar.';
}
function setBusy(busy) {
  state.busy = busy; $('controls').disabled = busy; $('empty-choose').disabled = busy;
  document.body.classList.toggle('busy', busy); updateControls();
}
function clearResults() { for (const url of state.urls) URL.revokeObjectURL(url); state.urls = []; $('result-links').replaceChildren(); $('results').hidden = true; }
function addDownload(blob, name, label) {
  const url = URL.createObjectURL(blob); state.urls.push(url);
  const link = document.createElement('a'); link.href = url; link.download = name; link.textContent = label;
  $('result-links').append(link); return link;
}

async function selectFiles(files, folder = false) {
  if (state.busy) return;
  let selected = [...files].filter(file => /\.pdf$/i.test(file.name));
  if (folder) selected = selected.filter(file => file.webkitRelativePath.split('/').length === 2);
  if (!selected.length) { message('No hay PDF en la selección. Las subcarpetas no se incluyen.', 'error'); return; }
  if (selected.length > 100 || selected.some(f => f.size > 50 * 1024 ** 2) || selected.reduce((sum, f) => sum + f.size, 0) > 150 * 1024 ** 2) {
    message('Elige hasta 100 PDF, de máximo 50 MB cada uno y 150 MB en total. Divide carpetas grandes en varios grupos.', 'error'); return;
  }
  selected.sort((a, b) => a.name.localeCompare(b.name, 'es', { numeric: true }));
  state.files = selected; clearResults();
  $('file-list').replaceChildren(...selected.map((file, i) => new Option(file.name, String(i))));
  $('file-count').textContent = String(selected.length);
  await openDocument(0);
}
async function openDocument(index) {
  if (state.busy) return;
  setBusy(true); ++state.previewId;
  $('preview-status').textContent = 'Abriendo documento…';
  $('paper').hidden = true; $('stamp-handle').hidden = true;
  try {
    const bytes = new Uint8Array(await state.files[index].arrayBuffer());
    const doc = await loadPDF(bytes);
    await state.original?.loadingTask.destroy();
    state.original = doc; state.bytes = bytes; state.page = 1; state.zoom = 1;
    $('empty-preview').hidden = true;
    message(`${state.files.length} documento${state.files.length > 1 ? 's' : ''} seleccionado${state.files.length > 1 ? 's' : ''}. ${state.stamp ? 'Revisa la posición del sello.' : 'Ahora elige la imagen de tu sello.'}`);
  } catch (error) {
    await state.original?.loadingTask.destroy(); state.original = null; state.bytes = null;
    $('empty-preview').hidden = false; $('preview-status').textContent = 'No se pudo abrir';
    message(friendly(error), 'error');
  } finally { setBusy(false); schedulePreview(); }
}

async function normalizeImage(blob, name) {
  if (blob.size > 20 * 1024 ** 2) throw new Error('La imagen no puede superar los 20 MB.');
  let bitmap;
  try { bitmap = await createImageBitmap(blob); } catch { throw new Error('No se pudo leer la imagen. Usa PNG, JPG, WEBP o BMP.'); }
  try {
    const factor = Math.min(1, 2048 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(bitmap.width * factor)); canvas.height = Math.max(1, Math.round(bitmap.height * factor));
    const ctx = canvas.getContext('2d'); ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const rgba = new Uint8Array(ctx.getImageData(0, 0, canvas.width, canvas.height).data);
    const png = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
    if (!png) throw new Error('No se pudo preparar la imagen.');
    return { name, blob: png, rgba, width: canvas.width, height: canvas.height };
  } finally { bitmap.close(); }
}
function showStamp(stamp) {
  if (state.stamp?.url) URL.revokeObjectURL(state.stamp.url);
  stamp.url = URL.createObjectURL(stamp.blob); state.stamp = stamp;
  $('stamp-thumbnail').src = stamp.url; $('stamp-thumbnail').hidden = false; $('stamp-placeholder').hidden = true;
  $('stamp-name').textContent = stamp.name; updateControls(); schedulePreview();
}
async function chooseImage(file) {
  if (!file || state.busy) return;
  try { showStamp(await normalizeImage(file, file.name)); $('saved-stamps').value = ''; updateControls(); message('Sello cargado. Ajusta sus medidas o arrástralo en la vista previa.'); }
  catch (error) { message(friendly(error), 'error'); }
}

let previewTimer, previewRunning = false, previewQueued = false;
function schedulePreview(delay = 250) {
  ++state.previewId; clearTimeout(previewTimer);
  $('stamp-handle').hidden = true;
  previewTimer = setTimeout(() => { previewQueued = true; drainPreview(); }, delay);
}
async function drainPreview() {
  if (previewRunning || state.busy || !state.original || !previewQueued) return;
  previewRunning = true; previewQueued = false;
  const version = state.previewId;
  let renderedDoc;
  try {
    $('preview-status').textContent = 'Actualizando…';
    const originalPage = await state.original.getPage(state.page);
    const dimensions = originalPage.getViewport({ scale: 1 });
    let page = originalPage;
    if (state.stamp) {
      const stamp = state.stamp;
      const response = await request({ pdf: state.bytes, rgba: stamp.rgba, width: stamp.width, height: stamp.height, options: options(), pageIndex: state.page - 1 });
      if (version !== state.previewId) return;
      await validateMiddle(response.source, response.check);
      renderedDoc = await loadPDF(response.pdf); page = await renderedDoc.getPage(1);
    }
    if (version !== state.previewId) return;
    state.pageWidth = dimensions.width; state.pageHeight = dimensions.height;
    const available = Math.max(180, $('preview-area').clientWidth - 58);
    const availableHeight = Math.max(180, $('preview-area').clientHeight - 58);
    const scale = Math.min(1.25, available / dimensions.width, availableHeight / dimensions.height) * state.zoom;
    state.scale = scale;
    const canvas = document.createElement('canvas');
    const pixelRatio = Math.min(2, window.devicePixelRatio || 1);
    await renderPage(page, canvas, scale * pixelRatio);
    if (version !== state.previewId) return;
    const target = $('pdf-canvas'); target.width = canvas.width; target.height = canvas.height;
    target.style.width = `${dimensions.width * scale}px`; target.style.height = `${dimensions.height * scale}px`;
    target.getContext('2d').drawImage(canvas, 0, 0);
    $('paper').hidden = false; $('empty-preview').hidden = true;
    $('zoom-label').textContent = `${Math.round(state.zoom * 100)}%`;
    $('preview-status').textContent = state.stamp ? 'Sello aplicado' : 'Documento original';
    $('drag-hint').textContent = state.stamp ? 'Arrastra el sello. También puedes usar las flechas del teclado.' : 'Elige una imagen para colocar tu sello.';
    updateHandle();
  } catch (error) {
    if (version === state.previewId) { $('preview-status').textContent = 'Revisa los ajustes'; $('stamp-handle').hidden = true; message(friendly(error), 'error'); }
  } finally {
    await renderedDoc?.loadingTask.destroy(); previewRunning = false; updateControls();
    if (previewQueued && !state.busy) drainPreview();
  }
}
function updateHandle() {
  if (!state.stamp || !state.original || state.busy) { $('stamp-handle').hidden = true; return; }
  const opts = options(), width = opts.width * MM, height = width * state.stamp.height / state.stamp.width;
  const handle = $('stamp-handle');
  Object.assign(handle.style, { width: `${width * state.scale}px`, height: `${height * state.scale}px`,
    left: `${(state.pageWidth - (opts.right * MM) - width) * state.scale}px`, top: `${opts.top * MM * state.scale}px` });
  handle.hidden = false;
}

async function refreshLibrary(selected = '') {
  try {
    state.saved = (await listStamps()).sort((a, b) => a.name.localeCompare(b.name, 'es'));
    $('saved-stamps').replaceChildren(new Option('Elegir sello guardado', ''), ...state.saved.map(s => new Option(s.name, s.id)));
    $('saved-stamps').value = selected; updateControls();
  } catch (error) { message(friendly(error), 'error'); }
}
function setOptions(opts) { for (const key of ['width', 'top', 'right', 'layer']) $(key).value = opts[key]; updateLayerHelp(); }
function updateLayerHelp() {
  $('layer-help').textContent = {
    foreground: 'El sello aparece sobre el contenido del PDF.',
    background: 'Los fondos opacos o las imágenes pueden ocultar el sello.',
    middle: 'Sobre los gráficos, debajo del texto. En escaneos, las letras son parte de la imagen. Se comprueba que la separación conserve el aspecto original.',
  }[$('layer').value];
}
function csv(rows) {
  const escape = value => '"' + (/^[\s]*[=+@-]/.test(String(value)) ? "'" : '') + String(value).replaceAll('"', '""') + '"';
  return '\ufeff' + [['Archivo', 'Estado', 'Páginas', 'Detalle'], ...rows].map(row => row.map(escape).join(';')).join('\r\n');
}
function zipAsync(files) { return new Promise((resolve, reject) => zip(files, { level: 1 }, (error, data) => error ? reject(error) : resolve(data))); }
function resultName(file, used) {
  const base = file.name.replace(/\.pdf$/i, '').replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_') || 'documento';
  let name = `${base}_sellado.pdf`, i = 2;
  while (used.has(name.toLowerCase())) name = `${base}_sellado (${i++}).pdf`;
  used.add(name.toLowerCase()); return name;
}
async function exportFiles() {
  if (state.busy || !state.files.length || !state.stamp) return;
  let opts;
  try { opts = options(); } catch (error) { message(friendly(error), 'error'); return; }
  const run = ++state.run; ++state.previewId; clearTimeout(previewTimer); previewQueued = false;
  setBusy(true); clearResults(); $('cancel').hidden = false; $('progress').hidden = false; $('progress').max = state.files.length; $('progress').value = 0;
  const stamp = state.stamp, archive = {}, used = new Set(), rows = [], success = [];
  let outputBytes = 0;
  try {
    for (let i = 0; i < state.files.length; i++) {
      const file = state.files[i];
      if (run !== state.run) return;
      message(`Sellando ${i + 1} de ${state.files.length}: ${file.name}`);
      $('export-hint').textContent = `Procesando documento ${i + 1} de ${state.files.length}…`;
      try {
        const response = await request({ pdf: new Uint8Array(await file.arrayBuffer()), rgba: stamp.rgba, width: stamp.width, height: stamp.height, options: opts });
        if (run !== state.run) return;
        await validateMiddle(response.source, response.check, (page, total) => { $('export-hint').textContent = `Comprobando capas: página ${page} de ${total}…`; });
        if (run !== state.run) return;
        outputBytes += response.pdf.length;
        if (outputBytes > 200 * 1024 ** 2) throw new Error('Los resultados superan 200 MB. Procesa menos documentos a la vez.');
        const name = resultName(file, used); archive[name] = response.pdf;
        success.push(name); rows.push([file.name, 'Sellado', response.pages, '']);
      } catch (error) {
        if (run !== state.run) return;
        rows.push([file.name, 'Error', '', friendly(error)]);
      }
      $('progress').value = i + 1;
    }
    if (run !== state.run) return;
    const failed = rows.filter(row => row[1] === 'Error');
    $('results').hidden = false;
    $('results-title').textContent = success.length ? 'Tus archivos están listos' : 'No se pudieron sellar los documentos';
    $('result-count').textContent = `${success.length} correcto${success.length !== 1 ? 's' : ''} · ${failed.length} con error`;
    if (state.files.length === 1 && success.length) {
      const name = success[0]; addDownload(new Blob([archive[name]], { type: 'application/pdf' }), name, `Descargar ${name}`).click();
    } else if (success.length) {
      $('export-hint').textContent = 'Preparando la carpeta de resultados…';
      archive['informe.csv'] = strToU8(csv(rows));
      const zipped = await zipAsync(archive);
      if (run !== state.run) return;
      addDownload(new Blob([zipped], { type: 'application/zip' }), 'PDF-sellados.zip', 'Descargar todos en ZIP').click();
    }
    if (rows.length > 1 || failed.length) addDownload(new Blob([csv(rows)], { type: 'text/csv;charset=utf-8' }), 'informe.csv', 'Descargar informe');
    for (const row of failed) { const p = document.createElement('p'); p.className = 'failed'; p.textContent = `${row[0]}: ${row[3]}`; $('result-links').append(p); }
    message(success.length ? `${success.length} PDF sellado${success.length !== 1 ? 's' : ''}. Tus originales se conservaron.${failed.length ? ' Revisa los errores del informe.' : ''}` : 'No se generaron PDF. Revisa los errores indicados debajo.', failed.length ? 'error' : 'success');
  } catch (error) { message(friendly(error), 'error'); }
  finally {
    if (run === state.run) { setBusy(false); $('cancel').hidden = true; $('progress').hidden = true; schedulePreview(); }
  }
}

$('choose-pdfs').onclick = $('empty-choose').onclick = () => $('pdf-input').click();
$('choose-folder').onclick = () => $('folder-input').click();
$('pdf-input').onchange = event => { selectFiles(event.target.files); event.target.value = ''; };
$('folder-input').onchange = event => { selectFiles(event.target.files, true); event.target.value = ''; };
$('file-list').onchange = () => openDocument(Number($('file-list').value));
$('choose-image').onclick = () => $('image-input').click();
$('image-input').onchange = event => { chooseImage(event.target.files[0]); event.target.value = ''; };
for (const id of ['width', 'top', 'right', 'layer']) $(id).addEventListener('input', () => { updateLayerHelp(); schedulePreview(); });
$('reset-position').onclick = () => { $('width').value = 35; $('top').value = 10; $('right').value = 10; schedulePreview(); };
$('previous').onclick = () => { if (state.page > 1) { --state.page; updateControls(); schedulePreview(0); } };
$('next').onclick = () => { if (state.page < state.original.numPages) { ++state.page; updateControls(); schedulePreview(0); } };
function zoom(value) { state.zoom = Math.max(.25, Math.min(3, value)); schedulePreview(0); }
$('zoom-in').onclick = () => zoom(state.zoom + .25); $('zoom-out').onclick = () => zoom(state.zoom - .25); $('fit').onclick = () => zoom(1);
$('preview-area').addEventListener('wheel', event => { if (event.ctrlKey && state.original && !state.busy) { event.preventDefault(); zoom(state.zoom + (event.deltaY < 0 ? .1 : -.1)); } }, { passive: false });
window.addEventListener('resize', () => schedulePreview(300));
$('export').onclick = exportFiles;
$('cancel').onclick = () => { ++state.run; ++state.previewId; terminateWorker(); setBusy(false); $('cancel').hidden = true; $('progress').hidden = true; clearResults(); message('Proceso cancelado. Los originales no se modificaron.'); };

const area = $('preview-area');
area.addEventListener('dragover', event => { event.preventDefault(); if (!state.busy) area.classList.add('dragover'); });
area.addEventListener('dragleave', () => area.classList.remove('dragover'));
area.addEventListener('drop', event => { event.preventDefault(); area.classList.remove('dragover'); if (!state.busy) selectFiles(event.dataTransfer.files); });
window.addEventListener('dragover', event => event.preventDefault()); window.addEventListener('drop', event => event.preventDefault());

let drag;
const handle = $('stamp-handle');
handle.addEventListener('pointerdown', event => {
  if (state.busy || !state.stamp) return;
  event.preventDefault(); handle.focus(); handle.setPointerCapture(event.pointerId);
  drag = { x: event.clientX, y: event.clientY, ...options() }; handle.classList.add('dragging');
});
handle.addEventListener('pointermove', event => {
  if (!drag) return;
  const maxRight = Math.max(0, state.pageWidth / MM - drag.width);
  const maxTop = Math.max(0, state.pageHeight / MM - drag.width * state.stamp.height / state.stamp.width);
  $('right').value = Math.max(0, Math.min(maxRight, drag.right - (event.clientX - drag.x) / state.scale / MM)).toFixed(2);
  $('top').value = Math.max(0, Math.min(maxTop, drag.top + (event.clientY - drag.y) / state.scale / MM)).toFixed(2);
  updateHandle();
});
function finishDrag(cancel = false) { if (!drag) return; if (cancel) { $('right').value = drag.right; $('top').value = drag.top; } drag = null; handle.classList.remove('dragging'); schedulePreview(0); }
handle.addEventListener('pointerup', () => finishDrag()); handle.addEventListener('pointercancel', () => finishDrag(true));
handle.addEventListener('keydown', event => {
  if (event.key === 'Escape') { finishDrag(true); return; }
  if (state.busy || !['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) return;
  event.preventDefault(); const step = event.shiftKey ? 5 : 1, opts = options();
  const top = opts.top + (event.key === 'ArrowDown' ? step : event.key === 'ArrowUp' ? -step : 0);
  const right = opts.right + (event.key === 'ArrowLeft' ? step : event.key === 'ArrowRight' ? -step : 0);
  $('top').value = Math.max(0, Math.min(state.pageHeight / MM - opts.width * state.stamp.height / state.stamp.width, top)).toFixed(2);
  $('right').value = Math.max(0, Math.min(state.pageWidth / MM - opts.width, right)).toFixed(2);
  schedulePreview(200);
});
$('save-stamp').onclick = () => { $('save-error').textContent = ''; $('save-name').value = state.stamp.name.replace(/\.[^.]+$/, ''); $('save-dialog').showModal(); $('save-name').focus(); };
$('confirm-save').onclick = async event => {
  event.preventDefault(); const name = $('save-name').value.trim();
  if (!name || name.length > 80) { $('save-error').textContent = 'Escribe un nombre de hasta 80 caracteres.'; return; }
  try {
    const opts = options(); const existing = state.saved.find(s => s.name.toLocaleLowerCase() === name.toLocaleLowerCase());
    if (existing && !confirm(`Ya existe «${name}». ¿Reemplazar su imagen y ajustes?`)) return;
    const id = existing?.id || crypto.randomUUID();
    await putStamp({ id, name, blob: state.stamp.blob, options: opts });
    await refreshLibrary(id); $('save-dialog').close(); message('Sello guardado en este navegador.', 'success');
  } catch (error) { $('save-error').textContent = friendly(error); }
};
$('saved-stamps').onchange = async () => {
  updateControls(); const saved = state.saved.find(s => s.id === $('saved-stamps').value); if (!saved) return;
  try { const stamp = await normalizeImage(saved.blob, saved.name); setOptions(saved.options); showStamp(stamp); message(`Sello «${saved.name}» cargado con sus ajustes.`); }
  catch (error) { message(friendly(error), 'error'); }
};
$('delete-stamp').onclick = async () => {
  const saved = state.saved.find(s => s.id === $('saved-stamps').value);
  if (!saved || !confirm(`¿Eliminar «${saved.name}» de este navegador? La imagen original se conserva.`)) return;
  try { await removeStamp(saved.id); await refreshLibrary(); message('Sello eliminado de la biblioteca.'); } catch (error) { message(friendly(error), 'error'); }
};
refreshLibrary(); updateControls();
