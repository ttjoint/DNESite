from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import json, shutil, re
import base64
import html as html_module
import unicodedata

ROOT = Path(__file__).resolve().parent
META = ROOT / "metadata.json"

def read_meta(): return json.loads(META.read_text(encoding="utf-8")) if META.exists() else []
def write_meta(items): META.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
def esc(s):
    """Escape text before inserting it into generated HTML."""
    # Keep apostrophes: MediaWiki uses two/three apostrophes for emphasis.
    # Attribute values are generated from slugs and are escaped separately by
    # the browser-safe HTML templates below.
    return html_module.escape(str(s or ""), quote=False)


def _slug(value):
    value = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value, flags=re.UNICODE).strip("-")
    return value or "section"


def _lookup_entry(target):
    """Resolve an internal wiki title to the generated static page."""
    target = target.split("#", 1)[0].strip().replace("_", " ")
    if not target:
        return None
    for item in read_meta():
        if item.get("title", "").strip().casefold() == target.casefold():
            return item
    return None


def _lookup_media(name):
    """Resolve a File: name using media-index.json when available."""
    index_path = ROOT / "media-index.json"
    if not index_path.exists():
        return None
    wanted = Path(str(name).strip()).name.casefold()
    wanted_base = re.sub(r"^\d+px-", "", wanted)
    try:
        media = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return next((item for item in media if (
        Path(item.get("name", "")).name.casefold() == wanted
        or Path(item.get("name", "")).name.casefold().endswith("-" + wanted)
        or Path(item.get("name", "")).name.casefold().endswith(wanted)
        or re.sub(r"^\d+px-", "", Path(item.get("name", "")).name.casefold()) == wanted_base
    )), None)


def _split_attrs(value):
    """Split a table cell's optional HTML attributes from its content."""
    value = value.strip()
    if " | " in value:
        attrs, content = value.split(" | ", 1)
        if re.match(r"(?:[\w-]+\s*=\s*[^ ]+\s*)+$", attrs):
            return attrs, content
    return "", value


