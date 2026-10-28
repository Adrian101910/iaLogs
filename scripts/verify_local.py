"""Comprueba el despliegue local y prueba Ollama solo si el modelo ya existe.

No descarga modelos. Puede guardar un análisis real de dos eventos existentes.
Ejecutar con el servicio sender, que proporciona API_KEY solo por entorno.
"""
import argparse
import os
import re
import sys

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', help='Limita los dos eventos de la prueba a un origen concreto')
    args = parser.parse_args()
    key = os.environ.get('API_KEY')
    if not key:
        sys.exit('Falta API_KEY en el entorno.')
    base = os.environ.get('IALOGS_URL', 'http://127.0.0.1:8000').rstrip('/')
    frontend = os.environ.get('FRONTEND_URL', 'http://frontend:8080').rstrip('/')
    headers = {'X-API-Key': key}
    with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as client:
        health = client.get(base + '/health')
        if health.status_code != 200:
            sys.exit('La comprobación de PostgreSQL falló.')
        index = client.get(frontend + '/')
        if index.status_code != 200 or 'id="root"' not in index.text:
            sys.exit('No se pudo obtener la aplicación React.')
        assets = re.findall(r'(?:src|href)="([^" ]+\.(?:js|css))"', index.text)
        if len(assets) < 2:
            sys.exit('Faltan los recursos compilados de React.')
        for asset in assets:
            if client.get(frontend + '/' + asset.lstrip('/')).status_code != 200:
                sys.exit('No se pudo obtener un recurso de la interfaz.')
        if client.get(frontend + '/api/v1/logs?limit=1').status_code != 401:
            sys.exit('El proxy debe exigir API key.')
        filters = {'limit': 2}
        if args.source:
            filters['source'] = args.source
        logs = client.get(frontend + '/api/v1/logs', params=filters, headers=headers)
        if logs.status_code != 200:
            sys.exit('La consulta autenticada a través del proxy falló.')
        page = logs.json()
        print(f'Despliegue HTTP OK: PostgreSQL, React, JS/CSS, proxy y API key. Eventos: {page["total"]}.')
        ollama = os.environ.get('OLLAMA_BASE_URL', 'http://host.docker.internal:11434').rstrip('/')
        model = os.environ.get('OLLAMA_MODEL', 'qwen2.5-coder:14b')
        try:
            tags = client.get(ollama + '/api/tags', timeout=3)
            tags.raise_for_status()
            installed = {entry.get('name') for entry in tags.json().get('models', [])}
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            print('PENDIENTE: Ollama no responde desde Docker; el modelo real no se ha verificado.')
            return
        if model not in installed:
            print(f'PENDIENTE: Ollama responde, pero {model} no está instalado. No se descarga automáticamente.')
            return
        if not page['items']:
            sys.exit('No hay eventos para probar el modelo real. Ejecuta primero sender.')
        timeout = float(os.environ.get('OLLAMA_TIMEOUT_SECONDS', '120')) + 10
        analysis = client.post(base + '/v1/analyses', headers=headers,
                               json={'log_ids': [row['id'] for row in page['items']]}, timeout=timeout)
        if analysis.status_code != 201:
            sys.exit(f'La prueba con el modelo real falló (HTTP {analysis.status_code}). Revisa servicio/modelo; no se guarda salida inválida.')
        result = analysis.json()
        stored = client.get(base + '/v1/analyses/' + result['id'], headers=headers)
        if stored.status_code != 200 or stored.json() != result:
            sys.exit('El análisis no se pudo recuperar de PostgreSQL después de guardarlo.')
        print(f'Modelo real OK: diagnóstico validado y guardado como {result["id"]}.')


if __name__ == '__main__':
    main()
