const { app, BrowserWindow, Menu, protocol, session, dialog } = require('electron');
const path = require('node:path');
const fs = require('node:fs/promises');
const { localFile, types } = require('./protocol.cjs');

protocol.registerSchemesAsPrivileged([{ scheme: 'app', privileges: {
  standard: true, secure: true, supportFetchAPI: true, corsEnabled: true, codeCache: true,
} }]);
app.enableSandbox();
app.setAppUserModelId('cl.sello.pdf.desktop');
app.setName('Sello PDF Escritorio');
// Una ruta explícita permite probar con un perfil separado, sin tocar los sellos personales.
const profile = process.argv.find(arg => arg.startsWith('--sello-profile='));
if (profile) app.setPath('userData', path.resolve(profile.slice('--sello-profile='.length)));
let window;

async function createWindow() {
  window = new BrowserWindow({
    width: 1360, height: 950, minWidth: 700, minHeight: 600,
    title: 'Sello PDF Escritorio', backgroundColor: '#f4f6fa', show: false,
    autoHideMenuBar: true,
    webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true,
      webSecurity: true, allowRunningInsecureContent: false, webviewTag: false, spellcheck: false },
  });
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', (event, url) => { if (url !== 'app://sello/' && url !== 'app://sello/index.html') event.preventDefault(); });
  window.webContents.on('will-attach-webview', event => event.preventDefault());
  window.webContents.on('page-title-updated', event => { event.preventDefault(); });
  window.webContents.on('did-finish-load', () => {
    // Etiqueta de presentación: el motor y los controles son exactamente los de la web.
    window.webContents.executeJavaScript("document.title='Sello PDF Escritorio'; document.querySelector('.web-label').textContent='ESCRITORIO · SIN CONEXIÓN'; document.querySelector('.privacy-badge').lastChild.textContent='Archivos privados, en tu equipo';").catch(() => {});
  });
  window.once('ready-to-show', () => { if (!process.argv.includes('--sello-hidden')) window.show(); });
  window.on('closed', () => { window = null; });
  await window.loadURL('app://sello/');
}

app.whenReady().then(async () => {
  Menu.setApplicationMenu(null);
  const root = path.join(app.getAppPath(), 'docs');
  protocol.handle('app', async request => {
    if (!['GET', 'HEAD'].includes(request.method)) return new Response('', { status: 405 });
    try {
      const file = localFile(root, request.url);
      if (!file) return new Response('', { status: 403 });
      const body = await fs.readFile(file);
      return new Response(request.method === 'HEAD' ? null : body, { headers: {
        'Content-Type': types[path.extname(file)] || 'application/octet-stream',
        'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store',
      } });
    } catch { return new Response('', { status: 404 }); }
  });
  const localSession = session.defaultSession;
  localSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  localSession.setPermissionCheckHandler(() => false);
  localSession.webRequest.onBeforeRequest({ urls: ['http://*/*', 'https://*/*', 'ws://*/*', 'wss://*/*'] }, (_details, callback) => callback({ cancel: true }));
  localSession.on('will-download', (event, item) => {
    // Solo resultados producidos por la propia interfaz, nunca instaladores o enlaces externos.
    if (!item.getURL().startsWith('blob:app://sello/') || !/\.(pdf|zip|csv)$/i.test(item.getFilename())) { event.preventDefault(); return; }
    item.setSaveDialogOptions({ title: 'Guardar resultado de Sello PDF', defaultPath: path.join(app.getPath('downloads'), path.basename(item.getFilename())) });
    item.once('done', (_event, status) => {
      if (status === 'interrupted' && window) dialog.showMessageBox(window, { type: 'error', title: 'No se pudo guardar', message: 'No se pudo guardar el archivo. Vuelve a pulsar el enlace del resultado y elige una carpeta con espacio disponible.' });
    });
  });
  await createWindow();
}).catch(() => {
  dialog.showErrorBox('Sello PDF', 'No se pudo iniciar la aplicación. Reinstala esta versión desde la publicación oficial.');
  app.quit();
});
app.on('window-all-closed', () => app.quit());
