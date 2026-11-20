# Sello PDF Web

**[Abrir la aplicación web](https://bravoisaac.github.io/SELLOS_ALL/)**

Agrega tu sello a todas las páginas de uno o varios PDF directamente desde el navegador. Usa Chrome, Edge o Firefox actualizado. La interfaz se adapta a escritorio y móvil.

## Cómo usarla

1. Abre la aplicación y pulsa **Elegir PDF**, o selecciona una carpeta.
2. Elige la imagen de tu sello o selecciona uno de **Mis sellos**.
3. Ajusta el ancho y los márgenes en milímetros. También puedes arrastrar el sello en la vista previa y cambiar de página o usar el zoom.
4. Elige la capa: **Delante del texto**, **Al medio · debajo del texto** o **Al fondo**.
5. Pulsa el botón de guardar el resultado. Se genera una copia de cada documento y se conservan los originales. Para varios PDF, la aplicación reúne los resultados y un informe de errores en un ZIP.

## Privacidad y sellos guardados

Los PDF y las imágenes se procesan en la memoria de tu navegador, sin enviarlos a un servidor. El sitio solo solicita sus propios archivos de aplicación; no usa servicios de análisis ni fuentes externas.

**Mis sellos** guarda la imagen y sus ajustes en este navegador mediante IndexedDB. No se sincronizan entre equipos. Borrar los datos del sitio elimina esa biblioteca; en navegación privada puede desaparecer al cerrar la sesión.

## Funciones y límites

- PNG, JPG, WEBP y BMP como imágenes de sello; PNG permite conservar la transparencia.
- PDF individual o grupos de hasta 100 archivos: máximo 50 MB por archivo y 150 MB en total. Las carpetas no incluyen subcarpetas.
- Vista previa con zoom, arrastre y movimiento del sello con las flechas del teclado.
- Texto seleccionable, rotación de páginas, recortes, formularios y enlaces conservados en las pruebas.
- La capa intermedia comprueba visualmente que separar texto y gráficos no cambie el aspecto original. Si el PDF no admite esa separación, muestra un error y permite elegir otra capa.
- En un escaneo, las letras son parte de una imagen y no se pueden separar como texto.
- Se rechazan documentos cifrados o protegidos; utiliza una copia autorizada sin restricciones.
- Una imagen de sello no es una firma digital. Modificar un PDF firmado puede invalidar su firma.

La primera operación puede tardar mientras se carga el motor local. El tiempo de procesamiento depende del tamaño de los documentos y de la memoria disponible. El botón **Cancelar proceso** permite detener el sellado.

## Desarrollo y publicación

GitHub Pages publica únicamente la carpeta `docs/` de la rama `main`. El código de escritorio se conserva como referencia histórica y no forma parte del sitio web.

```powershell
npm ci --ignore-scripts
npm run vendor
npm run check
npm run serve
```

La vista local se abre en `http://127.0.0.1:4173`. Las versiones de las bibliotecas están fijadas en `package-lock.json`; el paquete de pypdf también se comprueba por SHA-256. Consulta los [componentes y licencias](docs/THIRD_PARTY.md).

- `docs/index.html`, `styles.css`, `app.js`: interfaz y flujo de trabajo.
- `docs/renderer.js`: vista previa y comprobación visual de la capa intermedia.
- `docs/pdf-worker.js`, `engine.py`: motor de procesamiento aislado de la interfaz.
- `docs/library.js`: biblioteca local de sellos.
- `scripts/prepare-web.mjs`: preparación reproducible de las dependencias del sitio.
- `tests/test_web_engine.py`: geometría, capas, transparencia, protección y preservación del documento.
