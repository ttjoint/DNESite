# 中国人Wiki

这是一个由多个本地 Wiki 镜像合并生成的静态知识库，支持 GitHub Pages 等静态托管，也支持管理者在本地编辑。

## 项目结构

```text
NewSite/
├─ index.html          # 首页、搜索、排序和标签筛选
├─ pages/              # 词条 HTML 页面
├─ assets/             # 原始图片和附件
├─ search-index.json   # 首页搜索索引
├─ metadata.json       # 标签、录入日期和编辑元数据
├─ style.css           # 全站视觉样式与夜间模式变量
├─ app.js              # 主题切换、搜索和阅读页逻辑
├─ admin.html          # 本地管理界面
├─ admin.js            # 源码编辑、实时预览和保存操作
├─ admin.css           # 管理界面样式
├─ local_server.py     # 本地文件读写 API
├─ build.py            # 从原始镜像重新构建站点
├─ convert_simple.py    # 将可安全转换的 HTML 词条转为 MediaWiki 源码
└─ upgrade_site.py     # 生成标签和录入日期元数据
```

## MediaWiki 源码支持

管理端编辑器保存的是 MediaWiki 风格源码，预览和保存页面使用同一个解析器。当前覆盖词条中最常用的语法：

- `== 标题 ==` 至 `====== 六级标题 ======`，并自动生成可跳转的 `section-...` 锚点
- `'''粗体'''`、`''斜体''`、`'''''粗斜体'''''`、`----`、`*`/`#` 列表
- `[[词条]]`、`[[词条|显示文字]]`、带章节的词条链接，以及 `[https://... 显示文字]`
- `{| ... |}` 表格（表头、`rowspan`/`colspan`、caption、File 图片）
- `<poem>`、`<nowiki>`、`<pre>`、`<syntaxhighlight>`、`<source>`、`<code>`、`<math>`、`<gallery>`
- `<ref>...</ref>`、命名引用、`<references />`、`<br />`、`<center>`、`<blockquote>` 等扩展标签
- `{{来源请求}}`、`{{主条目|...}}` 等常见模板的安全显示 fallback

模板递归展开、Lua 模块、复杂参数解析和服务器端扩展不属于静态页面能力；未识别模板会以文本标记显示，不会执行任意代码。

## 两种运行方式

静态阅读：直接打开 `index.html`，或部署到 GitHub Pages。此模式只提供阅读、搜索、排序和标签筛选。

本地管理：在 `NewSite` 目录运行：

```powershell
python local_server.py
```

然后访问 `http://127.0.0.1:8765/admin.html`。管理端支持查询、创建、编辑、删除词条，编辑 MediaWiki 风格源码并实时预览。保存直接写入本地文件，不会执行 Git 操作；删除的文件会移动到 `.trash/`。

## 主题模式

首次访问时根据系统 `prefers-color-scheme` 自动选择白天或夜间模式。点击页面右上角的主题按钮后，选择会保存到浏览器 `localStorage`，后续页面沿用该选择。

## 重新构建

当原始镜像发生变化时，可运行 `python build.py` 重新生成页面和附件，再运行 `python upgrade_site.py` 更新标签及录入日期元数据；如需再次把可转换的 HTML 词条转为源码，最后运行 `python convert_simple.py`。

对于已有 HTML 词条，可运行 `python convert_simple.py`。脚本会把标题、段落、列表、链接、图片、粗斜体和简单表格转换为 MediaWiki 源码；复杂布局、视频、音频、脚本和超大页面会保留 HTML，并在 `metadata.json` 中标记为 `format: "html"`。

项目不包含留言、评论区、讨论页或留言板。
