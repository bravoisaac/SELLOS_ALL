# Mapa del proyecto

- Objetivo: aplicación Windows portable que agrega una imagen arriba a la derecha de cada página de un PDF o de todos los PDF de una carpeta.
- Framework: Python, Tkinter/ttk, Pillow y PyMuPDF; empaquetado con PyInstaller.
- Entrada: `app.py`.
- Pantalla: selección de PDF o carpeta e imagen, selector de documento para vista previa, tamaño y márgenes en milímetros, progreso y resumen por archivo.
- Servicio: `stamping.py` valida archivos, calcula coordenadas según la rotación, inserta el sello detrás del contenido original y guarda una copia de forma atómica. La vista previa y ambos modos de guardado comparten `insert_stamp`.
- Estado local: rutas, página actual, opciones del sello y estado de procesamiento. Sin servicios externos ni base de datos.
- Flujo: elegir archivos → ajustar y revisar → elegir destino → sellar todas las páginas → abrir resultado.
- Patrones previos: carpeta vacía.
- Archivos de esta ampliación: `app.py`, `stamping.py`, `tests/test_batch.py`, `README.md`, `MAPA.md`. Se reutilizan las dependencias y el proceso de compilación.
- Lotes: PDF directamente contenidos en la carpeta, sin subcarpetas. Resultados en una nueva carpeta `Sellados` (numerada si ya existe), informe CSV y continuidad ante errores individuales.
- Cambio de capas: `stamping.py`, texto de ayuda en `app.py`, `README.md` y prueba de texto superpuesto en `tests/test_stamping.py`. Se conserva la posición superior derecha y el flujo de carpetas.
- Verificación: pruebas automáticas de motor y lotes, incluida legibilidad de texto sobre el sello; prueba de integración Tk con procesos independientes en `tests/gui_smoke.py`.
- Archivos que se preservan: PDF e imagen originales; no se modifica configuración externa.
- Validaciones: archivos ilegibles, PDF protegido, valores inválidos, sello fuera de página, destino igual al original, errores de escritura.
- Riesgo: medio; la geometría se verifica con páginas de distinto tamaño, recortadas y rotadas. El procesamiento se ejecuta en procesos separados para mantener la ventana disponible y aislar el motor PDF.
