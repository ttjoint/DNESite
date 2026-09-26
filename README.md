# 合并 Wiki 静态站点

这是由 `esu-main`、`red-bank-main`、`simafive-master/Red` 和 `simafive-master/esutest` 本地镜像合并生成的中国人Wiki项目。

- `index.html`：入口页与客户端模糊搜索
- `pages/`：去重后的词条页面
- `assets/`：从原始镜像复制的图片与附件
- `search-index.json`：搜索索引
- `metadata.json`：标签、录入日期和本地编辑元数据
- `admin.html`：本地管理界面
- `local_server.py`：本地编辑 API 服务
- `build.py`：可重复执行的构建脚本

`react-esuwiki-main` 目录经检查是 React 源码仓库（不是词条数据），因此没有把其中的开发文件混入内容库。

本项目不包含留言、评论区、讨论页或留言板。静态部署时页面只读；需要编辑时在 `NewSite` 目录运行 `python local_server.py`，然后打开 `http://127.0.0.1:8765/admin.html`。保存会直接写入本地 `pages/` 和 `metadata.json`，删除的文件会移动到 `.trash/`，不执行 Git 推送。
