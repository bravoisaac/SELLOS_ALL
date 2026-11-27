import { _electron as electron } from 'playwright';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import path from 'node:path';
import assert from 'node:assert/strict';

const root = process.cwd();
const out = path.join(root, 'tmp/desktop-qa');
await mkdir(out, { recursive: true });
const fixtures = spawnSync(path.join(root, '.venv/Scripts/python.exe'), ['tests/make_desktop_fixtures.py'], { encoding: 'utf8' });
if (fixtures.status !== 0) throw new Error('No se pudieron crear los PDF sintéticos de prueba: ' + fixtures.stderr);
const packaged = process.env.SELLO_PACKAGED_EXE;
const executablePath = packaged || path.join(root, 'node_modules/electron/dist/electron.exe');
const profile = path.join(out, `profile-${Date.now()}`);
const env = { ...process.env }; delete env.ELECTRON_RUN_AS_NODE;
const args = [...(packaged ? [] : [root]), '--sello-hidden', `--sello-profile=${profile}`];
let app;
async function launch() {
  app = await electron.launch({ executablePath, args, env, timeout: 45000 });
  const page = await app.firstWindow();
  await page.getByRole('heading', { name: 'Tu sello. En cada página.' }).waitFor();
  return page;
}
const errors = [];
try {
  const page = await launch();
  console.log('Ventana de escritorio iniciada.');
  page.on('pageerror', error => errors.push(error.message));
  assert.equal(page.url(), 'app://sello/');
  const isolation = await app.evaluate(({ BrowserWindow }) => {
    const settings = BrowserWindow.getAllWindows()[0].webContents.getLastWebPreferences();
    return { sandbox: settings.sandbox, contextIsolation: settings.contextIsolation, nodeIntegration: settings.nodeIntegration };
  });
  assert.deepEqual(isolation, { sandbox: true, contextIsolation: true, nodeIntegration: false });
  assert.equal(await page.evaluate(() => typeof window.require), 'undefined');
  const remoteBlocked = await page.evaluate(async () => { try { await fetch('https://example.com'); return false; } catch { return true; } });
  assert.equal(remoteBlocked, true);
  await page.locator('#pdf-input').setInputFiles(path.join(out, 'documento.pdf'));
  await page.getByText('Documento original', { exact: true }).waitFor();
  console.log('PDF sintético abierto.');
  await page.locator('#image-input').setInputFiles(path.join(out, 'sello.png'));
  await page.getByText('Sello aplicado', { exact: true }).waitFor({ timeout: 120000 });
  console.log('Motor local y vista previa verificados.');
  await page.getByRole('combobox', { name: 'Capa del sello' }).selectOption('middle');
  await page.getByText('Sello aplicado', { exact: true }).waitFor();
  await page.getByRole('button', { name: 'Guardar actual' }).click();
  await page.getByRole('textbox', { name: 'Nombre del sello' }).fill('Sello escritorio QA');
  await page.getByRole('button', { name: 'Guardar sello', exact: true }).click();
  await page.getByRole('dialog').waitFor({ state: 'hidden' });
  const destination = path.join(out, packaged ? 'empaquetado.pdf' : 'desarrollo.pdf');
  // Sustituye solo el diálogo de guardado en la sesión de prueba; la aplicación entregada siempre pregunta destino.
  await app.evaluate(({ session }, savePath) => {
    globalThis.qaDownloaded = null;
    session.defaultSession.once('will-download', (_event, item) => {
      item.setSavePath(savePath);
      item.once('done', (_event, status) => { globalThis.qaDownloaded = status; });
    });
  }, destination);
  await page.getByRole('button', { name: 'Descargar PDF sellado', exact: true }).click();
  await page.getByRole('heading', { name: 'Tus archivos están listos' }).waitFor({ timeout: 120000 });
  for (let i = 0; i < 100; i++) {
    if (await app.evaluate(() => globalThis.qaDownloaded) === 'completed') break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.equal(await app.evaluate(() => globalThis.qaDownloaded), 'completed');
  assert.ok((await readFile(destination)).subarray(0, 5).equals(Buffer.from('%PDF-')));
  await page.screenshot({ path: path.join(out, packaged ? 'empaquetado.png' : 'desarrollo.png'), fullPage: true });
  await app.close(); app = null;
  const reopened = await launch();
  await reopened.getByRole('combobox', { name: 'Mis sellos' }).selectOption({ label: 'Sello escritorio QA' });
  await reopened.getByRole('img', { name: 'Imagen del sello', exact: true }).waitFor();
  assert.equal(await reopened.getByRole('combobox', { name: 'Capa del sello' }).inputValue(), 'middle');
  assert.deepEqual(errors, []);
  const report = { packaged: !!packaged, executablePath, isolation, remoteBlocked, export: destination, persistence: true, errors };
  await writeFile(path.join(out, packaged ? 'packaged-validation.json' : 'dev-validation.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
} catch (error) {
  if (app) {
    const page = await app.firstWindow();
    console.error(await page.locator('#notice').textContent().catch(() => 'Sin aviso de la interfaz.'));
    console.error(await page.locator('#preview-status').textContent().catch(() => 'Sin estado de vista previa.'));
    await page.screenshot({ path: path.join(out, 'failure.png'), fullPage: true }).catch(() => {});
  }
  throw error;
} finally { await app?.close(); }
