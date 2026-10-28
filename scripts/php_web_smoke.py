"""Prueba HTTP del portal PHP/MySQL. No imprime credenciales.

Crea una solicitud de prueba y, con --with-model, un análisis real de dos logs.
"""
import argparse
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import json
from pathlib import Path
import re
from urllib import error, parse, request
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.inputs, self.links = [], []
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'input':
            self.inputs.append(attrs)
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])

    def token(self):
        return next(item['value'] for item in self.inputs if item.get('name') == 'csrf')

    def log_ids(self):
        return [item['value'] for item in self.inputs if item.get('name') == 'log_ids[]']


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8090/')
    parser.add_argument('--with-model', action='store_true')
    args = parser.parse_args()
    settings = {}
    for line in (ROOT / '.local' / 'php-web.env').read_text(encoding='utf-8').splitlines():
        name, _, value = line.partition('=')
        settings[name] = value
    base = args.url.rstrip('/') + '/'
    cookies = CookieJar()
    browser = request.build_opener(request.ProxyHandler({}), request.HTTPCookieProcessor(cookies))
    checks = 0

    def call(path, data=None, expected=200):
        nonlocal checks
        payload = parse.urlencode(data, doseq=True).encode() if data is not None else None
        req = request.Request(parse.urljoin(base, path), data=payload)
        try:
            response = browser.open(req, timeout=165 if args.with_model else 30)
        except error.HTTPError as exception:
            response = exception
        with response:
            html = response.read(8_388_609).decode('utf-8')
            check(response.status == expected, f'Estado inesperado en {path.partition("?")[0]}: {response.status}')
            check(settings['IALOGS_API_KEY'] not in html, 'La clave del motor apareció en el HTML')
            check(settings['APP_ADMIN_PASSWORD'] not in html, 'La contraseña apareció en el HTML')
            checks += 1
            return html, response.url, response.headers

    for page in ['', 'productos.php', 'planes.php', 'contacto.php', 'privacidad.php', 'login.php']:
        html, _, headers = call(page)
        check('<?php' not in html and 'Content-Security-Policy' in headers, 'Falta renderizado PHP o CSP')
    check('HttpOnly' in str(headers.get_all('Set-Cookie', [])) or any('HttpOnly' in cookie._rest for cookie in cookies), 'La sesión debe usar HttpOnly')
    for asset in ['assets/site.css', 'assets/site.js', 'assets/favicon.svg']:
        call(asset)
    health, _, _ = call('health.php')
    check(json.loads(health)['database'] == 'ok', 'MySQL no responde')
    for page in ['eventos.php', 'analisis.php', 'solicitudes.php', 'evento.php?id=invalid']:
        _, final_url, _ = call(page)
        check(parse.urlparse(final_url).path.endswith('/login.php'), 'Página privada accesible sin sesión')
    call('login.php', {'email': settings['APP_ADMIN_EMAIL'], 'password': settings['APP_ADMIN_PASSWORD']}, expected=403)
    html, _, _ = call('login.php')
    call('login.php', {'csrf': Page(html).token(), 'email': settings['APP_ADMIN_EMAIL'], 'password': 'invalid-password'}, expected=401)
    html, _, _ = call('login.php')
    events, final_url, _ = call('login.php', {'csrf': Page(html).token(), 'email': settings['APP_ADMIN_EMAIL'], 'password': settings['APP_ADMIN_PASSWORD']})
    check(parse.urlparse(final_url).path.endswith('/eventos.php'), 'El login no abrió el panel')
    check('Conectado al motor de iaLogs.' in events, 'El panel PHP no conecta con FastAPI')
    ids = Page(events).log_ids()
    check(bool(ids), 'No hay logs reales para comprobar la integración')
    call('evento.php?id=' + parse.quote(ids[0]))
    escaped, _, _ = call('eventos.php?' + parse.urlencode({'text': "' OR 1=1 -- <script>"}))
    check('&lt;script&gt;' in escaped and '<script>' not in escaped, 'El filtro no se escapa correctamente')
    history, _, _ = call('analisis.php')
    call('analizar.php', expected=405)
    call('analizar.php', {'csrf': Page(history).token(), 'log_ids[]': ['not-a-uuid']}, expected=422)
    call('analizar.php', {'log_ids[]': ids[:1]}, expected=403)
    call('logout.php', expected=405)
    call('instalar.php', expected=404)
    for private in ['.env', '_init.php']:
        call(private, expected=403)
    call('ialogs-private/config/local.php', expected=404)
    marker = 'web-smoke-' + uuid4().hex[:12]
    contact, _, _ = call('contacto.php?plan=equipo')
    result, _, _ = call('contacto.php', {'csrf': Page(contact).token(), 'name': 'Prueba del portal',
        'email': marker + '@example.test', 'company': 'Prueba local', 'plan': 'equipo',
        'message': '<script>literal-' + marker + '</script>', 'privacy': '1', 'website': ''})
    check('Solicitud guardada.' in result, 'La solicitud no se guardó')
    enquiries, _, _ = call('solicitudes.php')
    check(marker in enquiries and '&lt;script&gt;literal-' + marker in enquiries, 'La solicitud no se recuperó o no se escapó')
    analysis_id = None
    if args.with_model:
        analysis, final_url, _ = call('analizar.php', {'csrf': Page(events).token(), 'log_ids[]': ids[:2]})
        parsed = parse.parse_qs(parse.urlparse(final_url).query)
        check(parse.urlparse(final_url).path.endswith('/analisis.php') and 'id' in parsed, 'El modelo no devolvió un análisis guardado')
        analysis_id = parsed['id'][0]
        links = [link for link in Page(analysis).links if 'evento.php?id=' in link]
        check(bool(links), 'Faltan enlaces a las evidencias')
        for link in links:
            referenced = parse.parse_qs(parse.urlparse(link).query)['id'][0]
            check(referenced in ids[:2], 'Una evidencia no pertenece a la selección')
        call(links[0])
        call('analisis.php?id=' + parse.quote(analysis_id))
    latest, _, _ = call('solicitudes.php')
    old_cookie = '; '.join(f'{cookie.name}={cookie.value}' for cookie in cookies)
    call('logout.php', {'csrf': Page(latest).token()})
    _, final_url, _ = call('eventos.php')
    check(parse.urlparse(final_url).path.endswith('/login.php'), 'La sesión no se cerró')
    replay = request.build_opener(request.ProxyHandler({}))
    with replay.open(request.Request(parse.urljoin(base, 'eventos.php'), headers={'Cookie': old_cookie}), timeout=15) as response:
        check(parse.urlparse(response.url).path.endswith('/login.php'), 'La sesión anterior sigue autenticada')
    print(f'Portal PHP HTTP OK: {checks} peticiones, páginas, recursos, MySQL, login/logout, CSRF, escape HTML, solicitudes y FastAPI.')
    if analysis_id:
        print(f'Ollama real a través de PHP OK: análisis {analysis_id}, evidencias y recuperación desde PostgreSQL.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, StopIteration, KeyError):
        raise SystemExit('La prueba HTTP del portal no se completó. Revisa el estado de los servicios y los logs privados; no se muestran credenciales.') from None
