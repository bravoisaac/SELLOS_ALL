const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { localFile } = require('../desktop/protocol.cjs');
const root = path.resolve('docs');
test('sirve únicamente archivos del origen y directorio de la aplicación', () => {
  assert.equal(localFile(root, 'app://sello/'), path.join(root, 'index.html'));
  assert.equal(localFile(root, 'app://sello/vendor/pyodide/pyodide.asm.wasm'), path.join(root, 'vendor/pyodide/pyodide.asm.wasm'));
  for (const url of ['https://sello/index.html', 'app://otro/index.html', 'app://user@sello/index.html', 'app://sello:90/index.html',
    'app://sello/..%2fpackage.json', 'app://sello/%2e%2e%5cpackage.json', 'app://sello/%00']) {
    assert.equal(localFile(root, url), null, url);
  }
});
