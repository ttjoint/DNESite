from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import json, shutil, re

ROOT = Path(__file__).resolve().parent
META = ROOT / "metadata.json"

def read_meta(): return json.loads(META.read_text(encoding="utf-8")) if META.exists() else []
def write_meta(items): META.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
def wiki_html(source):
    # Deliberately small MediaWiki subset for local editing and preview.
    s = esc(source or "")
    s = re.sub(r"^={2,6}\s*(.*?)\s*={2,6}$", r"<h2>\1</h2>", s, flags=re.M)
    s = re.sub(r"'''(.*?)'''", r"<strong>\1</strong>", s)
    s = re.sub(r"''(.*?)''", r"<em>\1</em>", s)
    s = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: '<a href="#">'+(m.group(2) or m.group(1))+'</a>', s)
    return "\n".join("<p>" + x.replace("\n", "<br>") + "</p>" for x in re.split(r"\n\s*\n", s) if x.strip())
def page_html(item, body):
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(item['title'])} · 中国人Wiki</title><link rel="stylesheet" href="../style.css"></head><body><header class="site-header"><a class="brand" href="../index.html">中国人Wiki</a><a class="back" href="../index.html">返回目录</a><a class="edit-link" href="../admin.html?slug={item['slug']}">编辑</a></header><main class="page-wrap"><article class="article"><h1>{esc(item['title'])}</h1><div class="entry-info"><span>录入：{esc(item.get('date',''))}</span><span>{' '.join('#'+esc(t) for t in item.get('tags',[]))}</span></div><div class="article-body">{body}</div></article></main><script src="../app.js"></script></body></html>'''
class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/entries":
            data = read_meta()
            return self.send_json(data)
        if path == "/api/entry":
            slug = parse_qs(urlparse(self.path).query).get("slug", [""])[0]
            item = next((x for x in read_meta() if x["slug"] == slug), None)
            if not item and "-" in slug:
                # Browsers on Windows can transcode CJK filenames in query strings;
                # the stable hash suffix still identifies the entry uniquely.
                suffix = slug.rsplit("-", 1)[-1]
                item = next((x for x in read_meta() if x["slug"].rsplit("-", 1)[-1] == suffix), None)
            return self.send_json(item or {}, 200 if item else 404)
        return super().do_GET()
    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0)); data = json.loads(self.rfile.read(length) or b"{}")
        items = read_meta()
        if path == "/api/save":
            old = next((x for x in items if x["slug"] == data.get("slug")), None)
            if not old: return self.send_json({"error":"entry not found"}, 404)
            for key in ("title", "tags", "date", "source"): old[key] = data.get(key, old.get(key))
            old["body"] = data.get("body", old.get("body", "")); old["text"] = re.sub("<[^>]+>", " ", old["body"])[:1800]
            (ROOT / "pages" / old["slug"]).write_text(page_html(old, old["body"]), encoding="utf-8"); write_meta(items)
            return self.send_json({"ok":True})
        if path == "/api/create":
            slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", data.get("title", "新词条")).strip("-") + ".html"
            item = {"slug":slug,"title":data.get("title","新词条"),"tags":data.get("tags",["文章"]),"date":data.get("date",""),"source":"本地录入","body":data.get("body",""),"text":""}
            items.append(item); (ROOT / "pages" / slug).write_text(page_html(item, item["body"]), encoding="utf-8"); write_meta(items)
            return self.send_json({"ok":True,"slug":slug})
        if path == "/api/delete":
            old = next((x for x in items if x["slug"] == data.get("slug")), None)
            if not old: return self.send_json({"error":"entry not found"}, 404)
            trash = ROOT / ".trash"; trash.mkdir(exist_ok=True); src = ROOT / "pages" / old["slug"]
            if src.exists(): shutil.move(str(src), str(trash / src.name))
            write_meta([x for x in items if x["slug"] != old["slug"]]); return self.send_json({"ok":True})
        return self.send_json({"error":"unknown endpoint"}, 404)
    def send_json(self, obj, status=200):
        raw=json.dumps(obj, ensure_ascii=False).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
if __name__ == "__main__":
    print("中国人Wiki 本地管理端: http://127.0.0.1:8765")
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
