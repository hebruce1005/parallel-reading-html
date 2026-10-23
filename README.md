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

## 配置 Paddle 令牌：首次使用照着做

访问令牌就是 AI Studio 提供的一长串数字和字母，相当于调用服务的账户钥匙。它用于身份认证和账户额度归属，文件上传到哪个接口、用哪个解析模型，由脚本另外指定。Paddle 令牌不能用于 MinerU，也不会决定译文的语言风格。

### 1. 获取自己的令牌

1. 打开 [PaddleOCR 官方体验页面](https://paddleocr.aistudio-app.com/)，登录自己的 AI Studio 账户。
2. 在 API 调用窗口选择 PaddleOCR-VL-1.6，并使用“我的 AI Studio 访问令牌”；点击“获取令牌”入口，复制自己的令牌。界面名称如有调整，以当前页面为准。
3. 只复制令牌字符串，不带 `TOKEN =`、引号、空格或换行。每位使用者配置自己的令牌。

官方“复制代码”用于展示 API 调用方式。本仓库已有 `scripts/parse_paddle.py`，无需用示例代码覆盖它，也无需把令牌写进 Python 源文件。复制的官方示例可能包含个人令牌，公开分享前应移除。

### 2. 推荐：保存到仓库外的本地配置文件

这种方式适合由桌面 AI 助手运行 skill：同一电脑、同一系统用户下，脚本可以直接读取文件，不依赖某个终端的临时环境变量。

先打开终端，进入本仓库并准备好前文的 Python 环境。macOS／Linux 运行：

```bash
python -c 'from pathlib import Path; from getpass import getpass; p=Path.home()/".config/parallel-reading-html/paddle-token"; t=getpass("粘贴 Paddle 令牌后按回车（输入不显示）: ").strip(); assert t, "令牌不能为空"; p.parent.mkdir(parents=True, exist_ok=True); p.touch(mode=0o600, exist_ok=True); p.chmod(0o600); p.write_text(t+"\n"); print("已保存令牌，未显示内容")'
```

Windows PowerShell 运行：

```powershell
.\.venv\Scripts\python.exe -c 'from pathlib import Path; from getpass import getpass; p=Path.home()/".config/parallel-reading-html/paddle-token"; t=getpass("Paste Paddle token and press Enter (hidden): ").strip(); assert t, "Token must not be empty"; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(t+"\n"); print("Token saved; value not displayed")'
```

出现提示后，粘贴那串令牌并按回车。输入时看不到字符属于正常现象。文件中只保存令牌本身；macOS／Linux 命令将权限设为仅当前用户可读写，Windows 请使用个人用户目录并限制其他用户访问。

命令会替换该位置原有令牌，重置令牌后也用同一方法更新。令牌保存在当前系统用户的 `.config/parallel-reading-html/paddle-token`，不在仓库内。若助手运行在另一台机器、容器或不同系统用户下，需要在那个运行环境单独配置。

可以检查“是否已配置”，不显示令牌内容：

```bash
python -c 'import os; from pathlib import Path; p=Path.home()/".config/parallel-reading-html/paddle-token"; print("已配置环境变量（优先使用）" if os.getenv("PADDLEOCR_ACCESS_TOKEN") else "已配置令牌文件" if p.is_file() and p.read_text().strip() else "未配置")'
```

Windows 将 `python` 替换为 `.\.venv\Scripts\python.exe`。这一步只检查配置存在；令牌是否有效、账户是否有可用额度，要通过真实 API 请求才能确认。

### 3. 可选：通过环境变量传入

熟悉终端或需要自动化部署时，可设置名为 `PADDLEOCR_ACCESS_TOKEN` 的环境变量。它的值就是令牌字符串。读取顺序为：**非空环境变量 → 本地令牌文件**。如果更新了文件却仍提示旧令牌无效，检查运行进程是否还带着旧环境变量。

临时环境变量通常只影响当前终端及其启动的程序，已经打开的桌面助手不会自动获得它。仅创建 `.env` 文件也不会生效，本脚本不自动加载 `.env`。一般桌面使用优先采用上面的文件方式。

### 4. 运行一次小文件解析

在同一 Python 环境中，选一份可以上传的短 PDF，把下面的 `/path/to/sample.pdf` 替换为实际路径：

```bash
python scripts/parse_paddle.py "/path/to/sample.pdf" --workdir work/token-check --max-seconds 180
```

它会上传 PDF 并消耗账户解析额度。成功时会生成解析结果和页面 block；失败时根据状态排查。`--max-seconds` 是本次脚本的等待预算，不是服务器完成承诺，也不会取消服务器任务。换另一份 PDF 测试时应换一个工作目录。

令牌不应出现在 GitHub、截图或运行报告中。若已公开，先在 AI Studio 撤销或重置，再更新本地配置。

## Paddle／MinerU 在整个 skill 中做什么

PaddleOCR 和 MinerU 提供文档解析能力：从 PDF 页面提取文字，识别标题、段落、表格、公式等版面元素，并输出供程序处理的 JSON／Markdown。扫描件还需要 OCR，将图片中的文字识别出来。复杂 PDF 的难点不仅是“有没有文字”，还包括多栏阅读顺序、脚注归属和页面位置。

```text
原 PDF
  ↓ 文档解析：当前自动入口是 Paddle 云端 API
带页面信息的原文 JSON／Markdown
  ↓ 本地导入器：统一 block ID、文件页码，核验完整性
blocks.jsonl + pages.json + 原 PDF 指纹
  ↓ AI 助手：三段校准、渐进式双语编写、导读与术语
译文 + 单篇配置
  ↓ 本地构建器：排版、从原 PDF 裁切图表、生成页面锚点
Markdown + HTML
  ↓ 浏览器阅读；配合 Zotero Parallel Reader 按页定位
```

解析服务处在最前面的“原文获取与结构识别”阶段。渐进式双语由 AI 助手完成，HTML 由本地脚本构建。图表虽然可能被解析服务识别，最终呈现仍来自原 PDF 截图。

“异步解析”指先提交任务并取得任务编号，再查询 pending／running／done 等状态，最后下载结果。它便于长任务续查，并不保证立即完成。网络、上传、服务排队、文件复杂度和账户限制都可能影响等待时间。

## 解析卡顿时怎样处理，能替换成什么

令牌本身是凭据。“卡顿”应先定位在上传、排队、解析、下载还是后续 AI 翻译阶段。更换有效令牌不保证加速。

| 现象 | 建议处理 |
|---|---|
| 401／403 | 检查令牌、权限和账户状态；排除旧环境变量覆盖新令牌文件 |
| 429 | 检查限流或可用额度，等待恢复或按平台规则调整额度 |
| pending／running | 服务已接收任务；使用原工作目录续查，避免重复上传 |
| 网络错误、5xx 或本次等待超时 | 保留检查点；网络或服务恢复后用同一命令继续。若提示提交结果未知，先在服务端找回任务编号 |
| 解析已完成，双语输出仍慢 | 排查后续 AI 翻译或构建阶段，切换 OCR 服务未必有帮助 |
| 返回页数少于 PDF 页数 | 停止后续翻译，检查服务页数限制或任务结果，不把缺失页当空白页 |

平台页面可能规定单次解析页数上限。长书须核对当前异步接口的实际限制；不能把 HTML 的分轮渲染当成 API 自动拆分上传。若需分批解析，还必须把分批页码映射回原 PDF，并核验完整覆盖；当前脚本没有自动拆分上传功能。

| 替代路线 | 当前版本能否直接使用 | 适用情况与代价 |
|---|---|---|
| 复用已完成的 Paddle 或其他兼容解析结果 | 可以，由 `import_source.py` 导入 | 已经有正确页码和完整内容时优先使用，省去再次解析 |
| 在 MinerU 中单独解析，再导入结果 | 支持符合规范的历史 `page_idx` 列表；其他输出须先检查或转换 | 可作为另一家解析来源；最新输出格式不保证直接兼容 |
| 本地运行 PaddleOCR／MinerU，再导入结果 | 需要另行安装解析模型并核对输出格式 | 可减少云端排队依赖；有模型、硬件和维护成本，不保证更快 |
| 对清晰的文字型 PDF 用本地工具抽取文本 | 需要新增提取与页面映射步骤 | 简单版式可能更轻量；多栏、公式、脚注及扫描件仍需专门处理 |

**当前版本只内置 Paddle 云端自动提交和续查，没有 MinerU 自动调用或故障切换。** 现有 skill 禁止在 Paddle 失败后自动改走 MinerU；人工提供兼容的已有解析结果属于已支持的导入路径。要实现“一键换供应商”，需同时修改入口策略、增加服务适配器并验证页面契约，不能只换令牌或 URL。

替换解析来源时必须保留真实文件页码、完整页面清单、正确阅读顺序与原 PDF 对应关系；普通无页码 Markdown 不能直接保证 Zotero 定位。若已开始翻译，不应直接替换已有 block 分段。

参考：[PaddleOCR 官方 API 文档](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/inference_deployment/serving/paddleocr_official_api/python.md)、[MinerU 官方项目](https://github.com/opendatalab/MinerU)、[本 skill 输入格式](references/input-formats.md)。服务额度与接口限制以各平台当前说明为准。

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
