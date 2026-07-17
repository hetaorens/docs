# docs

本仓库用于把本地 Markdown 文档自动构建成适合墨水屏阅读的 PDF，并生成 RSS feed。

## 使用方式

1. 把文章放到 `docs/` 目录，文件扩展名使用 `.md`。
2. 每篇文章建议添加 front matter：

```markdown
---
title: 我的文章标题
date: 2026-07-17
tags: [reading, note]
---

正文内容...
```

3. 推送到 GitHub 后，GitHub Actions 会自动生成：

- `dist/articles/*.html`
- `dist/pdf/*.pdf`
- `dist/feed.xml`
- `dist/index.html`

4. 在 GitHub 仓库 `Settings -> Pages` 中选择 `GitHub Actions` 作为发布源。

发布后常用地址：

- 首页：`https://hetaorens.github.io/docs/`
- RSS：`https://hetaorens.github.io/docs/feed.xml`
- PDF：`https://hetaorens.github.io/docs/pdf/<article>.pdf`

## 本地构建

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build.py
```

生成结果会放在 `dist/` 目录。
