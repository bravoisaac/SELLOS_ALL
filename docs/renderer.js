import * as pdfjs from './vendor/pdf.min.mjs';

pdfjs.GlobalWorkerOptions.workerSrc = new URL('./vendor/pdf.worker.min.mjs', import.meta.url).href;
export const MM = 72 / 25.4;
const asset = name => new URL(`./vendor/${name}/`, import.meta.url).href;

export async function loadPDF(bytes) {
  const task = pdfjs.getDocument({
    data: bytes.slice(), cMapUrl: asset('cmaps'), cMapPacked: true,
    standardFontDataUrl: asset('standard_fonts'), wasmUrl: asset('wasm'),
    isEvalSupported: false, stopAtErrors: true,
  });
  try { return await task.promise; }
  catch (error) { await task.destroy(); throw error; }
}

export async function renderPage(page, canvas, scale, annotations = true) {
  const viewport = page.getViewport({ scale });
  canvas.width = Math.ceil(viewport.width);
  canvas.height = Math.ceil(viewport.height);
  await page.render({ canvasContext: canvas.getContext('2d', { willReadFrequently: true }), viewport,
    annotationMode: annotations ? pdfjs.AnnotationMode.ENABLE : pdfjs.AnnotationMode.DISABLE }).promise;
}

export async function validateMiddle(source, check, onProgress = () => {}) {
  if (!check.length) return;
  let before, after;
  try {
    before = await loadPDF(source);
    after = await loadPDF(check);
    if (before.numPages !== after.numPages) throw new Error('No se pudieron comprobar las capas del PDF.');
    const left = document.createElement('canvas'), right = document.createElement('canvas');
    for (let i = 1; i <= before.numPages; i++) {
      onProgress(i, before.numPages);
      const page = await before.getPage(i), recombined = await after.getPage(i);
      const view = page.getViewport({ scale: 1 });
      const scale = Math.min(1.5, 1400 / Math.max(view.width, view.height));
      await renderPage(page, left, scale, false);
      await renderPage(recombined, right, scale, false);
      if (left.width !== right.width || left.height !== right.height) throw new Error('Las capas cambian el tamaño de la página.');
      const a = left.getContext('2d').getImageData(0, 0, left.width, left.height).data;
      const b = right.getContext('2d').getImageData(0, 0, right.width, right.height).data;
      let different = 0;
      for (let j = 0; j < a.length; j += 4) {
        if (Math.max(Math.abs(a[j] - b[j]), Math.abs(a[j + 1] - b[j + 1]), Math.abs(a[j + 2] - b[j + 2])) > 21 && ++different > 3) {
          throw new Error(`Página ${i}: separar las capas cambiaría el aspecto del PDF. Elige Al fondo o Delante del texto.`);
        }
      }
      page.cleanup(); recombined.cleanup();
    }
    left.width = right.width = 0;
  } finally { await before?.loadingTask.destroy(); await after?.loadingTask.destroy(); }
}
