# Sello PDF

Aplicación de escritorio para Windows de 64 bits. Agrega una imagen en **todas las páginas** de un PDF y permite elegir si queda al fondo, al medio o delante del texto. El sello comienza arriba a la derecha y puedes moverlo con el mouse en la vista previa. Funciona localmente, sin subir documentos a internet.

## Descargar la versión actualizada

**Última actualización: 29 de octubre de 2026.** Esta entrega incluye el selector de capas **Al fondo / Al medio / Delante del texto**, el movimiento del sello con el mouse, zoom y sellado de carpetas completas.

- **[Descargar el ejecutable actualizado — SelloPDF.exe](dist/SelloPDF.exe)** — aplicación portable para Windows de 64 bits.
- **[Descargar el ZIP actualizado](SelloPDF-Windows-x64.zip)** — el mismo ejecutable, este README y el código fuente de esta entrega.

No requiere instalación, Python ni conexión a internet para funcionar. Si descargas el ZIP, extrae todo su contenido y abre `dist/SelloPDF.exe` con doble clic.

Si tienes una versión anterior abierta, ciérrala y abre el ejecutable de esta entrega. Para reconocer la versión actual, comprueba que aparezca el selector **Capa del sello** con las tres opciones, además de los controles **+**, **−** y **Ajustar** en la vista previa.

Estos enlaces apuntan a los archivos incluidos en esta entrega local. Para ofrecer descargas públicas, publica el ejecutable o el ZIP en un servicio de alojamiento y reemplaza los enlaces por sus direcciones de descarga.

## Qué permite hacer

- Sellar un PDF o todos los PDF de una carpeta con la misma imagen.
- Arrastrar el sello a la posición deseada y elegir su capa: **al fondo, al medio o delante del texto**.
- Ajustar ancho y márgenes en milímetros y ampliar la vista previa con zoom.
- Guardar copias sin modificar los originales.
- Continuar ante errores individuales y generar un informe al procesar carpetas.

## Uso

1. Abre `dist/SelloPDF.exe` con doble clic. No necesita Python instalado.
2. Pulsa **Un PDF…** y elige el documento.
3. Pulsa **Seleccionar imagen del sello**. Admite PNG, JPG, WEBP, BMP y TIFF.
4. Ajusta el ancho y los márgenes superior y derecho en milímetros. Por defecto usa un ancho de 35 mm y márgenes de 10 mm. La altura conserva la proporción de la imagen.
5. Arrastra el sello en la vista previa y revisa las páginas con las flechas. Usa **+**, **−** o **Ctrl + rueda del mouse** para ampliar o reducir.
6. Elige **Capa del sello**: Al fondo, Al medio (debajo del texto) o Delante del texto.
7. Pulsa **Guardar PDF sellado**, elige otro nombre y abre el resultado al terminar.

El original se conserva. La vista previa refleja la capa elegida, también al sellar carpetas. Para evitar un rectángulo de fondo en la propia imagen del sello, utiliza PNG con transparencia. Los bordes vacíos de la imagen forman parte de su tamaño; recórtalos antes si necesitas un ajuste preciso.

Si el sello no cabe en alguna página, el proceso se detiene y permite ajustar las medidas. Los PDF que requieren contraseña o no permiten modificaciones deben abrirse previamente como una copia autorizada sin esas restricciones. Modificar un PDF con firma digital puede invalidar esa firma; este programa coloca una imagen, no una firma digital.

## Sellar una carpeta completa

1. Pulsa **Carpeta de PDF…** y selecciona la carpeta de origen.
2. Selecciona una imagen del sello y ajusta el tamaño y los márgenes.
3. Usa el selector sobre la vista previa para revisar cualquiera de los PDF.
4. Pulsa **Sellar toda la carpeta**. Se procesan todas las páginas de cada PDF directamente contenido en la carpeta, incluidas extensiones `.PDF` en mayúsculas. No se incluyen subcarpetas.
5. Abre la carpeta de resultados desde el resumen final. Las copias conservan sus nombres y se guardan en `Sellados` dentro de la carpeta original. Si ya existe, se crea `Sellados (2)`, `Sellados (3)`, etc.

Un PDF dañado, protegido o demasiado pequeño para el sello no detiene el resto. El resumen muestra los fallos y `informe.csv` detalla los archivos sellados, sus páginas y los errores. Los resultados de ejecuciones anteriores no se sobrescriben ni se vuelven a procesar automáticamente.

