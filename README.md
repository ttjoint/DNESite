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
└─ upgrade_site.py     # 生成标签和录入日期元数据
```

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

当原始镜像发生变化时，可运行 `python build.py` 重新生成页面和附件，再运行 `python upgrade_site.py` 更新标签及录入日期元数据。

项目不包含留言、评论区、讨论页或留言板。
