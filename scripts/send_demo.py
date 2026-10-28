"""Envía eventos sintéticos. API_KEY solo se lee del entorno."""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
import sys
from urllib import error, request


class NoRedirect(request.HTTPRedirectHandler):
    """Reject redirects so credentials are sent only to the configured URL."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


open_request = request.build_opener(NoRedirect()).open


def send(url, key, path, data):
    req = request.Request(url.rstrip('/') + path, data=json.dumps(data).encode(),
                          headers={'X-API-Key': key, 'Content-Type': 'application/json'})
    try:
        with open_request(req, timeout=150) as response:
            return json.load(response)
    except error.HTTPError as exc:
        if 300 <= exc.code < 400:
            raise SystemExit(f'Redirección HTTP rechazada (HTTP {exc.code}); revisa IALOGS_URL o --url.') from None
        descriptions = {
            401: 'API key no válida',
            403: 'acceso no autorizado',
            413: 'el lote o el contexto supera el límite permitido',
            422: 'los datos enviados no son válidos',
            429: 'la IA está ocupada',
            502: 'el modelo devolvió una respuesta no válida',
            503: 'la API, PostgreSQL o el modelo no están disponibles',
            504: 'Ollama ha superado el tiempo límite',
        }
        # Never print an untrusted error body: it could echo request credentials.
        raise SystemExit(f'HTTP {exc.code}: {descriptions.get(exc.code, "la API no pudo completar la solicitud")}.') from None
    except (error.URLError, TimeoutError):
        raise SystemExit('No se pudo conectar con la API.') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=os.getenv('IALOGS_URL', 'http://127.0.0.1:8000'))
    parser.add_argument('--analyze', action='store_true', help='Solicita también un análisis al Ollama configurado')
    args = parser.parse_args()
    key = os.getenv('API_KEY')
    if not key:
        sys.exit('Define API_KEY en el entorno; no la pases en la línea de comandos.')
    now = datetime.now(timezone.utc)
    events = [
        ('INFO', 'Inicio del servicio de pedidos', {'version': '1.4.0'}),
        ('WARNING', 'El pool de conexiones está cerca de su capacidad', {'pool_active': 19, 'pool_limit': 20}),
        ('ERROR', 'No se pudo obtener conexión a PostgreSQL: timeout tras 5 s', {'request_id': 'demo-001'}),
        ('ERROR', 'POST /orders terminó con estado 503', {'request_id': 'demo-001'}),
        ('INFO', 'Se recuperó una conexión del pool', {'request_id': 'demo-002'}),
    ]
    payload = {'events': [dict(timestamp=(now + timedelta(seconds=i)).isoformat(),
                               source='demo-windows', service='orders-api', severity=severity,
                               message=message, attributes=attributes)
                           for i, (severity, message, attributes) in enumerate(events)]}
    result = send(args.url, key, '/v1/logs', payload)
    print(f'Eventos sintéticos guardados: {len(result["items"])}')
    for item in result['items']:
        print(f'  {item["id"]} {item["severity"]} {item["message"]}')
    if args.analyze:
        analysis = send(args.url, key, '/v1/analyses', {'log_ids': [i['id'] for i in result['items']]})
        print(json.dumps(analysis, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
