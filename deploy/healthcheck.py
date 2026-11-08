"""Verify HTTP and a database query, without depending on curl in the image."""
import json
from urllib.request import Request, urlopen
request = Request('http://127.0.0.1:8000/health/', headers={'Host': 'localhost', 'X-Forwarded-Proto': 'https'})
with urlopen(request, timeout=5) as response:
    if response.status != 200 or json.load(response).get('status') != 'ok':
        raise SystemExit(1)
