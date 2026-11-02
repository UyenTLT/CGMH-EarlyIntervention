"""Build a CDN-hosted frontend without copying application data or credentials."""
import hashlib
import re
import json
import os
from pathlib import Path
import shutil
from urllib.parse import urlsplit

root = Path(__file__).resolve().parents[1]
api_base = os.environ.get('API_BASE_URL', '').rstrip('/')
url = urlsplit(api_base)
if not api_base or url.scheme not in ('https', 'http') or not url.netloc or url.username or url.password or url.query or url.fragment or url.path:
    raise SystemExit('API_BASE_URL must be an HTTP(S) origin without credentials, path, query, or fragment')
if url.scheme != 'https' and url.hostname not in ('localhost', '127.0.0.1'):
    raise SystemExit('Public API_BASE_URL must use HTTPS')
output = root / 'dist'
output.mkdir(exist_ok=True)
for name in ('index.html', 'app.js', 'style.css', 'diagnosis-data.js'):
    shutil.copy2(root / 'app/static' / name, output / name)
(output / 'config.js').write_text('window.CHECKLIST_CONFIG = ' + json.dumps({'apiBase': api_base}) + ';\n')
# Every build ties HTML to the exact assets, preventing mixed old/new layouts.
html = (output / 'index.html').read_text()
for name in ('app.js', 'style.css', 'diagnosis-data.js', 'config.js'):
    revision = hashlib.sha256((output / name).read_bytes()).hexdigest()[:12]
    pattern = r'((?:src|href)="\./' + re.escape(name) + r')(?:\?[^"]*)?(")'
    html = re.sub(pattern, lambda match: match.group(1) + '?v=' + revision + match.group(2), html)
(output / 'index.html').write_text(html)
print('Static frontend built in dist/')
