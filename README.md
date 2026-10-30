# Sello PDF

Aplicación de escritorio para Windows de 64 bits. Agrega una imagen en la esquina superior derecha visible de **todas las páginas** de un PDF, detrás del texto y del contenido original. Funciona localmente, sin subir documentos a internet.

## Descargar para Windows

- **[Descargar SelloPDF.exe](dist/SelloPDF.exe)** — ejecutable portable para Windows de 64 bits.
- **[Descargar paquete ZIP](SelloPDF-Windows-x64.zip)** — aplicación, instrucciones y código fuente.

No requiere instalación, Python ni conexión a internet para funcionar. Si descargas el ZIP, extrae todo su contenido y abre `dist/SelloPDF.exe` con doble clic.

Estos enlaces apuntan a los archivos incluidos en esta entrega local. Para ofrecer descargas públicas, publica el ejecutable o el ZIP en un servicio de alojamiento y reemplaza los enlaces por sus direcciones de descarga.

## Qué permite hacer

- Sellar un PDF o todos los PDF de una carpeta con la misma imagen.
- Colocar el sello arriba a la derecha, **detrás del texto**.
- Ajustar ancho y márgenes en milímetros y revisar la vista previa.
- Guardar copias sin modificar los originales.
- Continuar ante errores individuales y generar un informe al procesar carpetas.

## Uso

1. Abre `dist/SelloPDF.exe` con doble clic. No necesita Python instalado.
2. Pulsa **Un PDF…** y elige el documento.
3. Pulsa **Seleccionar imagen del sello**. Admite PNG, JPG, WEBP, BMP y TIFF.
4. Ajusta el ancho y los márgenes superior y derecho en milímetros. Por defecto usa un ancho de 35 mm y márgenes de 10 mm. La altura conserva la proporción de la imagen.
5. Revisa las páginas con las flechas de la vista previa.
6. Pulsa **Guardar PDF sellado**, elige otro nombre y abre el resultado al terminar.

El original se conserva. El texto se dibuja por encima del sello, también en la vista previa y al sellar carpetas. En PDF escaneados o con un fondo opaco, ese fondo puede ocultar el sello situado detrás; revisa la vista previa. Para evitar un rectángulo de fondo en la propia imagen del sello, utiliza PNG con transparencia. Los bordes vacíos de la imagen forman parte de su tamaño; recórtalos antes si necesitas un ajuste preciso.

Si el sello no cabe en alguna página, el proceso se detiene y permite ajustar las medidas. Los PDF que requieren contraseña o no permiten modificaciones deben abrirse previamente como una copia autorizada sin esas restricciones. Modificar un PDF con firma digital puede invalidar esa firma; este programa coloca una imagen, no una firma digital.

## Sellar una carpeta completa

1. Pulsa **Carpeta de PDF…** y selecciona la carpeta de origen.
2. Selecciona una imagen del sello y ajusta el tamaño y los márgenes.
3. Usa el selector sobre la vista previa para revisar cualquiera de los PDF.
4. Pulsa **Sellar toda la carpeta**. Se procesan todas las páginas de cada PDF directamente contenido en la carpeta, incluidas extensiones `.PDF` en mayúsculas. No se incluyen subcarpetas.
5. Abre la carpeta de resultados desde el resumen final. Las copias conservan sus nombres y se guardan en `Sellados` dentro de la carpeta original. Si ya existe, se crea `Sellados (2)`, `Sellados (3)`, etc.

Un PDF dañado, protegido o demasiado pequeño para el sello no detiene el resto. El resumen muestra los fallos y `informe.csv` detalla los archivos sellados, sus páginas y los errores. Los resultados de ejecuciones anteriores no se sobrescriben ni se vuelven a procesar automáticamente.

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
- `stamping.py`: validación, geometría y guardado mediante archivo temporal y reemplazo atómico.
- `tests/test_stamping.py`: páginas rotadas 0/90/180/270 grados, recorte, transparencia, JPEG, medidas inválidas, archivos protegidos, preservación de originales y coincidencia de vista previa con salida.
- `tests/test_batch.py`: carpetas con varios PDF, errores parciales, informes, exclusión de subcarpetas y conservación de resultados anteriores.
- `tests/gui_smoke.py`: integración de selección de carpeta, vista previa, proceso de lote, resumen y regreso al modo individual; requiere escritorio Windows disponible.
- `MAPA.md`: conexiones y alcance del proyecto.

La inserción usa las coordenadas de página descritas en la [documentación oficial de PyMuPDF](https://pymupdf.readthedocs.io/en/latest/page.html). Se conserva el documento PDF; sus páginas no se convierten en capturas de pantalla.

PyMuPDF/MuPDF se distribuye bajo AGPL o licencia comercial. Consulta sus condiciones antes de redistribuir una versión cerrada de la aplicación.
