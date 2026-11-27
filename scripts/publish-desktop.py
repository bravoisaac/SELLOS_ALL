"""Publica únicamente el ZIP validado y su checksum como prerelease de GitHub.

Usa la sesión Git existente; no guarda ni imprime credenciales. Una entrega incompleta
permanece en borrador. Nunca carga el instalador NSIS incompleto.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request

root = Path(__file__).resolve().parents[1]
version = json.loads((root / 'package.json').read_text(encoding='utf-8'))['version']
report = json.loads((root / 'dist/desktop/validation.json').read_text(encoding='utf-8-sig'))
expected_name = f'SelloPDF-Escritorio-{version}-Windows-x64.zip'
if report.get('status') != 'portable-validated' or report.get('archive') != expected_name:
    raise SystemExit('Falta validar el ZIP final; no se publica.')
artifact = root / 'dist/desktop' / expected_name
with artifact.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
if digest.upper() != report['sha256'].upper():
    raise SystemExit('El ZIP cambió después de validarse.')
checksum = root / 'dist/desktop/SHA256SUMS.txt'
if checksum.read_text(encoding='ascii').strip() != f'{digest}  {expected_name}':
    raise SystemExit('El archivo de sumas no coincide.')
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
if subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip():
    raise SystemExit('Guarda los cambios en Git antes de publicar la versión.')
remote_commit = subprocess.check_output(['git', 'ls-remote', 'origin', 'refs/heads/main'], cwd=root, text=True).split()[0]
if remote_commit != commit:
    raise SystemExit('La versión local todavía no coincide con main en GitHub.')
credential = subprocess.run(['git', 'credential', 'fill'], cwd=root,
    input='protocol=https\nhost=github.com\n\n', text=True, capture_output=True)
if credential.returncode:
    raise SystemExit('No se pudo autenticar con la sesión Git existente.')
fields = dict(line.split('=', 1) for line in credential.stdout.splitlines() if '=' in line)
token = fields.get('password')
if not token:
    raise SystemExit('Git no devolvió una credencial utilizable.')


def api(url, method='GET', payload=None, binary=False):
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
               'User-Agent': 'SelloPDF-Desktop-Release', 'X-GitHub-Api-Version': '2022-11-28'}
    data = payload if binary else json.dumps(payload).encode() if payload is not None else None
    headers['Content-Type'] = 'application/octet-stream' if binary else 'application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method=method, headers=headers, data=data), timeout=240) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f'GitHub devolvió HTTP {error.code}; no se muestran credenciales ni cabeceras.') from None


base = 'https://api.github.com/repos/bravoisaac/SELLOS_ALL'
tag = f'desktop-v{version}'
releases = api(base + '/releases?per_page=100')
release = next((item for item in releases if item['tag_name'] == tag), None)
body = f'''Versión de prueba de Sello PDF Escritorio para Windows 11 x64, basada en la aplicación web.

1. Descarga `{expected_name}`.
2. Haz clic derecho → **Extraer todo**.
3. Abre **Sello PDF Escritorio.exe**. Conserva todos los archivos de la carpeta juntos.

Funciona sin internet e incluye su propio motor. No necesitas instalar Python ni Node.js.
Los sellos guardados pertenecen al perfil de esta aplicación y no se sincronizan con la web.

La aplicación extraída pasó pruebas de arranque, exportación de PDF, persistencia tras reinicio y aislamiento de la interfaz. Defender no registró detecciones durante el análisis local del ZIP y su carpeta extraída.

**No tiene firma digital propia.** Las políticas de otro PC o sus protecciones pueden bloquearla; estas pruebas no garantizan aceptación universal. No desactives el antivirus ni añadas exclusiones. El instalador NSIS incompleto no se distribuye.

SHA-256 del ZIP: `{digest}`.

[Aplicación web](https://bravoisaac.github.io/SELLOS_ALL/) · [Instrucciones de escritorio](https://github.com/bravoisaac/SELLOS_ALL/blob/{commit}/DESKTOP.md)
'''
if release is None:
    release = api(base + '/releases', 'POST', {'tag_name': tag, 'target_commitish': commit,
        'name': f'Sello PDF Escritorio {version} · Windows x64', 'body': body, 'draft': True, 'prerelease': True})
elif not release['draft']:
    raise SystemExit('Esta versión ya está publicada. No se sobrescriben entregas existentes.')
for file in (artifact, checksum):
    data = file.read_bytes()
    asset_digest = 'sha256:' + hashlib.sha256(data).hexdigest()
    existing = next((asset for asset in release['assets'] if asset['name'] == file.name), None)
    if existing:
        if existing.get('digest') != asset_digest:
            raise SystemExit('Hay un archivo distinto en el borrador; no se reemplaza automáticamente.')
        continue
    print(f'Cargando {file.name} ({len(data) // 1024 // 1024} MB)…', flush=True)
    url = release['upload_url'].split('{')[0] + '?name=' + urllib.parse.quote(file.name)
    uploaded = api(url, 'POST', data, binary=True)
    if uploaded.get('digest') != asset_digest:
        raise SystemExit('GitHub no confirmó el hash del archivo cargado. Se conserva el borrador.')
published = api(base + f"/releases/{release['id']}", 'PATCH', {'draft': False, 'prerelease': True, 'body': body})
print(json.dumps({'release_url': published['html_url'], 'downloads': [asset['browser_download_url'] for asset in published['assets']]}, ensure_ascii=False))
