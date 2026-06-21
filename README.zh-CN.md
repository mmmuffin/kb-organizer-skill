# knowledge-base-organizer

> 把在线文档站或本地资料夹，整理成一个适合后续检索、MCP 封装和 Agent 问答的本地知识包。

这是一个面向 Codex 的知识库整理 Skill。  
它不负责直接回答知识库问题，而是负责把原始知识源整理成一个**可检索、可追溯、可继续封装**的本地知识包。

当前版本的核心方向是：

- 默认走轻量方案，而不是重型默认
- 在新设备上尽量做到“装上 skill 就能开始”
- 对图片和 PDF 保持可追溯、可召回
- 缺依赖时优先提示并自举安装，失败时允许降级继续
- 对图文关系做更完整的保留，而不是只保存散落文件

---

## 这版解决了什么问题

之前的方案有两个明显问题：

1. OCR / PDF 处理链路偏重
2. 在全新设备上，脚本可能因为缺依赖而根本起不来

同时还有一个更关键的问题：

3. 文档和图片之间的关系不够完整，后续检索时图片容易变成“孤儿资源”

这版重构后，默认行为改成：

- 默认 OCR 档位：`mobile`
- 默认依赖策略：缺失时**展示安装计划并确认后安装**
- 默认失败策略：**降级继续**，而不是直接把整个知识包整理流程打断

也就是说，你现在可以把它理解成一个：

**“新设备优先、轻量优先、但仍保留图片/PDF 召回能力”的知识库整理 Skill。**

并且现在还补上了一个更重要的点：

**图文混合知识库里，文档和图片之间的召回关系会尽量被保留下来。**

---

## 仓库结构

本仓库采用“仓库根目录就是 Skill 根目录”的结构：

```text
.
├── README.md
├── README.zh-CN.md
├── SKILL.md
├── manifest.json
├── agents/
│   └── openai.yaml
├── references/
│   ├── capability-matrix.md
│   ├── image-handling.md
│   ├── local-normalization.md
│   ├── ocr-backends.md
│   ├── output-schema.md
│   └── web-ingestion.md
└── scripts/
    ├── bootstrap_env.py
    └── organize_kb.py
```

安装时复制整个仓库目录即可。

---

## 安装

把整个仓库目录复制到你的 Codex skills 目录，并命名为 `knowledge-base-organizer`：

```bash
cp -R . "${CODEX_HOME:-$HOME/.codex}/skills/knowledge-base-organizer"
```

---

## 推荐启动方式

### 1. 先看当前设备缺什么

```bash
python3 scripts/organize_kb.py --check-deps
```

这个命令会输出：

- Python 依赖状态
- 系统依赖状态
- 当前设备是否具备：
  - 文本知识库整理能力
  - 文本 PDF 提取能力
  - 图片 OCR 能力
  - 扫描 PDF OCR 能力

### 2. 直接开始整理知识库

本地目录：

```bash
python3 scripts/organize_kb.py \
  --input /absolute/path/to/source-folder \
  --output /absolute/path/to/organized-kb \
  --mode local \
  --ocr-profile mobile
```

在线文档站：

```bash
python3 scripts/organize_kb.py \
  --input https://docs.example.com/start-page \
  --output /absolute/path/to/organized-kb \
  --mode web \
  --ocr-profile mobile \
  --crawl-limit 40
```

---

## 全新设备上的默认行为

现在的默认行为是：

- `--ocr-profile mobile`
- `--install-missing prompt`

含义是：

- 如果你的终端是交互式终端
  - Skill 会先展示准备执行的安装计划
  - 然后询问你是否继续
  - 你确认后，它会自动安装推荐依赖并继续执行整理

- 如果你的终端是非交互式环境
  - Skill 不会静默自动安装
  - 会直接进入降级模式
  - 然后尽量继续整理可处理的内容

这套策略的目的很明确：

- 对个人机器和普通 VPS 尽量友好
- 不偷偷修改用户环境
- 又不让缺依赖时整个任务直接报废

---

## 一键补齐环境

如果你想先把环境补齐，再运行整理命令，可以手动执行：

```bash
python3 scripts/bootstrap_env.py --profile mobile
```

用于 CI 或明确知道要自动执行时：

```bash
python3 scripts/bootstrap_env.py --profile mobile --yes
```

### `bootstrap_env.py` 做什么

在 `mobile` 档位下，它会安装：

- core Python 依赖
  - `pandas`
  - `requests`
  - `beautifulsoup4`
  - `pillow`
  - `pypdf`
  - `openpyxl`
  - `lxml`
- OCR 运行时
  - `paddlepaddle` CPU 版
  - `paddleocr`
- PDF 工具
  - `poppler`

系统路径：

- macOS：`brew install poppler`
- Ubuntu：`sudo apt-get install -y poppler-utils`

默认**不安装 `tesseract`**。  
它只保留为可选 fallback，而不是默认栈的一部分。

---

## OCR 档位

### `none`

适合：

- 纯文本型知识库
- 你明确接受图片/PDF 召回能力变弱

特点：

- 不保证图片 OCR
- 不保证扫描 PDF OCR
- 图片仍然会保留并进入 `image_manifest.json`

### `mobile`

这是默认档位，也是推荐档位。

适合：

- 新设备
- 普通本机
- Ubuntu VPS
- 图片不少，但不想上重型 OCR 默认配置的知识库

默认模型：

