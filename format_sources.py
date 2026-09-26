"""Format generated HTML and the small hand-written asset files for contributors."""
from pathlib import Path
from bs4 import BeautifulSoup
import re

ROOT = Path(__file__).resolve().parent

def format_html(path: Path) -> None:
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    path.write_text(soup.prettify(formatter="html"), encoding="utf-8")

def format_css(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\s*\{\s*", " {\n", text)
    text = re.sub(r";\s*", ";\n  ", text)
    text = re.sub(r"\s*\}\s*", "\n}\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    path.write_text(text.strip() + "\n", encoding="utf-8")

for page in (ROOT / "pages").glob("*.html"):
    format_html(page)
for page in (ROOT / "*.html").parent.glob("*.html"):
    format_html(page)
format_css(ROOT / "style.css")
format_css(ROOT / "admin.css")
print("Formatted HTML pages and CSS assets")
