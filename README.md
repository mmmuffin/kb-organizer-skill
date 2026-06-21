# knowledge-base-organizer

一个用于**知识库整理与本地化**的 Codex Skill。  
它的目标不是直接回答知识库问题，而是把一个原始知识源整理成一个适合后续检索的本地知识包。

支持两类输入：
- 本地文件夹
- 在线文档站

支持的核心能力：
- 保留原始来源
- 规范化正文为 Markdown
- 生成目录索引 `data_structure.md`
- 生成文档清单 `manifest.json`
- 生成图片清单 `image_manifest.json`
- 为图片生成 OCR sidecar 文本
- 为后续 MCP 检索或 skill-first 检索准备统一输出结构

## 适用场景

适合下面这类需求：

- “把一个在线文档站落地成本地知识库”
- “把一个混乱的本地资料夹整理成便于检索的知识包”
- “给后续 MCP、RAG 替代方案、检索 Skill 做前置治理”
- “知识库里有图片，需要后续能靠 OCR 和上下文召回”

不适合直接拿来做：

- 在线问答 agent
- 向量数据库本身
- 登录态很重的私有站点自动化抓取
- 复杂图表语义理解

## 仓库结构

本仓库把**GitHub 说明**和**真实 Skill 目录**分开：

```text
.
├── README.md
└── knowledge-base-organizer/
    ├── SKILL.md
    ├── agents/
    ├── references/
    └── scripts/
```

其中：
- 根目录 `README.md` 是给 GitHub 使用者看的
- `knowledge-base-organizer/` 才是实际的 Skill 目录

## 安装方式

将 `knowledge-base-organizer/` 目录复制到你的 Codex skills 目录即可：

```bash
cp -R knowledge-base-organizer "${CODEX_HOME:-$HOME/.codex}/skills/"
```

安装后，Codex 就可以通过 Skill 触发词使用它。

## Skill 做什么

这个 Skill 的职责是：

1. 识别输入源类型
2. 把输入源整理到一个新的输出目录
3. 保留原始来源副本
4. 把正文转成适合后续检索的 Markdown
5. 处理图片与 OCR 元数据
6. 生成目录索引和结构化 manifest

它不会默认改动原始知识库。

## 处理流程

### 1. 本地文件夹输入

当输入是本地目录时，Skill 会：

- 递归扫描文件
- 识别常见格式：
  - `md`
  - `txt`
  - `html`
  - `pdf`
  - `docx` / `rtf`
  - `csv`
  - `xlsx`
  - 常见图片格式
- 保留原始文件到 `originals/local/`
- 把可提取正文的内容写到 `normalized/`
- 把图片单独保存到 `images/`
- 为图片生成 OCR 文本到 `ocr/`
- 生成索引与清单

### 2. 在线文档站输入

当输入是在线文档站时，Skill 会：

- 优先尝试 sitemap
- 无 sitemap 时在同站点内做有限 crawl
- 下载页面原始 HTML 到 `originals/web/`
- 提取页面主内容，转为 Markdown 到 `normalized/`
- 下载页面中的内容图片
- 为图片生成 OCR sidecar
- 记录页面原始 URL，供后续回答时引用

## 输出目录结构

Skill 默认输出一个新的知识包目录，结构类似：

```text
<organized-kb>/
  data_structure.md
  manifest.json
  image_manifest.json
  source_map.json
  run_report.json
  normalized/
    <domain>/
      data_structure.md
      *.md
  originals/
    local/...
    web/...
  images/
  ocr/
```

各部分含义：

- `normalized/`
  - 后续检索最常读的规范化正文
- `originals/`
  - 原始来源保留区，便于追溯
- `images/`
  - 图片本体
- `ocr/`
  - 图片 OCR 文本 sidecar
- `manifest.json`
  - 文档级元数据
- `image_manifest.json`
  - 图片级元数据
- `source_map.json`
  - 源路径/源 URL 与整理后文件之间的映射
