"""Build the media catalogue and link every embedded image to its viewer."""
from pathlib import Path
from hashlib import sha1
from bs4 import BeautifulSoup
import json, mimetypes, re

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
MEDIA = ROOT / "media"
MEDIA.mkdir(exist_ok=True)
records = []
for file in ASSETS.rglob('*'):
    if not file.is_file() or file.name.lower().startswith(('file-', 'file_')) or file.suffix.lower() in {'.css','.js','.json','.desc','.z','.octet-stream'}:
        continue
    rel = file.relative_to(ASSETS).as_posix()
    slug = sha1(rel.encode()).hexdigest()[:12]
    records.append({'slug': slug, 'name': file.name, 'path': 'assets/' + rel, 'type': mimetypes.guess_type(file.name)[0] or 'application/octet-stream', 'size': file.stat().st_size, 'date': file.stat().st_mtime})
by_path = {x['path']: x['slug'] for x in records}
(ROOT / 'media-index.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf8')
for page in (ROOT / 'pages').glob('*.html'):
    soup = BeautifulSoup(page.read_text(encoding='utf8', errors='replace'), 'html.parser')
    for image in soup.find_all('img'):
        src = image.get('src','').replace('../','')
        slug = by_path.get(src)
        if slug:
            parent = image.parent
            if parent.name == 'a': parent['href'] = '../media/' + slug + '.html'
            else:
                image.wrap(soup.new_tag('a', href='../media/' + slug + '.html'))
    page.write_text(soup.prettify(formatter='html'), encoding='utf8')
for item in records:
    body = f'<img class="media-view" src="../{item["path"]}" alt="{item["name"]}">' if item['type'].startswith('image/') else (f'<video controls src="../{item["path"]}"></video>' if item['type'].startswith('video/') else f'<audio controls src="../{item["path"]}"></audio>')
    (MEDIA / (item['slug'] + '.html')).write_text(f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{item["name"]} · 中国人Wiki</title><link rel="stylesheet" href="../style.css"></head><body><header class="site-header"><a class="brand" href="../index.html">中国人Wiki</a><a class="back" href="../media.html">媒体资源</a></header><main class="page-wrap"><article class="article"><h1>{item["name"]}</h1><p class="entry-info">{item["type"]} · {item["size"]:,} bytes</p><div class="media-detail">{body}</div></article></main><script src="../app.js"></script></body></html>', encoding='utf8')
print(f'media: {len(records)}')