- `PP-OCRv5_mobile_det`
- `PP-OCRv5_mobile_rec`

这是当前最合理的平衡点：

- 比 server 轻
- 比 no-OCR 强
- 足以支持大部分文档截图、界面图、参数图、扫描 PDF 页面

### `server`

适合：

- 你明确要更高 OCR 精度
- 能接受更大的模型、更慢的运行、更高的资源占用

不是默认档位。

---

## PDF 和图片的处理策略

### 文本型 PDF

处理顺序：

1. `pdftotext`
2. `pypdf`

也就是说，优先用 Poppler 的文本提取路径。  
如果 Poppler 不可用，再走 Python 文本回退。

### 扫描型 PDF

处理顺序：

1. `pdftoppm` 把页面转成临时图片
2. 用当前 OCR 档位识别页图
3. 合并成可检索文本

注意：

- 页图只放临时目录
- 任务结束后会删除
- 不会长期堆在知识包里

### 图片

图片的处理原则是：

- 始终保留原图
- 尽量生成 OCR sidecar 文本
- 即使 OCR 失败，也不丢图片

如果图片原本就是文档的一部分，当前版本还会尽量保留这种关系：

- 文档里的 `related_images`
- 图片里的 `parent_document_id`
- 图片的 `context_excerpt`
- 规范化 Markdown/HTML 里的图片引用会改写到知识包内部的 `images/` 路径

---

## 后续 AI 是怎么知道该召回什么的

这是这个 Skill 的关键设计点。

后续检索层不应该只靠 OCR 文本召回图片，而是应该综合使用：

- `image_manifest.json`
- `parent_document_id`
- `title_or_alt`
- `context_excerpt`
- `source_uri`
- OCR sidecar 文本

也就是说：

- OCR 是增强项
- 图片元数据和上下文同样重要
- 即使 OCR 不可用，AI 依然能“知道这张图属于哪篇文档、讲的是什么上下文、应不应该被召回”

这就是为什么这个 Skill 不是简单地“做个 OCR”，而是要把图片作为一等资源保存下来。

在当前版本里，这条链路已经比之前完整很多。对于本地 Markdown、HTML 这类常见知识源，Skill 会尽量做到：

1. 文档命中后，能顺着 `related_images` 找到相关图片
2. 图片命中后，能顺着 `parent_document_id` 回到父文档
3. 规范化后的文档图片链接，不会还是原始相对路径，而是会指向打包后的 `images/`

---

## 降级模式是什么意思

如果依赖没有装齐，或者你拒绝安装，或者安装失败，Skill 不会默认把整个任务打断。

它会尽量继续输出一个完整的知识包，但能力会下降。

### 降级后仍然会做的事

- 保留原始文件 / 原始 HTML
- 生成 `normalized/`
- 生成 `manifest.json`
- 生成 `image_manifest.json`
- 生成 `source_map.json`
- 生成 `run_report.json`

### 降级后可能变弱的事

- 图片没有 OCR sidecar
- 扫描 PDF 不能变成可检索文本
- 部分 PDF 只能保留原件，无法抽取正文

### `run_report.json` 会额外记录

- 当前 OCR profile
- 依赖检查结果
- capability matrix
- 是否是 degraded run
- 安装是否尝试过、是否成功

---

## 三档能力矩阵

### `none`

- 适合：纯文本型知识库
- 原生文本 PDF：弱支持，主要靠 `pypdf`
- 扫描 PDF：不支持 OCR
- 图片：保留，但不保证 OCR

### `mobile`

- 适合：默认使用场景
- 原生文本 PDF：强支持
- 扫描 PDF：支持 OCR
- 图片：支持 OCR 与召回元数据

### `server`

- 适合：重精度场景
- 原生文本 PDF：强支持
- 扫描 PDF：支持更重的 OCR 路径
- 图片：支持更重的 OCR 路径

更完整的能力说明见：

- [`references/capability-matrix.md`](./references/capability-matrix.md)

---

## 输出结构

标准输出结构：

```text
<organized-kb>/
  data_structure.md
  manifest.json
  image_manifest.json
  source_map.json
  run_report.json
  normalized/
  originals/
  images/
  ocr/
```

这些产物分别服务于：

- 目录式检索
- MCP 检索封装
- 后续 Agent 问答
- 来源追溯
- 图片召回

现在还可以更明确地理解成两条召回链：

- 文档 -> 图片
- 图片 -> 文档

这对于“请把那张架构图发给我”“哪张截图解释了这个流程”这类问题非常重要。

---

## 推荐的后续链路

```text
原始知识源
-> knowledge-base-organizer
-> 标准化本地知识包
-> retriever skill / MCP
-> 问答 Agent
```

职责分层仍然是：

- `knowledge-base-organizer`：整理
- retriever / MCP：检索
- Agent：回答

---

## 结论

这版 `knowledge-base-organizer` 的核心定位是：

**让一个新设备在默认轻量配置下，也能开始整理知识库；遇到图片和 PDF 时，尽量自动补齐 mobile 运行环境；即使补不齐，也能产出一个结构完整、图文关系尽量保留、后续可继续检索的知识包。**

如果你要做的是：

- 在线文档本地化
- 本地知识库整理
- 图片较多的知识库治理
- 为后续 MCP / retriever / Agent 做前置标准化

那么现在这版会比之前的“默认重型 OCR 路线”更适合作为第一步。
