"""Configura solo GitHub Pages del repositorio indicado, usando la sesión Git existente.

Las credenciales permanecen en memoria y nunca se imprimen ni se guardan.
"""
import argparse
import json
import subprocess
import urllib.error
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['status', 'enable'])
args = parser.parse_args()
repo = 'bravoisaac/SELLOS_ALL'
credential = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n', text=True, capture_output=True)
if credential.returncode:
    raise SystemExit('No se pudo usar la autenticación de GitHub configurada en Git.')
fields = dict(line.split('=', 1) for line in credential.stdout.splitlines() if '=' in line)
token = fields.get('password')
if not token:
    raise SystemExit('Git no devolvió una credencial utilizable.')


def api(path, method='GET', data=None):
    request = urllib.request.Request(f'https://api.github.com/repos/{repo}/{path}', method=method,
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                 'User-Agent': 'SelloPDF-Pages-Setup', 'X-GitHub-Api-Version': '2022-11-28'},
        data=json.dumps(data).encode() if data is not None else None)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.load(response) if response.status != 204 else {}
    except urllib.error.HTTPError as error:
        # No imprimir cabeceras ni contenido que pueda incluir credenciales.
        return error.code, {}


status, current = api('pages')
if args.action == 'enable':
    desired = {'build_type': 'legacy', 'source': {'branch': 'main', 'path': '/docs'}}
    if status == 404:
        status, current = api('pages', 'POST', desired)
    elif status == 200:
        status, _ = api('pages', 'PUT', desired)
        if status in (200, 204):
            status, current = api('pages')
    if status not in (200, 201, 204):
        raise SystemExit(f'No se pudo configurar Pages. HTTP {status}; no se cambiaron credenciales ni protecciones.')
    build_status, _ = api('pages/builds', 'POST', {})
    print(json.dumps({'configure_http': status, 'build_request_http': build_status}))
if status == 200 or status == 201:
    build_status, build = api('pages/builds/latest')
    print(json.dumps({'url': current.get('html_url'), 'status': current.get('status'),
        'source': current.get('source'), 'build_status': build.get('status'), 'build_commit': build.get('commit')}, ensure_ascii=False))
else:
    print(json.dumps({'pages_http': status}))
