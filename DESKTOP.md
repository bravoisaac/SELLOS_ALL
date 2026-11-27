# Sello PDF Escritorio

Versión de escritorio basada en Sello PDF Web, para **Windows 11 de 64 bits (x64)**. Incluye la interfaz, el visor y el motor de procesamiento; funciona sin internet y no necesita instalar Python ni Node.js.

**[Descargar la versión de escritorio 1.1.0](https://github.com/bravoisaac/SELLOS_ALL/releases/tag/desktop-v1.1.0)**

## Abrir la aplicación

1. Obtén `SelloPDF-Escritorio-1.1.0-Windows-x64.zip` desde la publicación anterior.
2. Haz clic derecho en el ZIP y elige **Extraer todo**.
3. Abre **Sello PDF Escritorio.exe** desde la carpeta extraída.

**Conserva todos los archivos y carpetas juntos.** Este paquete incluye su propio navegador; copiar solo el ejecutable no funciona. Puedes crear un acceso directo al ejecutable.

Elige tus PDF y la imagen del sello, ajusta su posición y capa, y guarda una copia desde el diálogo de Windows. La biblioteca **Mis sellos** permanece en el perfil de esta aplicación, independiente de la web. No se sincroniza entre equipos ni se trasladan automáticamente los sellos del navegador.

## Estado de la entrega

Esta es una **versión de prueba sin firma digital propia**. Un análisis local sin detecciones no garantiza la aceptación por todos los antivirus, navegadores o políticas de Windows. Si Windows la bloquea, no desactives la protección ni añadas exclusiones; conserva el mensaje para revisar la causa.

Se distribuye como carpeta portátil. La creación del instalador NSIS quedó bloqueada por la política de firma del equipo de compilación; no se publica ese instalador incompleto. La aplicación empaquetada se comprueba por separado mediante ejecución normal, sin cambiar las protecciones.

Los ejecutables antiguos de PyInstaller retirados por detecciones no se incluyen ni se reutilizan. La web sigue disponible en **[Sello PDF Web](https://bravoisaac.github.io/SELLOS_ALL/)**.

## Desarrollo

```powershell
npm ci
npm run desktop
npm run desktop:build
node --test tests/desktop-policy.test.cjs
npm run desktop:test
```

`desktop:test` usa PDF e imágenes sintéticos y un perfil temporal bajo `tmp/desktop-qa`. Requiere el entorno de desarrollo Python existente únicamente para generar los archivos de prueba. La aplicación entregada incluye Python WebAssembly y no usa el Python del equipo.

Para verificar el ejecutable empaquetado, establece `SELLO_PACKAGED_EXE` con su ruta antes de ejecutar la prueba. El resultado se guarda en `tmp/desktop-qa/packaged-validation.json`. Los artefactos de compilación se generan en `dist/desktop/`, fuera de Git.

`scripts/check-desktop.ps1` analiza el ZIP con Defender, lo extrae en una carpeta temporal, analiza esa carpeta y prueba la aplicación extraída. Solo si todo pasa genera `validation.json` y `SHA256SUMS.txt`. Tras guardar y subir el código, `scripts/publish-desktop.py` comprueba ese informe y los hashes; carga únicamente el ZIP y su suma en un borrador de GitHub, y publica la versión de prueba cuando GitHub confirma ambos archivos. Necesita la sesión Git del mantenedor y no almacena credenciales.

La interfaz tiene sandbox, aislamiento de contexto y Node.js deshabilitado. El protocolo local limita las lecturas a los recursos empaquetados; se bloquean navegación externa, ventanas nuevas y solicitudes de red. No hay puente IPC para ejecutar comandos del sistema.
