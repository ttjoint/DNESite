from pathlib import Path
from bs4 import BeautifulSoup
from datetime import date
import json, re

ROOT = Path(__file__).resolve().parent
tags = {
    "人物": ("姓名", "个人", "先生", "女士", "UP主", "SCP-ZHINA", "出生", "身份证"),
    "文章": ("正文", "作者", "报告", "声明", "教程", "研究", "小说", "事件"),
    "组织": ("公司", "基金会", "协会", "组织", "团队", "联盟", "社群"),
    "概念": ("什么是", "定义", "概念", "主义", "理论", "简史", "科普"),
}
records = []
for page in sorted((ROOT / "pages").glob("*.html")):
    soup = BeautifulSoup(page.read_text(encoding="utf-8", errors="replace"), "html.parser")
    article = soup.select_one(".article")
    if not article: continue
    title = (article.find("h1").get_text(" ", strip=True) if article.find("h1") else page.stem)
    body = article.select_one(".article-body")
    text = body.get_text(" ", strip=True) if body else ""
    if not body or not text.strip():
        continue
    chosen = [name for name, markers in tags.items() if any(m.lower() in (title + " " + text).lower() for m in markers)]
    if not chosen: chosen = ["文章"]
    records.append({"slug": page.name, "title": title, "tags": chosen, "date": date.today().isoformat(), "source": "", "body": body.decode_contents() if body else "", "text": re.sub(r"\s+", " ", text)[:1800]})
(ROOT / "metadata.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"metadata: {len(records)}")
