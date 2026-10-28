# Parallel Reading HTML

将英文论文或著作章节制作成适合渐进式阅读的中英双语 Markdown 和 HTML，并保留与原 PDF 对应的页面锚点。

中文承载句法和语义骨架，英文保留有学习价值的完整术语、搭配与论证表达。它是供 AI 助手执行的 skill：Python 脚本负责解析、导入、构建和检查，双语内容由助手依照 `SKILL.md` 编写；仅运行解析脚本不会自动生成译文。

## 能做什么

- 通过 PaddleOCR 异步 API 解析 PDF，或复用已有的兼容 JSON／带页码 Markdown。
- 输出逐 block 对应的双语 Markdown 和可独立打开的 HTML。
- 保留零起始文件页码与原 PDF 的 MD5，供 [Zotero Parallel Reader Plugin](https://github.com/hebruce1005/zotero-parallel-reader-plugin)按按钮定位原文和译文；不是持续滚动同步。
- 在摘要前只显示题目与作者，将学术脚注汇集到文末，以原 PDF 截图呈现图表。
- 在正文开始前梳理文献的“研究问题”、“研究方法”与“研究结论”
- 支持长篇文献按文件页范围分轮交付，并保留全书页面映射。

## 实际任务耗时参考

以下为两次为在ChatGPT 6.1 sol 高模型下进行的真实任务耗时，包含模型生成、解析等待、文件处理与必要修正。

| 流程 | 期刊论文 | 学术专著 |
|---|---:|---:|
| 文献规模 | 19 页，126 个源文块 | 254 页，1,582 个源文块，7 章 |
| 技能与文件检查 | 18 秒 | 17 秒 |
| PDF 解析与页面导入 | 1 分 26 秒 | 3 分 46 秒 |
| 源文检查与三段校准 | 30 秒 | 2 分 08 秒（含图表裁切） |
| 渐进式双语转换 | 3 分 40 秒 | 4 分 11 秒 |
| 首次语言审计与一轮定向调整 | 2 分 04 秒 | 2 分 04 秒 |
| 导读、配置、文件汇总及交付核验 | 1 分 36 秒 | 2 分 58 秒 |
| 用户确认后的独立 HTML 阶段 | 已包含在上一项 | 约 6 分 42 秒 |
| **完整交付总耗时** | **约 9 分 34 秒** | **约 22 分 05 秒** |
| 交付方式 | 一次完成 MD 与 HTML | 先交付 MD，确认后生成 HTML |
| 图表处理 | 无图表裁切 | 11 处原 PDF 截图 |

耗时受解析服务排队、文献结构、图表与脚注复杂度、模型响应速度及修正量影响，可以让Agent“审核一轮没有即可输出，无需过度审查”，否则agent 可能会通过多轮优化尝试更加逼近60%英文保留率的理想标准，消耗额外的时间与额度。一般的，一轮生成审核后的html会处在40-60%的英文保留率区间。

## 段落示例

下面是基于 ["Cognitive load theory and complex learning: Recent developments and future directions"](https://link.springer.com/article/10.1007/S10648-005-3951-0)这篇文献摘要的混合文本翻译示例，均为ChatGPT 6.1 sol提供。

**原文**
Traditionally, Cognitive Load Theory (CLT) has focused on instructional methods to decrease extraneous cognitive load so that available cognitive resources can be fully devoted to learning. This article strengthens the cognitive base of CLT by linking cognitive processes to the processes used by biological evolution. The article discusses recent developments in CLT related to the current view in instructional design that real-life tasks should be the driving force for complex learning. First, the complexity, or intrinsic cognitive load, of such tasks is often high so that new methods are needed to manage cognitive load. Second, complex learning is a lengthy process requiring learners’ motivational states and levels of expertise development to be taken into account. Third, this perspective requires more advanced methods to measure expertise and cognitive load so that instruction can be flexibly adapted to individual learners’ needs. Experimental studies are reviewed to illustrate these recent developments. Guidelines for future research are provided.

**40%英文保留率**
传统上，Cognitive Load Theory（CLT）一直关注通过 instructional methods 来 decrease extraneous cognitive load，使 available cognitive resources 能充分用于学习。本文通过把 cognitive processes 与 biological evolution 所采用的过程联系起来，强化 the cognitive base of CLT。文章讨论了 CLT 的 recent developments，它们与 instructional design 中的一种当前观点相关：real-life tasks 应成为 complex learning 的 driving force。首先，这类任务的复杂性，也就是 intrinsic cognitive load，往往较高，因此需要新的方法来 manage cognitive load。其次，complex learning 是一个 lengthy process，需要考虑学习者的 motivational states 以及 expertise development 的水平。第三，这一视角要求采用更先进的方法来 measure expertise and cognitive load，以便灵活调整教学，适应 individual learners’ needs。本文回顾 experimental studies，以说明这些近期发展，并提出 guidelines for future research。

**60%英文保留率**
传统上，Cognitive Load Theory（CLT）一直关注通过 instructional methods 来 decrease extraneous cognitive load，以便 available cognitive resources can be fully devoted to learning。本文通过把 cognitive processes 与 the processes used by biological evolution 联系起来，强化 the cognitive base of CLT。文章讨论 CLT 的 recent developments，它们与 instructional design 中的一种 current view 相关：real-life tasks 应成为 complex learning 的 driving force。首先，这类任务的复杂性，即 intrinsic cognitive load，往往很高，因此需要 new methods 来 manage cognitive load。其次，complex learning 是一个 lengthy process，需要把 learners’ motivational states 和 levels of expertise development 考虑在内。第三，这一 perspective 要求使用 more advanced methods 来 measure expertise and cognitive load，以便 instruction can be flexibly adapted to individual learners’ needs。本文回顾 experimental studies，来 illustrate these recent developments，并提出 guidelines for future research。

**中文翻译**
传统上，认知负荷理论一直关注通过教学方法减少外在认知负荷，使可用的认知资源能够充分用于学习。本文通过将认知过程与生物演化所采用的过程联系起来，强化认知负荷理论的认知基础。文章讨论了认知负荷理论的近期发展，这些发展与当前教学设计中的一种观点相关：真实生活中的任务应当成为复杂学习的驱动力。首先，这类任务的复杂性，也就是内在认知负荷，往往较高，因此需要新的方法来管理认知负荷。其次，复杂学习是一个长期过程，需要考虑学习者的动机状态及其专长发展的水平。第三，这一视角要求采用更先进的方法来测量专长和认知负荷，以便灵活调整教学，适应学习者的个体需要。本文回顾了实验研究，以说明这些近期发展，并为未来研究提出指导建议。

## 安装

下载本仓库并将文件夹命名为 `parallel-reading-html`，放入所用 AI Agent 支持的 skill 目录，或让复制网址让Agent直接安装。

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

## 配置 Paddle 令牌：让 AI 助手帮你完成

首次使用需要配置一次。令牌是调用 Paddle 解析服务的“钥匙”，每位使用者使用自己的令牌。

### 1. 领取令牌

打开 [PaddleOCR 官方体验页面](https://aistudio.baidu.com/paddleocr/task/new)，登录或注册账户。在“API 调用”中选择 **PaddleOCR-VL-1.6**，点击“获取令牌”，复制那串数字和字母即可。无需复制官方示例代码。

### 2. 让 AI 助手准备配置

在能操作本地文件的 Agent 中打开本 skill 文件夹，把下面这段话发给它：

> 请帮我配置 parallel-reading-html 的运行环境和 Paddle 令牌。先检查并安装所需依赖，再提供一个不会显示输入内容的本地令牌输入方式，由我亲自粘贴。将令牌保存到当前用户的 ~/.config/parallel-reading-html/paddle-token，限制文件访问权限；不要把令牌写入 skill、Git 仓库、聊天回复或日志。检查是否有旧的 PADDLEOCR_ACCESS_TOKEN 环境变量覆盖它。完成后只告诉我是否配置成功。

按助手提示，在本地输入窗口或终端中粘贴令牌、按回车即可。令牌输入时不显示字符是正常现象。若助手无法提供私密输入方式，请让它指导你在电脑上手动保存；云端 Agent 则需要在其实际运行环境中配置。

**不建议把令牌直接发到聊天里**，因为它可能被保存在聊天记录中。配置只需把钥匙保存在你自己的电脑上，无需修改 skill 源码。

### 3. 提供一份小 PDF 验证

给agent上传一份简短的PDF，再发送：

> 请用这份 PDF 验证刚才的配置：先检查 Paddle 能否成功解析、返回页数是否完整，再按 parallel-reading-html 生成一份双语 Markdown 和 HTML。请分别说明解析、双语生成和 HTML 检查是否成功。如果等待超时，保留任务记录，后续继续查询同一个任务，不要重复上传。

这一步会把 PDF 上传到 Paddle 并使用账户解析额度。测试通过后即可处理正式文献。以后更换电脑或重置令牌时，重新配置即可；已泄露的令牌应先在 AI Studio 撤销或重置。

## Paddle 在整个 skill 中做什么

PaddleOCR 提供文档解析能力：从 PDF 页面提取文字，识别标题、段落、表格、公式等版面元素，并输出供程序处理的 JSON／Markdown。扫描件还需要 OCR，将图片中的文字识别出来。复杂 PDF 的难点不仅是“有没有文字”，还包括多栏阅读顺序、脚注归属和页面位置。

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

解析服务处在最前面的“原文获取与结构识别”阶段。渐进式双语由 AI agent 完成，HTML 由本地脚本构建。图表虽然可能被解析服务识别，最终呈现仍来自原 PDF 截图。

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

类似的网站还有 MinerU，替换解析来源时必须保留真实文件页码、完整页面清单、正确阅读顺序与原 PDF 对应关系；普通无页码 Markdown 不能直接保证 Zotero 定位。若已开始翻译，不应直接替换已有 block 分段。

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
