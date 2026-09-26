from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup, Comment


ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
PAGES = OUT / "pages"
ASSETS = OUT / "assets"


def slug_for(source: str, rel: str, title: str) -> str:
    seed = f"{source}:{rel}:{title}".encode("utf-8", "ignore")
    digest = hashlib.sha1(seed).hexdigest()[:10]
    readable = unicodedata.normalize("NFKC", title or Path(rel).stem)
    readable = re.sub(r"[^\w\-\u4e00-\u9fff]+", "-", readable, flags=re.UNICODE).strip("-").lower()
    return f"{readable[:72] or 'entry'}-{digest}.html"


def clean_title(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    # Keep hyphens inside identifiers such as SCP-ZHINA-2019-50; only trim
    # the archive site's suffix when it is separated by surrounding spaces.
    value = re.sub(r"\s+[-|｜]\s+.*$", "", value)
    return value or "未命名词条"


def is_comment_title(title: str) -> bool:
    t = title.lower().replace(" ", "")
    markers = ("留言", "留言板", "评论区", "评论:", "评论：", "讨论:", "讨论：", "guestbook", "comment", "talk:")
    return any(m in t for m in markers)


def source_info():
    return {
        "esu": {"label": "esu-main", "base": ROOT / "esu-main"},
        "red": {"label": "red-bank-main", "base": ROOT / "red-bank-main" / "zhina.red"},
        "red-archive": {"label": "simafive-master/Red", "base": ROOT / "simafive-master" / "Red" / "zhina.red"},
        "esutest": {"label": "simafive-master/esutest", "base": ROOT / "simafive-master" / "esutest" / "esutestmirahezeorg_w-20200828-wikidump"},
    }


def copy_asset(source: str, base: Path, path: Path, cache: dict[str, str]) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        rel = path.relative_to(base)
    except ValueError:
        rel = Path(path.name)
    key = f"{source}/{rel.as_posix()}"
    if key not in cache:
        target = ASSETS / source / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(path, target)
        cache[key] = f"../assets/{source}/{rel.as_posix()}"
    return cache[key]


def resolve_local(source: str, base: Path, ref: str, cache: dict[str, str]) -> str | None:
    raw = unquote(ref.split("?", 1)[0].split("#", 1)[0]).replace("\\", "/")
    if not raw or raw.startswith(("data:", "http:", "https:", "//", "mailto:")):
        return None
    candidates = []
    clean = raw.lstrip("./")
    candidates.append(base / clean)
    candidates.append(base / "images" / Path(clean).name)
    candidates.append(base / Path(clean).name)
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return copy_asset(source, base, candidate, cache)
    # Last chance: locate by basename in the source tree (mirrors often flatten paths).
    name = Path(clean).name
    if name:
        found = next(base.rglob(name), None)
        if found and found.is_file():
            return copy_asset(source, base, found, cache)
    return None


def strip_comments_and_chrome(soup: BeautifulSoup) -> None:
    for node in soup.find_all(string=lambda text: isinstance(text, Comment)):
        node.extract()
    for tag in soup.select("script, style, noscript, form, nav, .sidebar, .navbar, .noprint, .printfooter, #p-search, #mw-head, #mw-panel"):
        tag.extract()
    for card in soup.find_all(class_=lambda value: value and "card" in str(value).split()):
        header = card.find(class_=lambda value: value and "card-header" in str(value).split())
        if header and re.search(r"留言|评论|讨论|comment|guestbook", header.get_text(" ", strip=True), re.I):
            card.extract()
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        if re.search(r"留言|评论|讨论|comment|guestbook", heading.get_text(" ", strip=True), re.I):
            parent = heading.parent
            if parent and parent.name in {"section", "div", "article"}:
                parent.extract()
            else:
                heading.decompose()


def select_content(soup: BeautifulSoup):
    return soup.select_one(".mw-parser-output") or soup.select_one(".main") or soup.find("article") or soup.body or soup


def normalise_html(source: str, base: Path, raw: str, asset_cache: dict[str, str], link_map: dict[str, str]) -> tuple[str, str]:
    soup = BeautifulSoup(raw, "html.parser")
    title = clean_title(soup.title.get_text(" ", strip=True) if soup.title else "")
    content = select_content(soup)
    strip_comments_and_chrome(content)
    for tag in content.find_all(True):
        # Keep semantic content and table structure, discard archived site chrome/styles.
        allowed = {"href", "src", "alt", "title", "colspan", "rowspan", "target", "rel", "width", "height"}
        for attr in list(tag.attrs):
            if attr not in allowed:
                del tag.attrs[attr]
        if tag.name == "img":
            tag["loading"] = "lazy"
            src = tag.get("src", "")
            mapped = resolve_local(source, base, src, asset_cache)
            if mapped:
                tag["src"] = mapped
        if tag.name == "a":
            href = tag.get("href", "")
            if href and not href.startswith(("#", "http:", "https:", "mailto:", "javascript:")):
                clean = unquote(href.split("?", 1)[0].split("#", 1)[0]).replace("\\", "/")
                rel = Path(clean).name
                target = link_map.get(f"{source}:{rel}") or link_map.get(f"{source}:{clean.lstrip('./')}")
                if target:
                    tag["href"] = f"../pages/{target}"
                else:
                    tag["href"] = "#"
            elif href.startswith(("http:", "https:")):
                tag["target"] = "_blank"
                tag["rel"] = "noopener noreferrer"
    text = re.sub(r"\s+", " ", content.get_text(" ", strip=True))
    return title, str(content), text


def wiki_to_html(text: str) -> str:
    text = html.escape(text or "")
    text = re.sub(r"^={2,6}\s*(.*?)\s*={2,6}$", r"<h2>\1</h2>", text, flags=re.M)
    text = re.sub(r"'''(.*?)'''", r"<strong>\1</strong>", text)
    text = re.sub(r"''(.*?)''", r"<em>\1</em>", text)
    text = re.sub(r"\[\[(?:文件|File):([^\]|]+)(?:\|[^\]]*)?\]\]", r"<span class=\"attachment\">附件：\1</span>", text, flags=re.I)
    text = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: f'<a href="#">{m.group(2) or m.group(1)}</a>', text)
    text = re.sub(r"(https?://[^\s<]+)", r'<a href="\1" target="_blank" rel="noopener noreferrer">\1</a>', text)
    blocks = []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue
        if block.startswith("<h2>"):
            blocks.append(block)
        else:
            blocks.append("<p>" + block.replace("\n", "<br>") + "</p>")
    return "\n".join(blocks)


