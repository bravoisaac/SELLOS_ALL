import { loadPyodide } from './vendor/pyodide/pyodide.mjs';

let runtime;
async function initialize() {
  if (!runtime) runtime = (async () => {
    postMessage({ type: 'status', message: 'Preparando el motor local de PDF…' });
    const py = await loadPyodide({ indexURL: new URL('./vendor/pyodide/', import.meta.url).href });
    const wheel = await fetch(new URL('./vendor/pypdf.whl', import.meta.url));
    if (!wheel.ok) throw new Error('No se pudo descargar el motor PDF. Recarga la página.');
    py.unpackArchive(await wheel.arrayBuffer(), 'zip', { extractDir: '/home/pyodide/lib' });
    py.runPython("import sys; sys.path.insert(0, '/home/pyodide/lib')");
    const source = await fetch(new URL('./engine.py', import.meta.url));
    if (!source.ok) throw new Error('No se pudo cargar el motor PDF.');
    await py.runPythonAsync(await source.text());
    return py;
  })().catch(error => { runtime = null; throw error; });
  return runtime;
}

let queue = Promise.resolve();
onmessage = ({ data }) => {
  queue = queue.then(async () => {
    try {
      const py = await initialize();
      if (data.type === 'init') { postMessage({ id: data.id, ready: true }); return; }
      const pdf = py.toPy(data.pdf);
      const pixels = py.toPy(data.rgba);
      let result;
      try {
        const process = py.globals.get('process');
        try { result = process(pdf, pixels, data.width, data.height, JSON.stringify(data.options), data.pageIndex ?? -1); }
        finally { process.destroy(); }
        const output = result.toJs({ dict_converter: Object.fromEntries });
        const pdfOut = Uint8Array.from(output.pdf);
        const check = Uint8Array.from(output.check);
        const source = Uint8Array.from(output.source);
        postMessage({ id: data.id, pdf: pdfOut, check, source, pages: output.pages }, [pdfOut.buffer, check.buffer, source.buffer]);
      } finally { pdf.destroy(); pixels.destroy(); result?.destroy(); }
    } catch (error) {
      const raw = String(error.message || error).split('\n').filter(Boolean).at(-1);
      const message = /PdfReadError|PdfStreamError|EmptyFileError|EOF/i.test(raw)
        ? 'El PDF está dañado o incompleto. Usa otra copia del documento.'
        : raw.replace(/^(?:[\w.]+\.)?ValueError:\s*/, '');
      postMessage({ id: data.id, error: message });
    }
  });
};
