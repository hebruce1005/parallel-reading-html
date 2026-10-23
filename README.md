# Parallel Reading HTML

将英文论文或著作章节制作成适合渐进式阅读的中英双语 Markdown 和 HTML，并保留与原 PDF 对应的页面锚点。

中文承载句法和语义骨架，英文保留有学习价值的完整术语、搭配与论证表达。它是供 AI 助手执行的 skill：Python 脚本负责解析、导入、构建和检查，双语内容由助手依照 `SKILL.md` 编写；仅运行解析脚本不会自动生成译文。

## 能做什么

- 通过 PaddleOCR 异步 API 解析 PDF，或复用已有的兼容 JSON／带页码 Markdown。
- 输出逐 block 对应的双语 Markdown 和可独立打开的 HTML。
- 保留零起始文件页码与原 PDF 的 MD5，供 Zotero Parallel Reader 按按钮定位原文和译文；不是持续滚动同步。
- 在摘要前只显示题目与作者，将学术脚注汇集到文末，以原 PDF 截图呈现图表。
- 支持长篇文献按文件页范围分轮交付，并保留全书页面映射。

## 安装

下载本仓库并将文件夹命名为 `parallel-reading-html`，放入所用 AI 助手支持的 skill 目录，或让助手直接读取这个文件夹中的 `SKILL.md`。保留 `references/`、`scripts/` 及其内部目录结构。

在仓库根目录创建 Python 3 虚拟环境并安装依赖。建议 Python 3.10 或更新版本；不同平台的实际可用版本还取决于 PyMuPDF 的安装支持。本仓库尚未进行跨平台测试。

macOS／Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell（无需激活环境）：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

后续命令中的 `python` 应使用此环境的解释器。Windows 可直接替换为 `.\.venv\Scripts\python.exe`。若助手运行在另一个终端或隔离环境中，应告知它该解释器的位置；不要假定它继承了当前终端环境。

## 配置 Paddle 令牌

只有调用 Paddle 解析服务时才需要令牌。先在服务提供方取得自己的访问令牌，再配置环境变量 `PADDLEOCR_ACCESS_TOKEN`。也可将令牌单独保存在用户目录下的 `.config/parallel-reading-html/paddle-token` 文件中；macOS／Linux 将文件权限设为 0600。

令牌文件应位于仓库之外，不要粘贴到 GitHub、截图或运行报告中。脚本不自动加载 `.env` 文件。

当没有兼容的既有解析结果时，脚本会将整份 PDF 上传到 `https://paddleocr.aistudio-app.com/api/v2/ocr/jobs`。服务访问、额度和费用以使用者的 Paddle 账户为准。复用既有解析结果的导入步骤不调用该服务。双语处理还可能由所用 AI 助手接收文档内容。

## 开始使用

向已加载此 skill 的助手提供 PDF，并说明：

> 使用 parallel-reading-html，将这份 PDF 制作成渐进式中英双语 Markdown 和 HTML。保留原 PDF 的页面映射，图表使用原文截图。

如果需要先审阅译文，可补充：

> 先交付 Markdown，等我确认后再生成 HTML。

只有 PDF 时，解析入口为：

```bash
python scripts/parse_paddle.py /path/to/source.pdf --workdir work/paper --max-seconds 900
```

如果已有兼容的 JSON 或带文件页标记的 Markdown：

```bash
python scripts/import_source.py /path/to/source.json --pdf /path/to/source.pdf --workdir work/paper
```

这些命令只完成解析或导入。随后由助手依照 [SKILL.md](SKILL.md) 完成样本校准、逐 block 双语编写、配置、审计、构建与验证。输入规范见 [input-formats.md](references/input-formats.md)，任务续查和 API 说明见 [paddle-api.md](references/paddle-api.md)。

单篇配置从 `scripts/assets/paper.example.json` 复制，并根据实际文档填写；其中的 block ID、术语与结论均是示例，不能直接套用到论文。

## 阅读与 Zotero 定位

生成的 HTML 可以直接用浏览器阅读。要与原 PDF 按页联动，需要另行安装兼容的 Zotero Parallel Reader 插件，本仓库不包含插件安装包。

页面映射要求打开生成时使用的同一份 PDF。脚本验证的是页面、指纹和 block 结构，不能代替双语内容核对，也不代表已验证用户端 Zotero 按钮的实际行为。文末脚注区域的原文定位需在实际插件中确认。

## 文件结构

```text
parallel-reading-html/
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── SKILL.md
├── references/
│   ├── input-formats.md
│   └── paddle-api.md
└── scripts/
    ├── parse_paddle.py
    ├── import_source.py
    ├── extract.py
    ├── extract_paddle.py
    ├── audit.py
    ├── build.py
    ├── overview.py
    ├── verify.py
    └── assets/
        ├── reading.css
        └── paper.example.json
```

运行缓存、原始阅读材料、译文、API 返回结果和日志应留在本地工作目录。`work/`、`outputs/`、虚拟环境和常见凭据文件已加入 `.gitignore`。网页手动上传时也应自行排除这些文件；忽略规则不是网页上传的隐私过滤器。

## 许可证

本仓库代码与说明采用 [MIT License](LICENSE)，署名为 `hebruce1005`。输入文献、生成内容所引用的原文图表以及外部依赖不因此改变其各自的权利或许可条件。