def extract_entries():
    info = source_info()
    entries = []
    # Main mirrored wiki.
    for path in sorted(info["esu"]["base"].glob("*.html")):
        if path.name.lower() in {"index.html", "404.html"}:
            continue
        entries.append({"source": "esu", "base": info["esu"]["base"], "path": path, "rel": path.name})
    # Red-bank mirrors; de-duplicate identical archived pages by title+body hash later.
    for key in ("red", "red-archive"):
        for path in sorted(info[key]["base"].rglob("*.html")):
            if path.name in {"index.html", "index-2.html", "newslist.html", "sblist.html", "email-protection.html"}:
                continue
            entries.append({"source": key, "base": info[key]["base"], "path": path, "rel": path.relative_to(info[key]["base"]).as_posix()})
    # MediaWiki XML dump contains the newer test wiki's actual page revisions.
    xml_path = info["esutest"]["base"] / "esutestmirahezeorg_w-20200828-history.xml"
    if xml_path.exists():
        root = ET.parse(xml_path).getroot()
        for page in root.findall(".//page"):
            title = (page.findtext("title") or "").strip()
            revision = page.find("revision")
            text = revision.findtext("text") if revision is not None else ""
            if not title or is_comment_title(title) or not (text or "").strip() or (text or "").strip() in {"<comments />", "<comments/>"}:
                continue
            entries.append({"source": "esutest", "base": info["esutest"]["base"], "path": xml_path, "rel": f"xml/{title}", "wiki_title": title, "wiki_text": text or ""})
    return entries


