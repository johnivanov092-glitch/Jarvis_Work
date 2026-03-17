import os
import httpx

OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')

async def list_ollama_models():
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(f'{OLLAMA_BASE_URL}/api/tags')
            response.raise_for_status()
            data = response.json()
    except Exception:
        return {'status': 'error', 'ollama_ok': False, 'models': []}
    models = []
    for item in data.get('models', []):
        name = (item or {}).get('name')
        if name:
            models.append({'name': name})
    return {'status': 'ok', 'ollama_ok': True, 'models': models}
