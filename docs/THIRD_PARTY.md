# Componentes de Sello PDF Web

Las bibliotecas se sirven desde este mismo sitio, con versiones fijadas. Los documentos del usuario no se envían a sus proveedores.

| Componente | Versión | Uso | Licencia y fuente |
| --- | --- | --- | --- |
| PDF.js | 6.5.438 | Vista previa y comparación de capas | [Apache-2.0](vendor/LICENSE-PDFJS), [fuente](https://github.com/mozilla/pdf.js) |
| Pyodide | 314.0.8 | Python dentro de un Web Worker | [MPL-2.0](vendor/LICENSE-PYODIDE), [fuente de esta versión](https://github.com/pyodide/pyodide/tree/314.0.8) |
| pypdf | 6.21.4 | Modificación vectorial de los documentos | [BSD-3-Clause](vendor/LICENSE-PYPDF), [fuente](https://github.com/py-pdf/pypdf/tree/6.21.4) |
| fflate | 0.8.3 | ZIP de resultados e informe | [MIT](vendor/LICENSE-FFLATE), [fuente](https://github.com/101arrowz/fflate) |

Los recursos de fuentes y los decodificadores de PDF.js incluyen sus avisos de licencia en `vendor/standard_fonts` y `vendor/wasm`. Pyodide incluye CPython y componentes de su distribución oficial, sin modificaciones al runtime. El motor propio está en `engine.py`; el resto del código de la aplicación está en este repositorio.