def page_shell(title: str, body: str, source: str = "") -> str:
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · 中国人Wiki</title><link rel="stylesheet" href="../style.css"></head>
<body><header class="site-header"><a class="brand" href="../index.html">中国人Wiki</a><a class="back" href="../index.html">返回目录</a><a class="edit-link" href="../admin.html">编辑</a></header>
<main class="page-wrap"><article class="article"><div class="eyebrow">{html.escape(source)}</div><h1>{html.escape(title)}</h1><div class="article-body">{body}</div></article></main>
<script src="../app.js"></script></body></html>'''


def build():
    if PAGES.exists():
        shutil.rmtree(PAGES)
    if ASSETS.exists():
        shutil.rmtree(ASSETS)
    PAGES.mkdir(parents=True)
    ASSETS.mkdir(parents=True)
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    entries = extract_entries()
    info = source_info()
    link_map: dict[str, str] = {}
    provisional = []
    for item in entries:
        if item.get("wiki_title"):
            title = item["wiki_title"]
        else:
            raw = item["path"].read_text(encoding="utf-8", errors="replace")
            title = clean_title(BeautifulSoup(raw, "html.parser").title.get_text(" ", strip=True) if BeautifulSoup(raw, "html.parser").title else Path(item["rel"]).stem)
        if is_comment_title(title):
            continue
        slug = slug_for(item["source"], item["rel"], title)
        link_map[f"{item['source']}:{Path(item['rel']).name}"] = slug
        link_map[f"{item['source']}:{item['rel']}"] = slug
        item["title"] = title
        item["slug"] = slug
        provisional.append(item)
    asset_cache: dict[str, str] = {}
    search = []
    seen_hashes = set()
    for item in provisional:
        if item.get("wiki_title"):
            body = wiki_to_html(item.get("wiki_text", ""))
            text = re.sub(r"\s+", " ", BeautifulSoup(body, "html.parser").get_text(" ", strip=True))
        else:
            raw = item["path"].read_text(encoding="utf-8", errors="replace")
            title, body, text = normalise_html(item["source"], item["base"], raw, asset_cache, link_map)
        digest = hashlib.sha1((item["title"] + "\n" + text).encode("utf-8", "ignore")).hexdigest()
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        source_label = info[item["source"]]["label"]
        (PAGES / item["slug"]).write_text(page_shell(item["title"], body, source_label), encoding="utf-8")
        search.append({"title": item["title"], "source": source_label, "url": f"pages/{item['slug']}", "text": text[:1800]})
    search.sort(key=lambda x: x["title"])
    (OUT / "search-index.json").write_text(json.dumps(search, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # Copy representative favicon/attachment files not referenced inline, preserving the original asset set.
    for key, data in info.items():
        for folder in (data["base"] / "images",):
            if folder.exists():
                for file in folder.rglob("*"):
                    if file.is_file():
                        copy_asset(key, data["base"], file, asset_cache)
    write_front_page(len(search), {k: sum(1 for x in search if x["source"] == v["label"]) for k, v in info.items()})
    print(f"Built {len(search)} entries and {len(asset_cache)} assets")


def write_front_page(total: int, counts: dict[str, int]):
    cards = "".join(f'<a class="source-card" href="#source-{i}"><span>{html.escape(info["label"])}</span><strong>{counts.get(i, 0):,}</strong><small>篇词条</small></a>' for i, info in source_info().items())
    body = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>合并 Wiki · 静态知识库</title><link rel="stylesheet" href="style.css"></head><body>
<header class="hero"><div class="hero-inner"><div class="eyebrow">STATIC KNOWLEDGE ARCHIVE</div><h1>合并 Wiki</h1><p>把分散的镜像词条整理成一个安静、可检索的本地知识库。</p><div class="search-box"><label for="search">搜索词条</label><input id="search" type="search" autocomplete="off" placeholder="输入关键词，支持模糊匹配…"><span id="search-count"></span></div></div></header>
<main class="home-wrap"><section class="intro"><div><span class="eyebrow">ARCHIVE INDEX</span><h2>内容目录</h2><p>共收录 <b>{total:,}</b> 篇去重后的词条。搜索会同时匹配标题、来源和正文摘要。</p></div><div class="legend">不包含留言、评论区、讨论页与留言板</div></section><section class="source-grid">{cards}</section><section id="results" class="results"><div class="result-head"><h2>全部词条</h2><span id="result-status">按标题排序</span></div><div id="result-list" class="result-list"></div></section></main><footer>静态归档 · 适用于 GitHub Pages / GitLab Pages</footer><script src="app.js"></script></body></html>'''
    (OUT / "index.html").write_text(body, encoding="utf-8")


if __name__ == "__main__":
    build()
