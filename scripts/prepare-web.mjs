import { mkdir, copyFile, cp, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { unzipSync } from 'fflate';

const out = new URL('../docs/vendor/', import.meta.url);
await mkdir(out, { recursive: true });
for (const name of ['pdf.min.mjs', 'pdf.worker.min.mjs', 'pdf.renderer.min.mjs']) {
  await copyFile(new URL(`../node_modules/pdfjs-dist/build/${name}`, import.meta.url), new URL(name, out));
}
for (const folder of ['cmaps', 'standard_fonts', 'wasm']) {
  await cp(new URL(`../node_modules/pdfjs-dist/${folder}`, import.meta.url), new URL(folder, out), { recursive: true });
}
await copyFile(new URL('../node_modules/fflate/esm/browser.js', import.meta.url), new URL('fflate.mjs', out));
await mkdir(new URL('pyodide/', out), { recursive: true });
for (const name of ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json']) {
  await copyFile(new URL(`../node_modules/pyodide/${name}`, import.meta.url), new URL(`pyodide/${name}`, out));
}
const wheelUrl = 'https://files.pythonhosted.org/packages/3f/4b/77e8ad4ac42c9d93600f40541a50e9feb3a61d2bbee2d76f659346072051/pypdf-6.21.4-py3-none-any.whl';
const response = await fetch(wheelUrl);
if (!response.ok) throw new Error(`pypdf: HTTP ${response.status}`);
const wheel = Buffer.from(await response.arrayBuffer());
if (createHash('sha256').update(wheel).digest('hex') !== '33e4fb41ca352810eb4e9838aa0d82d6888a5f8bf682f43e99cce5faa666255c') throw new Error('Hash de pypdf incorrecto.');
await writeFile(new URL('pypdf.whl', out), wheel);
const wheelFiles = unzipSync(wheel);
const license = Object.keys(wheelFiles).find(name => name.endsWith('/licenses/LICENSE'));
if (!license) throw new Error('Falta la licencia de pypdf.');
await writeFile(new URL('LICENSE-PYPDF', out), wheelFiles[license]);
const pyodideLicense = await fetch('https://raw.githubusercontent.com/pyodide/pyodide/314.0.8/LICENSE');
if (!pyodideLicense.ok) throw new Error('No se pudo obtener la licencia de Pyodide.');
await writeFile(new URL('LICENSE-PYODIDE', out), await pyodideLicense.text());
await copyFile(new URL('../node_modules/pdfjs-dist/LICENSE', import.meta.url), new URL('LICENSE-PDFJS', out));
await copyFile(new URL('../node_modules/fflate/LICENSE', import.meta.url), new URL('LICENSE-FFLATE', out));
await writeFile(new URL('../docs/.nojekyll', import.meta.url), '');
console.log('Dependencias web locales preparadas; pypdf verificado por SHA-256.');
