const path = require('node:path');

function localFile(root, address) {
  const url = new URL(address);
  if (url.protocol !== 'app:' || url.hostname !== 'sello' || url.port || url.username || url.password) return null;
  const pathname = decodeURIComponent(url.pathname);
  if (pathname.includes('\0') || pathname.includes('\\')) return null;
  const target = path.resolve(root, '.' + (pathname === '/' ? '/index.html' : pathname));
  const relative = path.relative(root, target);
  return relative && !relative.startsWith('..') && !path.isAbsolute(relative) ? target : null;
}

const types = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript',
  '.mjs': 'text/javascript', '.json': 'application/json', '.svg': 'image/svg+xml',
  '.wasm': 'application/wasm', '.png': 'image/png', '.ttf': 'font/ttf',
};
module.exports = { localFile, types };
