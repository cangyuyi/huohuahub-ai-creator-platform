# -*- coding: utf-8 -*-
import httpx, json, sys, time, os
sys.stdout.reconfigure(encoding='utf-8')

DIFY_API_KEY = os.environ.get("DIFY_API_KEY", "")

print('Calling Dify workflow (single image)...', flush=True)
start = time.time()
resp = httpx.post(
    'https://api.dify.ai/v1/workflows/run',
    headers={'Authorization': f'Bearer {DIFY_API_KEY}', 'Content-Type': 'application/json'},
    json={'inputs': {}, 'response_mode': 'blocking', 'user': 'test-single'},
    timeout=180,
    trust_env=False
)
elapsed = time.time() - start
data = resp.json()
status = data.get('data', {}).get('status', 'unknown')
print(f'Elapsed: {elapsed:.1f}s, Status: {status}', flush=True)

if status != 'succeeded':
    print(f'Error: {data.get("data", {}).get("error", "unknown")}', flush=True)
    print(json.dumps(data, ensure_ascii=False)[:2000], flush=True)
    sys.exit(1)

outputs = data.get('data', {}).get('outputs', {})
result = outputs.get('result', '')
print('=== RESULT ===', flush=True)
print(result[:2000], flush=True)

comic = outputs.get('comic_image', [])
if comic and isinstance(comic, list) and len(comic) > 0:
    url = comic[0].get('url', '') if isinstance(comic[0], dict) else str(comic[0])
    print(f'\n=== COMIC IMAGE ===\n{url}', flush=True)
else:
    print('\n=== COMIC IMAGE: EMPTY ===', flush=True)