def wiki_html(source, link_prefix="../"):
    """Render the practical MediaWiki subset used by this archive.

    The renderer intentionally remains dependency-free so it also works from the
    local editing server.  It supports headings, lists, links, tables, references,
    extension tags and safe fallbacks for unsupported templates.
    """
    text = str(source or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"__NOTOC__|__NOEDITSECTION__", "", text, flags=re.I)
    references = []
    named_refs = {}
    tokens = {}

    def token(value):
        key = f"\x00MW{len(tokens)}\x00"
        tokens[key] = value
        return key

    def ref_tag(match):
        attrs, body = match.group(1) or "", match.group(2) or ""
        name_match = re.search(r"(?:name|group)\s*=\s*[\"']?([^\s\"']+)", attrs, re.I)
        name = name_match.group(1) if name_match else ""
        if name and name in named_refs:
            number = named_refs[name]
            if body.strip() and number <= len(references) and not references[number - 1][1]:
                references[number - 1] = (name, body.strip())
        else:
            number = len(references) + 1
            if body.strip() or not name:
                references.append((name, body.strip()))
            if name:
                named_refs[name] = number
        return token(f'<sup class="reference"><a href="#cite-{number}" id="ref-{number}">[{number}]</a></sup>')

    text = re.sub(r"<ref\b([^>]*)>(.*?)</ref\s*>", ref_tag, text, flags=re.I | re.S)

    def ref_self(match):
        attrs = match.group(1) or ""
        name_match = re.search(r"(?:name|group)\s*=\s*[\"']?([^\s\"']+)", attrs, re.I)
        name = name_match.group(1) if name_match else ""
        number = named_refs.get(name, len(references) + 1)
        if name and name not in named_refs:
            named_refs[name] = number
        if number > len(references):
            references.append((name, ""))
        return token(f'<sup class="reference"><a href="#cite-{number}" id="ref-{number}">[{number}]</a></sup>')

    text = re.sub(r"<ref\b([^>]*)/\s*>", ref_self, text, flags=re.I)

    def block_tag(match):
        name, attrs, body = match.group(1).lower(), match.group(2) or "", match.group(3) or ""
        if name == "poem":
            rendered = f'<pre class="poem">{esc(body.strip())}</pre>'
        elif name in {"nowiki", "pre", "syntaxhighlight", "source", "code", "math"}:
            cls = "syntax" if name in {"syntaxhighlight", "source"} else name
            rendered = f'<pre class="{cls}"><code>{esc(body.strip())}</code></pre>' if name != "code" else f'<code>{esc(body)}</code>'
        elif name == "gallery":
            images = []
            for line in body.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("|", 1)
                media = _lookup_media(parts[0])
                if media:
                    label = parts[1] if len(parts) > 1 else media.get("name", "")
                    images.append(f'<a class="gallery-item" href="{link_prefix}media/{esc(media.get("slug", ""))}.html"><img loading="lazy" src="{link_prefix}{esc(media.get("path", ""))}" alt="{esc(label)}"><span>{esc(label)}</span></a>')
            rendered = '<div class="gallery">' + "".join(images) + '</div>'
        else:
            rendered = esc(body)
        return token(rendered)

    text = re.sub(r"<(poem|nowiki|pre|syntaxhighlight|source|code|math|gallery)\b([^>]*)>(.*?)</\1\s*>", block_tag, text, flags=re.I | re.S)
    refs_token = token("__REFERENCES__")
    toc_token = token("__TOC__")
    text = re.sub(r"__TOC__", toc_token, text, flags=re.I)
    text = re.sub(r"<references\b[^>]*(?:/\s*>|>.*?</references\s*>)", refs_token, text, flags=re.I | re.S)
    text = re.sub(r"<br\s*/?>", token("<br>"), text, flags=re.I)
    text = re.sub(r"<hr\s*/?>", token("<hr>"), text, flags=re.I)
    text = re.sub(r"<center\b[^>]*>(.*?)</center\s*>", lambda m: token(f'<div class="center">{esc(m.group(1))}</div>'), text, flags=re.I | re.S)
    text = re.sub(
        r"<(small|big|u|s|strike|blockquote)\b[^>]*>(.*?)</\1\s*>",
        lambda m: token(f'<{m.group(1).lower()}>{esc(m.group(2))}</{m.group(1).lower()}>'),
        text,
        flags=re.I | re.S,
    )
    # Transclusion-control tags do not have meaning in a static export; retain
    # their content while removing only the wrapper.
    text = re.sub(r"</?(?:includeonly|onlyinclude|noinclude)\b[^>]*>", "", text, flags=re.I)

    def inline(value):
        value = esc(value)
        # Templates commonly found in the imported dumps.
        value = re.sub(r"\{\{\s*来源请求\s*\}\}", '<sup class="citation-needed">[来源请求]</sup>', value, flags=re.I)
        value = re.sub(r"\{\{\s*主条目\s*\|\s*([^}]+)\}\}", lambda m: f'<span class="main-article">主条目：{m.group(1)}</span>', value, flags=re.I)
        value = re.sub(r"\{\{\s*([^{}|]+)(?:\|[^{}]*)?\}\}", lambda m: f'<span class="template">{m.group(1).strip()}</span>', value)
        value = re.sub(r"\[\[\s*(?:File|文件|Image|图像):([^|\]]+)(?:\|([^\]]*))?\]\]", file_link, value, flags=re.I)
        value = re.sub(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]", internal_link, value)
        value = re.sub(r"\[(https?://[^\s\]]+)(?:\s+([^\]]+))?\]", lambda m: f'<a href="{m.group(1)}" target="_blank" rel="noopener noreferrer">{m.group(2) or m.group(1)}</a>', value)
        value = re.sub(r"(?<![\"=>])(https?://[^\s<]+)", r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>', value)
        value = re.sub(r"'''''(.*?)'''''", r"<strong><em>\1</em></strong>", value, flags=re.S)
        value = re.sub(r"'''(.*?)'''", r"<strong>\1</strong>", value, flags=re.S)
        value = re.sub(r"''(.*?)''", r"<em>\1</em>", value, flags=re.S)
        value = re.sub(r"~~(.*?)~~", r"<s>\1</s>", value, flags=re.S)
        value = re.sub(
            r"\x00MW\d+\x00",
            lambda m: m.group(0) if m.group(0) in {refs_token, toc_token} else tokens.get(m.group(0), m.group(0)),
            value,
        )
        return value

    def file_link(match):
        name, options = match.group(1).strip(), match.group(2) or ""
        media = _lookup_media(name)
        label = next((part[4:] for part in options.split("|") if part.strip().lower().startswith("alt=")), name)
        if media:
            return f'<a class="media-link" href="{link_prefix}media/{esc(media.get("slug", ""))}.html"><img loading="lazy" src="{link_prefix}{esc(media.get("path", ""))}" alt="{esc(label)}"></a>'
        return f'<span class="attachment">图片：{esc(name)}</span>'

    def internal_link(match):
        raw_target, label = match.group(1).strip(), match.group(2)
        target, fragment = (raw_target.split("#", 1) + [""])[:2] if "#" in raw_target else (raw_target, "")
        item = _lookup_entry(target)
        shown = label or target
        if item:
            href = f'{link_prefix}pages/{esc(item.get("slug", ""))}'
            if fragment:
                href += "#" + (fragment if fragment.startswith("section-") else "section-" + _slug(fragment))
            return f'<a href="{href}">{shown}</a>'
        if fragment and not target:
            return f'<a href="#{_slug(fragment)}">{shown}</a>'
        return f'<a href="#">{shown}</a>'

    lines = text.splitlines()
    output, i = [], 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("{|" ):
            table_lines = [line]
            i += 1
            while i < len(lines):
                table_lines.append(lines[i])
                if lines[i].strip() == "|}":
                    i += 1
                    break
                i += 1
            output.append(render_table(table_lines))
            continue
        heading = re.match(r"^(={2,6})\s*(.*?)\s*\1\s*$", stripped)
        if heading:
            level = min(6, max(2, len(heading.group(1))))
            title = inline(heading.group(2))
            plain = re.sub(r"<[^>]+>", "", heading.group(2))
            output.append(f'<h{level} id="section-{_slug(plain)}">{title}</h{level}>')
            i += 1
            continue
        if re.match(r"^[*#;:]+\s*", stripped):
            list_lines = []
            while i < len(lines) and re.match(r"^\s*[*#;:]+\s*", lines[i]):
                list_lines.append(lines[i].strip()); i += 1
            output.append(render_list(list_lines))
            continue
        token_value = tokens.get(stripped, "")
        if stripped in {refs_token, toc_token} or token_value.startswith(("<pre", "<table", "<div class=\"gallery", "<section", "<hr")):
            output.append(stripped); i += 1; continue
        if re.match(r"^-{4,}\s*$", stripped):
            output.append("<hr>"); i += 1; continue
        block = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(={2,6})\s.*\1\s*$", lines[i].strip()) and not lines[i].strip().startswith("{|") and not re.match(r"^[*#;:]+\s*", lines[i].strip()):
            block.append(lines[i]); i += 1
        output.append(f'<p>{inline("\n".join(block)).replace(chr(10), "<br>")}</p>')

    html = "\n".join(output)
    if refs_token in html:
        items = "".join(f'<li id="cite-{idx}">{inline(body)} <a href="#ref-{idx}">↩</a></li>' for idx, (_, body) in enumerate(references, 1))
        html = html.replace(refs_token, f'<section class="references"><h3>参考资料</h3><ol>{items or "<li>页面未提供引用内容。</li>"}</ol></section>')
    if toc_token in html:
        headings = re.findall(r'<h([2-6]) id="([^"]+)">(.*?)</h\1>', html)
        toc_items = "".join(f'<li class="toc-level-{level}"><a href="#{ident}">{label}</a></li>' for level, ident, label in headings)
        html = html.replace(toc_token, f'<nav class="wiki-toc"><strong>目录</strong><ul>{toc_items}</ul></nav>')
    for key, value in tokens.items():
        if key in html and value not in {"__REFERENCES__", "__TOC__"}:
            html = html.replace(key, value)
    return html


def render_table(lines):
    attrs = lines[0].strip()[2:].strip()
    class_match = re.search(r"class\s*=\s*([\"'])(.*?)\1", attrs, flags=re.I)
    extra_classes = []
    if class_match:
        extra_classes = [value for value in class_match.group(2).split() if value.lower() != "wikitable"]
        attrs = attrs[:class_match.start()] + attrs[class_match.end():]
    class_value = "wikitable" + (" " + " ".join(extra_classes) if extra_classes else "")
    # Imported warning boxes use a small File icon followed by a short notice.
    # Mark them so their icon can stay compact without affecting infobox photos.
    table_text = " ".join(lines).lower()
    if "[[file:" in table_text and any(marker in table_text for marker in ("不适内容", "小作品", "warning", "notice")):
        class_value += " notice-box"
    out = [f'<table class="{class_value}"{(" " + attrs.strip()) if attrs.strip() else ""}>']
    caption = None
    row_open = False
    for raw in lines[1:]:
        line = raw.strip()
        if line == "|}":
            if row_open:
                out.append("</tr>")
            break
        if line.startswith("|+"):
            caption = line[2:].strip()
            continue
        if line.startswith("|-"):
            if row_open:
                out.append("</tr>")
            out.append("<tr>"); row_open = True
            continue
        if line.startswith("!") or line.startswith("|"):
            if not row_open:
                out.append("<tr>"); row_open = True
            head = line.startswith("!")
            content = line[1:].strip()
            separator = "!!" if head else "||"
            cells = content.split(separator)
            for cell in cells:
                attrs_text, value = _split_attrs(cell)
                tag = "th" if head else "td"
                out.append(f'<{tag}{(" " + attrs_text) if attrs_text else ""}>{inline_table(value)}</{tag}>')
            continue
        # A line without a cell marker continues the previous cell, as in
        # MediaWiki's common infobox form (text immediately following | value).
        if row_open and line:
            end = max(out[-1].rfind("</td>"), out[-1].rfind("</th>")) if out else -1
            if end >= 0:
                out[-1] = out[-1][:end] + "<br>" + inline_table(line) + out[-1][end:]
    if caption:
        out.insert(1, f"<caption>{inline_table(caption)}</caption>")
    out.append("</table>")
    return "".join(out)


def inline_table(value):
    # Tables use the same inline syntax; this helper avoids a recursive block parse.
    value = esc(value)
    value = re.sub(r"\{\{\s*来源请求\s*\}\}", '<sup class="citation-needed">[来源请求]</sup>', value, flags=re.I)
    def table_file(match):
        name, options = match.group(1).strip(), match.group(2) or ""
        media = _lookup_media(name)
        label = next((part[4:] for part in options.split("|") if part.strip().lower().startswith("alt=")), name)
        if media:
            return f'<a class="media-link" href="../media/{esc(media.get("slug", ""))}.html"><img loading="lazy" src="../{esc(media.get("path", ""))}" alt="{esc(label)}"></a>'
        return f'<span class="attachment">图片：{esc(name)}</span>'
    value = re.sub(r"\[\[\s*(?:File|文件|Image|图像):([^|\]]+)(?:\|([^\]]*))?\]\]", table_file, value, flags=re.I)
    value = re.sub(r"'''(.*?)'''", r"<strong>\1</strong>", value, flags=re.S)
    value = re.sub(r"''(.*?)''", r"<em>\1</em>", value, flags=re.S)
    def table_link(match):
        raw, label = match.group(1).strip(), match.group(2)
        target, fragment = (raw.split("#", 1) + [""])[:2] if "#" in raw else (raw, "")
        item = _lookup_entry(target)
        if item:
            href = f'../pages/{esc(item.get("slug", ""))}'
            if fragment:
                href += "#" + (fragment if fragment.startswith("section-") else "section-" + _slug(fragment))
            return f'<a href="{href}">{label or target}</a>'
        return f'<a href="#">{label or raw}</a>'
    value = re.sub(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]", table_link, value)
    return value


def render_list(lines):
    # Keep ordered/unordered list semantics and nested depth readable without JS.
    out, stack = [], []
    for raw in lines:
        match = re.match(r"^([*#;:]+)\s*(.*)$", raw)
        if not match:
            continue
        marks, value = match.groups(); depth = len(marks); kind = "ol" if marks[-1] == "#" else "ul"
        while len(stack) < depth:
            out.append(f"<{kind}>"); stack.append(kind)
        while len(stack) > depth:
            out.append(f"</{stack.pop()}>")
        if stack and stack[-1] != kind:
            out.append(f"</{stack.pop()}><{kind}>"); stack.append(kind)
        out.append(f"<li>{inline_table(value)}</li>")
    while stack:
        out.append(f"</{stack.pop()}>")
    return "".join(out)
def page_html(item, body):
    # Metadata stores MediaWiki source.  Only preserve a complete HTML document
    # when an administrator explicitly pasted one; extension tags such as
    # <poem>, <ref> and <references> must still go through the wiki renderer.
    is_full_html = item.get("format") == "html" or bool(
        re.search(r"<!doctype\s+html|<article\b|<div\s+class=[\"']article-body", body or "", re.I)
    )
    if not is_full_html:
        body = wiki_html(body)
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
        if path == "/api/render":
            source = parse_qs(urlparse(self.path).query).get("source", [""])[0]
            return self.send_json({"html": wiki_html(source, link_prefix="")})
        return super().do_GET()
    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0)); data = json.loads(self.rfile.read(length) or b"{}")
        if path == "/api/render":
            return self.send_json({"html": wiki_html(data.get("source", ""), link_prefix=data.get("prefix", ""))})
        items = read_meta()
        if path == "/api/save":
            old = next((x for x in items if x["slug"] == data.get("slug")), None)
            if not old: return self.send_json({"error":"entry not found"}, 404)
            for key in ("title", "tags", "date", "source"): old[key] = data.get(key, old.get(key))
            old["body"] = data.get("body", old.get("body", "")); old["text"] = re.sub("<[^>]+>", " ", old["body"])[:1800]
            old["format"] = "html" if re.search(r"<!doctype\s+html|<article\b|<div\s+class=[\"']article-body", old["body"], re.I) else "wiki"
            (ROOT / "pages" / old["slug"]).write_text(page_html(old, old["body"]), encoding="utf-8"); write_meta(items)
            return self.send_json({"ok":True})
        if path == "/api/create":
            slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", data.get("title", "新词条")).strip("-") + ".html"
            item = {"slug":slug,"title":data.get("title","新词条"),"tags":data.get("tags",["文章"]),"date":data.get("date",""),"source":"本地录入","body":data.get("body",""),"text":"","format":"wiki"}
            items.append(item); (ROOT / "pages" / slug).write_text(page_html(item, item["body"]), encoding="utf-8"); write_meta(items)
            return self.send_json({"ok":True,"slug":slug})
        if path == "/api/delete":
            old = next((x for x in items if x["slug"] == data.get("slug")), None)
            if not old: return self.send_json({"error":"entry not found"}, 404)
            trash = ROOT / ".trash"; trash.mkdir(exist_ok=True); src = ROOT / "pages" / old["slug"]
            if src.exists(): shutil.move(str(src), str(trash / src.name))
            write_meta([x for x in items if x["slug"] != old["slug"]]); return self.send_json({"ok":True})
        if path == "/api/media/upload":
            name = re.sub(r"[^\w\u4e00-\u9fff.()-]+", "-", data.get("name", "upload.bin")).strip("-") or "upload.bin"
            target = ROOT / "assets" / "uploads" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(data.get("content", "")))
            return self.send_json({"ok": True, "path": "assets/uploads/" + name})
        return self.send_json({"error":"unknown endpoint"}, 404)
    def send_json(self, obj, status=200):
        raw=json.dumps(obj, ensure_ascii=False).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
if __name__ == "__main__":
    print("中国人Wiki 本地管理端: http://127.0.0.1:8765")
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
