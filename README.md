# Sello PDF

Aplicación de escritorio para Windows de 64 bits. Agrega una imagen en **todas las páginas** de un PDF y permite elegir si queda al fondo, al medio o delante del texto. El sello comienza arriba a la derecha y puedes moverlo con el mouse en la vista previa. Funciona localmente, sin subir documentos a internet.

## Descarga suspendida por detección de Defender

**No descargues, ejecutes ni distribuyas esta versión.** El 19 de noviembre de 2026, Microsoft Defender detectó `Trojan:Script/Ulthar.A!ml` en `SelloPDF-Windows-x64 (1).zip`, descargado desde la dirección pública de este repositorio. El historial local registra la acción de protección completada, amenaza no activa y sin ejecución registrada.

Se retiraron los enlaces de descarga. Los binarios que aún figuren entre los archivos o en el historial del repositorio no son una alternativa validada. No restaures copias bloqueadas ni desactives Defender ni añadas exclusiones para abrirlas.

Los análisis locales anteriores sin detecciones y las 41 pruebas funcionales **no descartan esta alerta**. Tampoco puede atribuirse a la falta de firma digital ni al archivo de instrucciones eliminado. La causa sigue sin confirmar; no se afirma que sea un falso positivo.

La revisión debe realizarse a través del [portal oficial de análisis de archivos de Microsoft](https://www.microsoft.com/en-us/wdsi/filesubmission). La entrega permanece suspendida hasta resolver la detección y volver a comprobar la distribución. No se ha enviado una muestra todavía.

Identificadores de los archivos publicados al suspender la descarga (solo para investigación, no para ejecutarlos):

- ZIP: SHA-256 `AEFC795066A8FDC632334A11F5CFE0C548E071736938E585C385C345625C93BE`.
- Ejecutable: SHA-256 `9B985D56ADC009EA0502C7B6CC16E74D86D7D884EF146C9B45349B5961CB5579`.

Estos hashes corresponden a las copias del proyecto; el historial consultado no proporciona el hash del ZIP bloqueado en Descargas.

### Compilación anterior retirada

La compilación anterior también fue retirada tras una detección `Trojan:Win32/Ulthar.A!ml`. Su SHA-256 es `E3687EC15C8846366545481DE1137A488DEBA16631FD41438CC552D40CF0D778`. No la ejecutes ni la restaures.

## Qué permite hacer

- Sellar un PDF o todos los PDF de una carpeta con la misma imagen.
- Arrastrar el sello a la posición deseada y elegir su capa: **al fondo, al medio o delante del texto**.
- Ajustar ancho y márgenes en milímetros y ampliar la vista previa con zoom.
- Guardar sellos con nombre, imagen, tamaño, márgenes y capa para reutilizarlos en otros documentos.
- Trabajar en ventanas amplias o compactas, con controles desplazables y el botón de guardar siempre visible.
- Guardar copias sin modificar los originales.
- Continuar ante errores individuales y generar un informe al procesar carpetas.

## Uso

Las instrucciones siguientes documentan las funciones de la aplicación. La distribución actual está suspendida: no ejecutes los binarios retirados.

1. Abre la versión validada de `SelloPDF.exe` con doble clic. No necesita Python instalado.
2. Pulsa **Un PDF…** y elige el documento.
3. Pulsa **Elegir imagen del sello** o elige uno guardado en **Mis sellos**. Admite PNG, JPG, WEBP, BMP y TIFF.
4. Ajusta el ancho y los márgenes superior y derecho en milímetros. Por defecto usa un ancho de 35 mm y márgenes de 10 mm. La altura conserva la proporción de la imagen.
5. Arrastra el sello en la vista previa y revisa las páginas con las flechas. Usa **+**, **−** o **Ctrl + rueda del mouse** para ampliar o reducir.
6. Elige **Capa del sello**: Al fondo, Al medio (debajo del texto) o Delante del texto.
7. Pulsa **Guardar PDF sellado**, elige otro nombre y abre el resultado al terminar.

El original se conserva. La vista previa refleja la capa elegida, también al sellar carpetas. Para evitar un rectángulo de fondo en la propia imagen del sello, utiliza PNG con transparencia. Los bordes vacíos de la imagen forman parte de su tamaño; recórtalos antes si necesitas un ajuste preciso.

Si el sello no cabe en alguna página, el proceso se detiene y permite ajustar las medidas. Los PDF que requieren contraseña o no permiten modificaciones deben abrirse previamente como una copia autorizada sin esas restricciones. Modificar un PDF con firma digital puede invalidar esa firma; este programa coloca una imagen, no una firma digital.

## Guardar y reutilizar sellos

1. En **Mis sellos**, pulsa **Elegir imagen del sello** y selecciona tu imagen.
2. Ajusta su ancho, márgenes y capa. Puedes guardarlo incluso sin tener un PDF abierto.
3. Pulsa **Guardar sello…**, escribe un nombre y confirma. La app guarda una copia de la imagen junto con sus ajustes.
4. Para usarlo en otro documento o después de cerrar y abrir la app, selecciónalo en la lista de **Mis sellos**. Puedes modificar sus ajustes para ese documento sin cambiar la copia guardada.
5. Para actualizar un sello, vuelve a guardarlo con el mismo nombre y confirma el reemplazo. **Eliminar…** pide confirmación y borra solo la copia de la biblioteca; conserva la imagen original y los PDF.

Los sellos se guardan en `%LOCALAPPDATA%\SelloPDF\sellos`, dentro de tu perfil de Windows. Seguirán disponibles aunque muevas la imagen original o actualices el ejecutable. Puedes respaldar esa carpeta; no se incluye dentro del `.exe` ni se sincroniza por internet.

## Ventanas pequeñas

La ventana admite tamaños desde **640 × 520 píxeles**. En ventanas amplias, los ajustes y el documento se muestran lado a lado. Al reducir el ancho aparecen las pestañas **Archivos y sellos** y **Vista previa**, que conservan tus selecciones al cambiar entre ellas.

Desplázate por los ajustes con la rueda o la barra lateral; al navegar con **Tab**, el control enfocado se hace visible. **Guardar PDF sellado** permanece en la parte inferior. En la vista previa puedes ampliar con **+** o **Ctrl + rueda**.

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
.\tests\release_checks.ps1
.\build.ps1
```

`build.ps1 -Python 'C:\ruta\python.exe'` requiere Python 3.12 de 64 bits y crea un entorno independiente en `build/release-<id>/venv`. Instala únicamente las ruedas oficiales fijadas por URL y SHA-256 en `requirements-windows.lock`, sin reutilizar la caché ni el entorno de desarrollo. El archivo de bloqueo incluye las dependencias transitivas del empaquetador; debe revisarse al actualizar `requirements.txt`.

La compilación requiere Defender activo y permisos para consultar sus detecciones. Analiza el entorno, comprueba las dependencias gráficas, ejecuta las pruebas del motor y de la interfaz, genera un candidato, analiza el ejecutable y comprueba su apertura y cierre. Cualquier fallo detiene el proceso y queda registrado en `build/release-<id>/validation.json`. No se desactiva ni modifica la protección.

El candidato permanece en `build/release-<id>/dist/SelloPDF.exe`; no se copia automáticamente a la raíz ni se publica. Un análisis sin detecciones no revoca el aviso anterior: antes de distribuirlo falta la revisión del proveedor y, donde corresponda, una firma de código aceptada. Los archivos antiguos en `dist/`, en la raíz o en el ZIP no se actualizan al fallar una compilación.

La distribución está suspendida por la nueva detección durante la descarga. Los informes de validación anteriores conservan su valor histórico, pero no autorizan republicar estos binarios. Resolver primero la detección con Microsoft; después revisar el resultado y validar nuevamente la entrega.

## Archivos y validación

- `app.py`: ventana, vista previa, navegación, progreso y selección de archivos.
- `preview.py`: zoom, desplazamiento, capas de vista previa y arrastre del sello.
- `ui_components.py`: panel de ajustes desplazable con acceso por rueda y teclado.
- `stamp_library.py`: biblioteca local de sellos, copias PNG con ajustes y reemplazo atómico.
- `stamping.py`: validación, geometría y guardado mediante archivo temporal y reemplazo atómico.
- `pdf_layers.py`: separación vectorial entre gráficos y texto para la capa intermedia, con verificación de apariencia.
- `tests/test_stamping.py`: páginas rotadas 0/90/180/270 grados, recorte, transparencia, JPEG, medidas inválidas, archivos protegidos, preservación de originales y coincidencia de vista previa con salida.
- `tests/test_batch.py`: carpetas con varios PDF, errores parciales, informes, exclusión de subcarpetas y conservación de resultados anteriores.
- `tests/test_preview.py`: conversión del arrastre, límites de página y coincidencia de las capas con la salida en páginas rotadas y recortadas.
- `tests/test_layers.py`: tres órdenes de capas, fondos de imagen, texto seleccionable, formularios gráficos anidados, enlaces, campos y documentos que no admiten separación.
- `tests/test_stamp_library.py`: persistencia, transparencia, reemplazo atómico, nombres duplicados, archivos dañados y conservación de originales.
- `tests/gui_smoke.py`: integración de selección de carpeta, vista previa, exportación, cuatro tamaños de ventana y reutilización de sellos tras reiniciar y mover la imagen original; requiere escritorio Windows disponible.
- `tests/release_checks.ps1`: ocho escenarios de análisis y remediación simulados; verifica que una detección, protección desactivada o error impidan validar una entrega, sin modificar Defender.
- `requirements-windows.lock`: diez dependencias de compilación, con URLs oficiales y hashes SHA-256 para Python 3.12/Windows x64.
- `MAPA.md`: conexiones y alcance del proyecto.

La inserción usa las coordenadas de página descritas en la [documentación oficial de PyMuPDF](https://pymupdf.readthedocs.io/en/latest/page.html). Se conserva el documento PDF; sus páginas no se convierten en capturas de pantalla.

La separación de instrucciones utiliza [ContentStream de pypdf](https://pypdf.readthedocs.io/en/6.9.0/modules/generic.html).

PyMuPDF/MuPDF se distribuye bajo AGPL o licencia comercial. Consulta sus condiciones antes de redistribuir una versión cerrada de la aplicación.
