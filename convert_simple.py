"""Convert safe, simple migrated HTML entries to readable MediaWiki source."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag


ROOT = Path(__file__).resolve().parent
META = ROOT / "metadata.json"


def clean_text(value: str) -> str:
    return re.sub(r"[ \t\f\v]+", " ", value.replace("\xa0", " ")).strip()


def image_markup(node: Tag) -> str:
    src = unquote(str(node.get("src", "")))
    if not src or src.startswith(("http:", "https:", "data:")):
        return clean_text(node.get("alt", ""))
    name = Path(urlparse(src).path).name
    if not name:
        return clean_text(node.get("alt", ""))
    options = []
    width = node.get("width")
    if width and str(width).isdigit():
        options.append(f"{width}px")
    options.append(f"alt={clean_text(node.get('alt', '')) or name}")
    return f"[[File:{name}|{'|'.join(options)}]]"


def inline(node) -> str:
    if isinstance(node, NavigableString):
        return str(node).replace("\r", "").replace("\n", " ")
    if not isinstance(node, Tag):
        return ""
    name = node.name.lower()
    if name == "br":
        return "\n"
    if name == "img":
        return image_markup(node)
    if name in {"strong", "b"}:
        return "'''" + "".join(inline(child) for child in node.children).strip() + "'''"
    if name in {"em", "i"}:
        return "''" + "".join(inline(child) for child in node.children).strip() + "''"
    if name in {"del", "s", "strike"}:
        return "~~" + "".join(inline(child) for child in node.children).strip() + "~~"
    if name == "a":
        label = clean_text("".join(inline(child) for child in node.children))
        image = node.find("img", recursive=False)
        if image:
            return image_markup(image)
        href = unquote(str(node.get("href", ""))).strip()
        title = clean_text(str(node.get("title", "")))
        if href.startswith(("http://", "https://")):
            return f"[{href} {label or href}]"
        target = title or Path(urlparse(href).path).stem
        target = re.sub(r"\.(?:html?|php)$", "", target, flags=re.I).strip()
        if not target or target in {"#", "index"}:
            return label or href
        return f"[[{target}|{label}]]" if label and label != target else f"[[{target}]]"
    if name in {"code", "small", "big", "span", "font", "center"}:
        return "".join(inline(child) for child in node.children)
    if name == "blockquote":
        text = clean_text("".join(inline(child) for child in node.children))
        return "\n".join("> " + line for line in text.splitlines())
    return "".join(inline(child) for child in node.children)


def list_markup(node: Tag, marker: str) -> list[str]:
    lines = []
    for item in node.find_all("li", recursive=False):
        nested = item.find(["ul", "ol"], recursive=False)
        content = "".join(
            inline(child)
            for child in item.children
            if not (isinstance(child, Tag) and child.name in {"ul", "ol"})
        )
        content = clean_text(content)
        if content:
            lines.append(marker + " " + content)
        if nested:
            lines.extend(list_markup(nested, marker + ("#" if nested.name == "ol" else "*")))
    return lines


def table_markup(table: Tag) -> list[str]:
    classes = ["wikitable"]
    if "infobox" in {str(value).lower() for value in table.get("class", [])}:
        classes.append("infobox")
    lines = ['{| class="' + " ".join(classes) + '"' + (' style="float:right"' if "infobox" in classes else "")]
    caption = table.find("caption", recursive=False)
    if caption:
        lines.append("|+ " + clean_text(inline(caption)))
    for row in table.find_all("tr"):
        lines.append("|-")
        for cell in row.find_all(["th", "td"], recursive=False):
            prefix = "!" if cell.name == "th" else "|"
            attrs = []
            for attr in ("colspan", "rowspan"):
                if cell.get(attr):
                    attrs.append(f'{attr}="{html.escape(str(cell[attr]), quote=True)}"')
            value = clean_text(inline(cell))
            lines.append(f"{prefix} {' '.join(attrs) + ' | ' if attrs else ''}{value}")
    lines.append("|}")
    return lines


def block_nodes(root: Tag):
    """Unwrap mirror-specific section containers but keep real content blocks."""
    for node in root.children:
        if not isinstance(node, Tag):
            yield node
            continue
        classes = " ".join(node.get("class", []))
        if node.name == "div" and (
            classes.startswith("mf-section")
            or "mw-parser-output" in classes
            or (not node.get_text("", strip=True) and node.find(["table", "h2", "h3", "p"]))
        ):
            yield from block_nodes(node)
        else:
            yield node


def convert_body(body: str) -> str | None:
    soup = BeautifulSoup(body, "html.parser")
    tags = {tag.name.lower() for tag in soup.find_all(True)}
    blocked = {"iframe", "video", "audio", "svg", "script", "style", "form", "pre", "canvas"}
    if tags & blocked or len(soup.find_all(True)) > 150:
        return None
    root = soup.select_one(".mw-parser-output") or soup.body or soup
    parts: list[str] = []
    for node in block_nodes(root):
        if isinstance(node, NavigableString):
            if clean_text(str(node)):
                parts.append(clean_text(str(node)))
            continue
        if not isinstance(node, Tag):
            continue
        name = node.name.lower()
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = max(2, min(6, int(name[1])))
            parts.append("=" * level + " " + clean_text(inline(node)) + " " + "=" * level)
        elif name == "table":
            parts.extend(table_markup(node))
        elif name in {"ul", "ol"}:
            parts.extend(list_markup(node, "#" if name == "ol" else "*"))
        elif name == "hr":
            parts.append("----")
        elif name == "blockquote":
            parts.append(inline(node))
        elif name in {"p", "div", "section", "article"}:
            value = clean_text(inline(node))
            if value:
                parts.append(value)
        else:
            value = clean_text(inline(node))
            if value:
                parts.append(value)
    source = "\n\n".join(part.strip() for part in parts if part.strip()).strip()
    return source or None


def is_html_body(body: str) -> bool:
    return bool(re.search(r"<\/?[a-z][^>]*>", body or "", re.I))


def main() -> None:
    items = json.loads(META.read_text(encoding="utf-8"))
    converted = 0
    retained_html = 0
    for item in items:
        body = item.get("body", "")
        if not is_html_body(body):
            item["format"] = "wiki"
            item["text"] = re.sub(r"\s+", " ", re.sub(r"\[\[|\]\]|'{2,5}|==+|\{\{.*?\}\}|<[^>]+>", "", body)).strip()[:1800]
            continue
        source = convert_body(body)
        if source:
            item["body"] = source
            item["format"] = "wiki"
            item["text"] = re.sub(r"\s+", " ", re.sub(r"\[\[|\]\]|'{2,5}|==+|\{\{.*?\}\}|<[^>]+>", "", source)).strip()[:1800]
            converted += 1
        else:
            item["format"] = "html"
            retained_html += 1
    META.write_text(json.dumps(items, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"converted {converted}; retained complex HTML {retained_html}")


if __name__ == "__main__":
    main()