## Mover el sello y usar el zoom

- Haz clic dentro del marco azul del sello, mantén presionado el botón izquierdo y arrástralo. Al soltarlo, se actualizan los márgenes superior y derecho. **Esc** cancela el arrastre.
- El sello se mantiene dentro de la página. El marco azul es una ayuda de edición y no aparece en el PDF guardado.
- Los botones **+** y **−**, o **Ctrl + rueda**, permiten cambiar el zoom entre 25 % y 300 %. **Ajustar** muestra la página completa.
- Usa la rueda para desplazarte verticalmente, **Shift + rueda** para desplazarte horizontalmente, o las barras de desplazamiento.
- El zoom solo cambia la visualización; el tamaño del sello en el archivo final sigue siendo el ancho en milímetros.
- La posición elegida se aplica a todas las páginas y a todos los PDF de la carpeta, conservando las distancias a los bordes superior y derecho. Si hay tamaños de página distintos, revisa su vista previa; un sello que no quepa se informa como error.

## Elegir la capa del sello

| Opción | Resultado |
| --- | --- |
| **Al fondo** | Debajo del contenido original. Un fondo opaco o una imagen de página completa puede ocultar el sello. |
| **Al medio (debajo del texto)** | Encima de imágenes y gráficos, debajo del texto PDF. Se conservan las fuentes y el texto seleccionable. |
| **Delante del texto** | Encima del contenido de la página. Una imagen de sello opaca puede cubrir las letras. |

La capa seleccionada se conserva al arrastrar y se aplica a todas las páginas del PDF o de la carpeta. Las anotaciones y campos interactivos del documento se conservan y siguen siendo objetos independientes del contenido de página.

En un documento escaneado, las letras forman parte de la imagen: la opción intermedia no puede separarlas de esa imagen. Si un PDF usa texto como máscara o sus capas no se pueden separar sin cambiar el aspecto original, el modo intermedio muestra un error; usa Al fondo o Delante del texto para ese archivo. La aplicación no convierte las páginas en imágenes al exportar.

## Desarrollo

Requiere Python 3.12 de 64 bits con Tkinter en Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Pruebas y compilación:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tests/gui_smoke.py
.\build.ps1
```

`build.ps1 -Python 'C:\ruta\python.exe'` permite elegir el intérprete al crear el entorno. El resultado es un ejecutable portable en `dist/SelloPDF.exe`. No incluye instalador ni firma de código.

## Archivos y validación

- `app.py`: ventana, vista previa, navegación, progreso y selección de archivos.
- `preview.py`: zoom, desplazamiento, capas de vista previa y arrastre del sello.
- `stamping.py`: validación, geometría y guardado mediante archivo temporal y reemplazo atómico.
- `pdf_layers.py`: separación vectorial entre gráficos y texto para la capa intermedia, con verificación de apariencia.
- `tests/test_stamping.py`: páginas rotadas 0/90/180/270 grados, recorte, transparencia, JPEG, medidas inválidas, archivos protegidos, preservación de originales y coincidencia de vista previa con salida.
- `tests/test_batch.py`: carpetas con varios PDF, errores parciales, informes, exclusión de subcarpetas y conservación de resultados anteriores.
- `tests/test_preview.py`: conversión del arrastre, límites de página y coincidencia de las capas con la salida en páginas rotadas y recortadas.
- `tests/test_layers.py`: tres órdenes de capas, fondos de imagen, texto seleccionable, formularios gráficos anidados, enlaces, campos y documentos que no admiten separación.
- `tests/gui_smoke.py`: integración de selección de carpeta, vista previa, proceso de lote, resumen y regreso al modo individual; requiere escritorio Windows disponible.
- `MAPA.md`: conexiones y alcance del proyecto.

La inserción usa las coordenadas de página descritas en la [documentación oficial de PyMuPDF](https://pymupdf.readthedocs.io/en/latest/page.html). Se conserva el documento PDF; sus páginas no se convierten en capturas de pantalla.

La separación de instrucciones utiliza [ContentStream de pypdf](https://pypdf.readthedocs.io/en/6.9.0/modules/generic.html).

PyMuPDF/MuPDF se distribuye bajo AGPL o licencia comercial. Consulta sus condiciones antes de redistribuir una versión cerrada de la aplicación.