- `run_report.json`
  - 本次整理运行报告，包括失败、跳过、统计

## 图片与 OCR

这个 Skill 把图片视为**一等知识资源**，不会把它们当成可忽略附件。

第一版的图片处理策略是：

- 保留图片文件
- 记录来源 URL 或原始路径
- 记录所属文档
- 记录标题/alt 文本/文件名
- 记录周边上下文片段
- 尝试生成 OCR 文本

OCR 是**可插拔后端**，策略如下：

1. 如果显式指定后端，就优先使用指定后端
2. 否则优先尝试 `pytesseract`
3. 再尝试 `tesseract` CLI
4. 如果没有 OCR 能力，记录为 `unavailable`

注意：
- 即使 OCR 失败，也不会丢弃图片
- 图片仍会进入 `image_manifest.json`
- 失败原因会写入 `run_report.json`

第一版**不做复杂图意理解**，也就是：
- 不强制解释图表趋势
- 不单独生成“图片语义摘要”
- 主要依赖 OCR + 周边上下文进行后续召回

## 与后续检索的关系

这个 Skill 不是检索层，而是**前置治理层**。

它整理好的知识包，适合被两类下游能力消费：

### 1. Skill-first 检索

例如：
- `kb-retriever`
- 目录树 + `data_structure.md` 的分层检索方式

### 2. MCP 检索

例如你后续封装的：
- `search_docs`
- `read_doc`
- `search_images`
- `read_image_ocr`

也就是说，这个 Skill 负责：

**知识落地与结构化**

后续 Skill 或 MCP 负责：

**知识检索与问答**

## 运行脚本

核心脚本：

```bash
python3 knowledge-base-organizer/scripts/organize_kb.py \
  --input /absolute/path/to/source-folder \
  --output /absolute/path/to/organized-kb \
  --mode local
```

在线文档站示例：

```bash
python3 knowledge-base-organizer/scripts/organize_kb.py \
  --input https://docs.example.com/start-page \
  --output /absolute/path/to/organized-kb \
  --mode web \
  --crawl-limit 40
```

常用参数：

- `--input`
  - 输入源，文件夹路径或网站 URL
- `--output`
  - 输出知识包目录
- `--mode auto|local|web`
  - 输入模式
- `--ocr-backend`
  - OCR 后端，默认 `auto`
- `--sitemap-url`
  - 可选 sitemap
- `--crawl-limit`
  - 限制网页抓取数

## 参考文档

Skill 内部还带了这些参考说明：

- `references/output-schema.md`
- `references/local-normalization.md`
- `references/web-ingestion.md`
- `references/image-handling.md`
- `references/ocr-backends.md`

这些文档分别定义：
- 输出结构契约
- 本地文件归一化规则
- 在线文档抓取规则
- 图片处理规则
- OCR 后端契约

## 已知限制

当前版本的已知边界：

- 不内置登录态网站自动化
- 不保证所有 PDF 在无外部解析库时都能成功提取
- 不保证所有 DOCX/PDF 内嵌图片都能完整抽取
- 不做复杂图表/架构图语义理解
- 不默认原地改写源知识库

## 推荐使用方式

建议按这个顺序使用：

1. 用 `knowledge-base-organizer` 整理知识源
2. 输出标准化本地知识包
3. 基于这个知识包再做：
   - MCP
   - 检索 Skill
   - 问答 Agent

也就是：

**知识治理 -> 检索能力 -> Agent**

## 许可证与后续扩展

如果你打算把它继续做成团队可复用的方案，下一步最值得扩展的是：

- 登录态站点同步
- 更强的 PDF 解析
- 可插拔 OCR 后端管理
- 图片语义摘要
- 内嵌图片抽取
- 直接生成 MCP 模板

---

如果你是从 GitHub 下载这个仓库，请记住：  
真正要安装到 Codex 的目录是：

`knowledge-base-organizer/`
