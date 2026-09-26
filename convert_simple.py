"""Safely convert simple migrated HTML bodies to readable MediaWiki source."""
from pathlib import Path
from bs4 import BeautifulSoup
import json, re

ROOT = Path(__file__).resolve().parent
meta = json.loads((ROOT / 'metadata.json').read_text(encoding='utf8'))
converted = 0
for item in meta:
    body = item.get('body', '')
    soup = BeautifulSoup(body, 'html.parser')
    if soup.find(['table', 'img', 'video', 'audio', 'iframe', 'pre']) or len(soup.find_all(True)) > 80:
        continue
    parts = []
    for node in soup.select('.mw-parser-output > *') or soup.contents:
        if not getattr(node, 'get_text', None):
            continue
        if node.name in {'h2', 'h3', 'h4', 'h5', 'h6'}:
            level = min(max(int(node.name[1]), 2), 6)
            parts.append('=' * level + ' ' + node.get_text(' ', strip=True) + ' ' + '=' * level)
        elif node.name == 'p':
            text = node.get_text(' ', strip=True)
            for strong in node.find_all(['strong', 'b']):
                text = text.replace(strong.get_text(' ', strip=True), "'''" + strong.get_text(' ', strip=True) + "'''")
            for em in node.find_all(['em', 'i']):
                text = text.replace(em.get_text(' ', strip=True), "''" + em.get_text(' ', strip=True) + "''")
            for link in node.find_all('a'):
                label = link.get_text(' ', strip=True)
                if label: text = text.replace(label, '[[' + label + ']]', 1)
            if text: parts.append(text)
    source = '\n\n'.join(parts).strip()
    if source and source != soup.get_text('\n', strip=True):
        item['body'] = source
        converted += 1
(ROOT / 'metadata.json').write_text(json.dumps(meta, ensure_ascii=True, indent=2), encoding='utf8')
print('converted', converted)
