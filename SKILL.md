---
name: parallel-reading-html
description: 使用 PaddleOCR-VL-1.6 异步 API 解析 PDF，或复用已有 JSON／Markdown 文本及页面映射，制作渐进式中英学术阅读 HTML，包含逐页锚点与 block id，供 Zotero Parallel Reader 跨文档定位；支持长篇文献（著作、专著章节）按页码范围分轮交付。当用户需要中英对照或双语对照 HTML 时使用；不适用于普通阅读任务。
---

# Parallel Reading HTML

将论文制作成单个中文翻译 HTML 文件，使 Zotero 的 **Parallel Reader** 插件能够与原 PDF 相互定位：阅读器工具栏中的「定位译文」会让译文窗格跳到当前屏幕所显示的 PDF 页；译文窗格中的「定位原文」则会让 PDF 跳到译文当前显示的页面。

这**不是**滚动同步。系统不会持续运行定位逻辑。页面关系在构建 HTML 时写入文件，只在用户点击按钮时读取一次。

## 输出结果约束（绝对不能出错的部分）

插件只从 HTML 中读取两类信息：

| 内容 | 位置 | 用途 |
|---|---|---|
| 每个 PDF 页面对应一个 `<section data-pr-page="N">`，N 为**从零开始**的页码 | 任意元素 | `jumpToPage(N)` 通过 `querySelector('[data-pr-page="N"]')` + `scrollIntoView` 跳转；`visibleSourcePage` 读取与顶部阅读线相交的第一个 section |
| `#parallel-reader-map` 元素，其中保存 `{"schema":"parallel-reader-pages-v1","source":{"md5":...,"pageCount":...}}` | `<script type="application/json">` | 控制按钮是否可用，并**证明当前打开的 PDF 就是生成译文时使用的那一份** |

必须明确以下后果：

- block 使用 `data-pr-page-ref`，绝不能使用 `data-pr-page`。如果另一个元素也带有 `data-pr-page="7"`，就会破坏“读取第一个 section”的逻辑。
- `md5` 是 **PDF 文件本身**的 MD5，因此用户必须打开完全相同的 PDF。若不匹配，应报告「译文对应另一份 PDF」，而不能发生错误定位。
- 页面必须连续覆盖 `0..pageCount-1`。若存在缺页，就有页面永远无法定位，构建必须中止。
- 可见 HTML 正文在 References/Bibliography 标题之前立即结束。参考文献条目及其后的任何内容（包括作者简介）均不在 HTML 中渲染。构建器仍要为被省略的每个 PDF 页面生成一个最小的空页面锚点，以维持 `0..pageCount-1`、源文件指纹以及 Zotero 按钮契约。这些锚点不得包含参考文献文字，也不得形成可见的参考文献部分。


### 内容呈现规则

- **Abstract／摘要之前只保留论文题目和作者姓名。** 不显示期刊名、卷期、出版年份、页码范围、DOI、出版商／期刊 logo、版权与授权声明、网站链接、文章类型、ORCID、单位及通讯信息；作者姓名后的单位序号也不保留。不要把这些信息移入概览、页首 source 或文末脚注。根据原 PDF 版面识别，不能仅按 OCR 顺序或包含 URL 就删除正文。混合 block 只保留其中的题目／姓名，保留原 ID 和一行占位契约。
- **各页学术脚注统一置于整份 HTML 文末**，保持源文顺序、编号、内容和来源页；正文只保留可点击的引用标记。出版元数据不算学术脚注。跨页脚注保留续文；逐页／逐章重编号时必须使用含源页的唯一锚点并核对引用，不能把同号脚注合并。分轮交付时收集本轮范围内脚注。
- **所有 PDF 图、表均截取原 PDF 对应区域作为图片**，不翻译图表、图题／表题、图例、表注，不重绘或重新制表；裁切须包含完整标题、图例、坐标轴、单位、来源和图表自身注释。跨页图表按源页分图，正文仍按原位置引用。图表自身注释随截图保留，独立正文脚注后置。出版 logo 不作为学术图表。
- 源 block 和逐行译文仍保留，隐藏和替换只发生于 HTML 渲染。图表相关 block 原样复制，不送翻译模型、不作术语／结论高亮。仅有文本输入时仍须从原 PDF 截图，不以 OCR 表格或“未提取到图注”等占位符代替。

## 前置条件

- 原 PDF 文件；只有 PDF 时自动调用 PaddleOCR-VL-1.6 异步 API。已有兼容 JSON／Markdown 和明确页面关系时直接复用。
- 用户端已安装 Parallel Reader Zotero 插件，以便使用最终结果。

### 运行环境

- 在 skill 根目录运行下文命令，使 `scripts/` 和配置示例的相对路径正确解析。
- 使用已安装依赖的 Python 3 环境。优先使用用户指定的 `$PARALLEL_READER_PYTHON`；否则使用已激活虚拟环境中的 `python3`（Windows 可用 `python`）。该变量是执行指引，脚本不会自动读取它；设置后须用 `"$PARALLEL_READER_PYTHON" scripts/...` 替换示例中的 `python3 scripts/...`。
- 首次安装时创建独立虚拟环境，在其中运行 `python -m pip install -r requirements.txt`。具体命令见 [README.md](README.md)。不要假定特定应用的受管解释器存在，也不要默认向系统 Python 全局安装依赖。
- **依赖**：`requests` 用于 Paddle API；`PyMuPDF` 用于读取 PDF 和裁切原文图表。`pypdf`／`pdfinfo` 仅是页数读取的备选，不能替代图表裁切所需的 PyMuPDF。
- **令牌**：由使用者设置环境变量 `PADDLEOCR_ACCESS_TOKEN`，或自行创建 `~/.config/parallel-reading-html/paddle-token`。POSIX 系统建议文件权限为 0600；Windows 应限制为当前用户可读。不得将实际令牌写入 skill、日志或产物。脚本不会自动加载 `.env` 文件。
- **网络与数据**：仅有 PDF 而没有兼容解析结果时，解析脚本会将整份 PDF 上传到 Paddle 服务。已有兼容 JSON／Markdown 时可直接导入。若遇网络错误，检查当前环境的代理设置，勿写死代理端口，也勿将含凭据的代理 URL 输出到日志。结果下载请求不携带 API bearer 令牌。
- 把解析缓存、译文和运行记录写入独立工作目录（例如 `work/`），不要混入可发布源文件。

## 有界执行契约

工作流必须在可预测的时间内结束。对于通常不超过约 40 个 PDF 页面的期刊论文，除非用户明确要求更慢、更深入的审查，否则采用以下默认限制：

- 目标墙钟时间为 15–30 分钟；30 分钟为硬停止线；
- 优先复用兼容解析结果；缺少结果时只提交一次 Paddle 异步任务，保存 jobId 并续查，不因超时重复上传；
- 只进行一次三段校准调用；
- 只进行一次带检查点的全文处理，每批约 8,000–12,000 个源字符；
- 除校准调用外，全文模型调用最多 12 次；
- 每个失败批次最多重试一次，全文最多进行一次定向修正；
- 构建一次、核心验证一次、本地成功打开或渲染检查一次。

到达硬停止线后，不得启动新路线或再次全文处理。保留所有检查点；若能够安全完成就构建完整结果，否则交付可用的中间状态并准确说明尚缺内容。时间或额度限制不能成为采用未经校准文本、或把不完整结果声称为已完成的理由。

## 步骤

### 1. 解析 PDF 或复用已有 JSON／Markdown

默认收到原 PDF 后连续完成解析、渐进式翻译、MD 与 HTML 构建及验证。只有用户明确要求先审阅 MD 时才暂停在该阶段。Paddle 负责原文解析，后续翻译仍严格执行本 Skill 的渐进式双语要求。

先检查已有兼容页面 block 或解析结果；没有结果时运行：

```bash
python3 scripts/parse_paddle.py <source.pdf> --workdir <workdir> --max-seconds 900
```

入口使用 `https://paddleocr.aistudio-app.com/api/v2/ocr/jobs`、`bearer` 鉴权及 `PaddleOCR-VL-1.6`，提交整份 PDF 并保存 jobId。它会保存原始 JSONL、带页标记的原文 MD，核验返回页数后自动调用步骤 2 的导入器。成功后无需重复导入。详细恢复与输出规则见 [Paddle 异步解析](references/paddle-api.md)。

解析预算计入整体 30 分钟硬停止线；按剩余总预算调整 `--max-seconds`。超时后保留任务，后续运行同一命令续查；不得重传或自动退回 MinerU。提交结果不明时先找回任务编号。该异步入口不套用旧同步 API 的十页截断规则，也不假定无限页数；以返回进度和实际完整页面结果核验，缺页即停止翻译。

若已有 JSON／Markdown，继续使用下列导入入口。原 PDF 始终用于核验完整文件指纹和页对页定位契约。

统一入口 `scripts/import_source.py` 支持：

- PaddleOCR-VL 逐页 JSON：含 `prunedResult.parsing_res_list` 或 `parsing_res_list`，列表下标即零起始文件页码，记录数必须等于 PDF 页数。由 `scripts/extract_paddle.py` 适配（丢弃页眉页脚、把 `number`／`header` 里的括号码转成印刷页码、`paragraph_title` 转 level 2、`footnote` 转 `kind="footnote"`、规范化 `$ ^{1} $` → `$^{1}$`）。长篇只做其中一段时，可先跑
  `python3 scripts/extract_paddle.py <paddle.json> --workdir <workdir> --pages LO HI`，
  但 pages.json 仍覆盖全部页面，需与配置里的 `renderPages` 配对使用。
- 带 `page_idx` 的 JSON 列表：直接读取既有结果，包括历史 MinerU `content_list.json`；不调用其服务。
- 标准 `blocks.jsonl`＋`pages.json` 目录，或包含 `blocks`、`pages` 的 JSON：核验后保留已有 block ID 和顺序。
- 带明确文件页标记的 Markdown，或配套逐段页面映射的 Markdown。普通无页码 MD 不能按篇幅、章节或印刷页偏移猜测文件页码。

具体字段、MD 标记和配套映射格式见 [输入格式说明](references/input-formats.md)。未知 JSON 结构或缺失页面映射时，报告缺少的字段并请用户补充；不得猜测字段或静默重新解析；只有 PDF 且无兼容结果时使用上述 Paddle 入口。

先区分**待翻译源文**与**已确认译文**。已有译文 MD 必须与源 block 的 ID、顺序、页码逐项匹配，才能通过 `--translation-md` 复用；仅行数相等不足以证明对应关系。复用译文后沿用既定审计与构建流程，不重新翻译已确认内容。

### 2. 导入带页码的 block

```bash
python3 scripts/import_source.py <source.json或source.md或标准block目录> \
    --pdf <source.pdf> --workdir <workdir>
```

无内嵌页标记的 Markdown 还须提供 `--page-map <mapping.json>`；该映射必须绑定源 MD 的 SHA256，并逐段指定文件页码。复用已有译文时，另加 `--translation-md <reviewed.md>`，同时仍提供对应源文输入。

导入器按输入结构自动分派：Paddle 逐页记录 → `extract_paddle.py`；含 `page_idx` 的列表 → `extract.py`（只读文件，不调用其服务）；标准 `blocks.jsonl`／`{blocks, pages}` → 原样沿用既有 ID。分派结果写进 `run-manifest.json` 的 `import.format`，并记录 `sourceSha256`；对无法转成正文的 `table`／`chart`／`image` 项计数并打印提示，不静默吞掉。

导入器只适配输入，输出与现有下游脚本相同的：

- `blocks.jsonl`：按文档顺序排列，包含 `id`、`page`、`printed`、`level`、`kind`、`text`；
- `pages.json`：完整的零起始页面清单，包括输入明确标识的空白页；
- `run-manifest.json`：记录原 PDF MD5、页数、输入来源、输入指纹和 block 契约；保留已有批次检查点。

将 manifest 中核验过的 `source.pageCount` 写入单篇配置的 `pageCount`，供现有构建器保留末尾空白页或非文本页的锚点；不能仅以最后一个正文 block 的页码推断总页数。

脚本在写入前检查连续页面覆盖、页码范围、源文顺序及 ID 唯一性。已有工作目录的 PDF 指纹或 block 契约不同即中止，不覆盖既有译文。新导入的无 ID 文本只在此阶段由脚本按顺序分配 ID；之后冻结分段。

检查逐页 block 数和字符数报告，发现异常后先核对输入：

- **非文本内容用原 PDF 截图补齐。** 检查未进入 block 的图表，在冻结分段前建立对应位置，再按上述截图规则处理；不重复启动识别流程。
- **文件页码与印刷页码分开。** 文件页码是定位依据，必须来自输入中的明确页面关系。`000` 等无效印刷页码不保留，不推测固定偏移；缺少印刷页码时沿用文件页码回退规则。

### 2.5. 在进行全文处理前锁定路线

全文翻译是成本最高的步骤。在处理所有 block 前，必须先运行一个**三段校准门**：从开头、中部和结尾选择有代表性的正文，或分别选择一个理论密集段、一个普通论证段和一个含引文/引用较多的段落。依据默认双语配置和语义忠实要求展示或检查这些样本。

- 当源 PDF MD5、页数和 block 契约一致时，复用兼容的已导入源文件与页面 block。将这三项写入 `<workdir>/run-manifest.json`，不得仅为获得新目录而重新导入或改变分段。manifest 还需记录已完成批次的文件名和 block-id 范围。
- 不得并行启动多个竞争性的全文方案。根据三个样本选定路线后，只运行一次全文处理。
- 同一工具、供应商或模型路线针对同一错误最多重试一次。再次失败时必须立即更换路线，或交付当前最安全的中间结果并说明限制。
- 缓存已完成 block。供应商失败或比例需要调整时，只续跑或修补受影响 block；默认不得重新处理全部译文。
- 如果校准样本明显生硬，应在全文处理前停止并修正 prompt 或选择规则。四份不理想的全文草稿不能替代一次成功校准。

默认执行循环（不得扩展）：

1. 核验源文件指纹并复用或提取页面 block。
2. 用三个代表性 block 校准。
3. 将 block 分为实质正文与原样保留 block。参考文献、书目列表、URL/DOI、出版元数据以及其他应保持英文的 block 直接复制；绝不能为它们消耗模型调用。
4. 只对实质正文运行一次带检查点的转换，同时为每个源 block 保留一行输出。
5. 运行 `scripts/audit.py`；最多只对明确列出的离群 block 进行一次定向再平衡，绝不能重做全文。
6. 在一次综合处理里生成 overview、terms 和 conclusions 候选，然后写入配置。
7. 构建、运行核心验证、打开或渲染一次并交付。

可用且限制说明诚实的结果，优先于长时间试验不同路线。如果结果已经满足所需语言配置和结构契约，应立即停止；不要增加无法改变交付结果的探索性检查。

### 3. 按源文顺序翻译

在 `<workdir>` 中写入 `zh-1.txt`、`zh-2.txt`……；**每个 block 对应一行，顺序必须与 `blocks.jsonl` 完全一致**。文件拆分仅用于控制单次写入规模。构建器按位置将二者配对。

- 必须严格一行对应一个 block，行数必须一致，否则构建中止。不要把跨页延续的 block 合并到前一个 block，也不要拆分 block。经核验并冻结的源 block 分段就是契约。
- **文件名必须补零**：`zh-01.txt`、`zh-02.txt`……构建器按文件名**字典序**拼接，`zh-10.txt` 会排到 `zh-2.txt` 前面。超过 9 个分片文件时用 `zh-1.txt` 这类不补零命名会静默打乱顺序、错位到每一页，且不会有任何报错。
- 绝不能手工指定 block id。顺序是译文行与源 block 保持对应的唯一依据；过去曾有人工标号导致偏移一行、随后所有页面都在无提示情况下错位。
  - 允许（且推荐）的变体：正文先写成 **以 block id 为键的中间文件**（如 `tr-01.tsv`，
    每行 `<block-id>\t<译文>`），再用脚本按键装配出定位式 `zh-*.txt`。这样缺行、重复、
    错序都会立刻报错而不是静默偏移；交给 builder 的 `zh-*.txt` 里仍然不含任何 id。
- 脚注引用标记保持为 `$^{1}$`；构建器会进行转换。
- 拉丁语技术术语保持拉丁字母形式（如 `deditio`、`habitus`）；中文正文承载其含义，同时使术语强调可以配置。
- 从 References/Bibliography 标题及 block 模式识别参考文献起点。参考条目直接原样复制，不调用模型。纯元数据、URL/DOI、作者标识和已经是英文书目记录的内容也直接复制。作者简介属于正文，除非用户另有要求，仍应转换。
- 只有实质正文 block 才按批次送给模型，但最终 `zh-*.txt` 必须按原始 block 顺序重建。每个检查点都要在 `run-manifest.json` 中记录源 block-id 范围。
- 每批约 8,000–12,000 个源字符。单个批次失败时，不得改成逐 block 的微小调用；只重试该批一次，然后更换供应商或保留检查点停止。

#### 默认渐进式双语配置

除非用户要求其他语言处理方式，否则使用中文语义和句法骨架，并依据**词汇学习价值**保留英文，而不是依据词性。以下是已经验证的默认配置；不得称为机械的“25% 英文模式”：

| 指标 | 默认目标 |
|---|---:|
| 源英文 token 保留率 | 约 60%；通常为 58–62% |
| 混合显示单位中的英文占比 | 仅作诊断；当一个英文词和一个汉字各计一个单位时，通常为 48–50% |
| 连续英文跨度平均长度 | 3–4 个词 |
| 单词跨度 | 不超过全部英文跨度的约 22% |
| 多词跨度所包含的英文 token | 至少约占全部英文 token 的 93% |
| 真正不熟悉的学习单元 | 每 100 个源英文词约 2–5 个 |

这些是**语料库层面的软目标**，不是逐句配额。只在实质正文上计算：排除参考文献、书目记录、URL/DOI、出版元数据和其他原样保留 block。语义忠实、自然中文、完整词汇单元、引文、公式、引用以及一 block 一行的契约，均优先于机械追求比例。

以下情况才算“显著偏离”：语料库保留率低于 55% 或高于 65%；平均英文跨度低于 2.5 或高于 5.0 个词；单词跨度超过 30%。只调整明确列出的离群 block，并且只重新审计一次；不得为了比例而拆碎短语或重做全文。第二次审计后即使仍偏离软目标，只要文本忠实、可读，就应交付并报告实测限制，而不是继续循环。

按以下优先顺序保留英文：

1. 论文术语、具名理论、核心概念和关键区分。
2. 可复用的学术词汇及承担论证功能的动词。
3. 自然搭配、词汇束和多词表达。
4. 当完整保留较长命题能减少语言切换，且周围中文足以帮助推断含义时，保留完整命题。
5. 不增加显著认知负担、但可提高英文接触量的熟悉英文。

应优先保留较少但较长、连贯的英文跨度，避免频繁出现孤立单词。`underlying probability distribution`、`bridge this gap`、`condition state behavior` 等单元必须整体保留；绝不能因为词性规则只保留其中的名词。冠词、代词、助动词、普通连词和介词在只承担语法骨架作用时应翻译，但如果它们属于受保护词汇单元，则应保留。高价值学术动词构成自然单元时，通常也保留英文。

必须保留完整命题以及所有限定、否定、情态、因果、程度、时间关系、例子、标题、脚注、引用和 block 顺序。这是全文转换，不是摘要。为形成自然中文句法，可以进行局部重排，但不得加入作者未提出的解释。长直接引语在精确措辞重要时默认保持英文；周围论证应翻译到足以让读者理解该引语在上下文中的作用。

候选学习单元不等同于生词。如果用户提供 `KNOWN`、`LEARNING` 或 `UNKNOWN` 词表，用它们估计真正的新颖度：

- `KNOWN`：可自由保留，不计入新学习单元密度。
- `LEARNING`：优先保留；源文重复时保持一致重复。
- `UNKNOWN`：重要且可从上下文推断时保留；边缘且晦涩时翻译。

若没有个人词表，只能将新学习单元密度报告为明确标注的**候选代理指标**，不能声称测得了真实词汇知识。人名、书目信息、URL 和普通缩写在出现时计入原始英文暴露量，但除非其本身就是学习概念，否则不计入学习单元代理。

### 4. 编写单篇论文配置

配置包含 `overview`、`terms`、`conclusions`、`inferredLabels`、`author` 和 `source`。将 `scripts/assets/paper.example.json` 复制到 PDF 旁边并命名为 `<title>.parallel-reader.json`，确保可以复现构建。

- `terms`：论文自己的关键术语，必须使用它们在译文中的形式。每个术语首次出现时带“术语首见”标签，后续出现处使用普通标签。匹配表达式为 `(?<![A-Za-z])term(?![A-Za-z])`，因此不得同时列出互为子串的术语（例如同时列出 `能力` 和 `国家能力` 会造成标签嵌套）。只保留较长形式。
- 参考文献列表：不得翻译，也不得发送给模型。逐 block 原样输出，每行一个 block。行数是契约，语言不是。参考文献保留在 Markdown 归档中以便复现，但最终 HTML 会将它们及所有后续 block 省略。
- `conclusions`：形如 `{block-id: [exact sentence, …]}`，用于标记承载核心论证的句子。**必须逐字引用最终译文中的句子**。不匹配时构建应中止；强调标记静默丢失比构建失败更糟。
- `inferredLabels`：只为输入未提供有效印刷页码的页面（封面、前置材料）填写印刷页码。不得假设文件页码与印刷页码存在固定偏移；先检查 `pages.json`。
- 在最终译文正文形成后，用一次综合调用同时生成 `overview`、`terms` 和候选 `conclusions`。候选结论随后必须从最终译文逐字复制；不得为了匹配候选句而重新生成正文。
- `overview`：必需的开篇研究概览。阅读全文或章节，并以简明、忠于来源的中文撰写 `puzzle`、`method` 和 `conclusion`；将 `type` 设为 `theory`、`quantitative` 或 `qualitative`。
  - `theory`：还应提供 `contribution` 和分步骤的 `argument`。
  - `quantitative`：提供 `data`（若原文有说明，则包括来源、样本、期间和分析单位）以及 `regression`（若原文有说明，则包括变量、模型、识别策略和稳健性）。
  - `qualitative`：提供 `caseSelection` 与 `comparison`，并在不存在系统性跨案例比较时明确说明。

在适当处引用 PDF 页码或源文章节。不得虚构不存在的方法或数据；必须区分作者主张和你的综合判断。

### 5. 构建并放置产物

```bash
python3 scripts/build.py --workdir <workdir> --pdf <the.pdf> \
    --title "<title>" --out <dir> --config <title>.parallel-reader.json
```

脚本生成：

- `<title>（中文翻译）.md`
- `<title>（双语对照）.html`

将两者都放在 PDF 旁边——用户会在该位置寻找文件，插件文件选择器也会从这里使用。`.md` 是归档副本，`.html` 是实际载入文件。HTML 先显示研究概览，再显示映射后的 PDF 页面。overview 不得带 `data-pr-page`，也不得改变页面映射。

默认 `htmlStopBeforeReferences` 为 `true`：HTML 在标题完全等于 `References`、`Bibliography`、`Works Cited`、`Footnote references`、`Literature references`、`Source references` 或 `参考文献` 之前停止渲染（拉丁文字不区分大小写）。`Footnote references` 是 *Economic History Review* 自己的 list 标题（Oxley 2003 实测），漏掉它会让整份书目被当成正文渲染。普通运行不得关闭这一选项。Markdown 仍保留完整的有序 block 归档。如果没有找到这些标题，构建器应报告事实，不得猜测截断位置。**audit.py 的 `REFERENCE_HEADING` 必须与 build.py 的正则逐字相同**，否则审计分母会与渲染范围不一致。

**图表截图与元数据过滤配置**：使用 `htmlOmitBlockIds` 列出已核对的纯元数据以及被截图完整覆盖的重复图题／表格 block；使用 `htmlBlockText` 按已有 block ID 指定混合 block 中应显示的题目／作者部分。`source` 留空；构建器 HTML 页首仅显示 author。

`pdfCrops` 按已有 block ID 设置裁切区域，例如 `"pdfCrops": {"block-0012": {"page": 3, "bbox": [50, 120, 550, 640]}}`。page 为零起始源页，必须与该 block 一致；bbox 为 PyMuPDF 页面坐标（point，非 OCR 像素），须核对比例、旋转和实际区域。构建器以 180 dpi 渲染并内嵌 PNG，单个 HTML 可独立打开；必须查看截图确认完整清晰。若图表尚无 block，须在冻结分段、开始翻译之前通过导入器建立对应页的占位 block，再配置截图；不得在已有逐行译文中插入 block。缺少裁切配置的已识别 HTML 表格会中止构建，不能回退成重新制表。旧纯文本图表需人工识别并加入配置。

如需在不重建译文正文的情况下更新既有 HTML，运行：

```bash
python3 scripts/overview.py --html <existing.html> --config <paper.json>
```

**绝不能覆盖已有的 `<title>（中文翻译）.md`。** 文件夹中可能已有另一轮、采用不同分段方式生成的译文；它虽没有 block id、无法复用，但仍属于用户文件。复制前先检查，使用不同名称（如 `（中文翻译·按页）.md`），不得覆盖。

### 6. 单篇论文设置

- `termChip: "first"`：只标记每个术语首次出现的位置。当论文术语在译文语言中属于普通词、会高频出现时使用（例如“斯多亚”出现 80 次以上）。如果术语在视觉上明显不同（如拉丁字母术语），保持默认值 `"all"`。
- `footnotesAtEnd: true`（默认且必需，不是可选展示方式）：把每个 `kind == "footnote"` 的 block 从其页面 section 抽出来，统一放到文末的
  `section.pr-notes`；正文里的 `$^{n}$` 变成指向 `#pr-note-n` 的链接，脚注条目带一条回到正文的 `↑`。
  要点：该 section **不带** `data-pr-page`（与 overview 同理），因此页面 section 仍是连续的 `0..pageCount-1`；
  block id 仍挂在包裹每个脚注 block 的 `div[data-pr-id]` 上，不会被拆散。一个脚注 block 内含多条编号脚注时
  （如 `$^{1}$…$^{2}$…`），会按键拆成多条并各自获得锚点。实测注意：滚到文末脚注区后，「定位原文」
  没有可读的页面 section，插件多半沿用上一次的页码——这一点必须在交付时说明，由用户在 Zotero 里确认。
- `pageCount`：总页数，取 `run-manifest.json` 里核验过的 `source.pageCount`。构建器只用它补齐末尾空白页／非文本页的锚点；配得比最后一个 block 的页码还小会直接中止。
- 分隔符：正文里独立成块的 `* * * * *` 自动渲染成 `.pr-sep` 分隔线，译文里不需要特殊处理。
- 页码标签回退：某页有 1–4 位有效印刷页码就用它，否则用 `inferredLabels[页]`，都没有才回退为「文件页码 + 1」。

#### 长篇分轮次交付（著作、多章节文献）

一本书或长文献按轮次交付时，**不要**为每轮重建 mapping，也不要缩小 `pageCount`：

- `pageCount` 保持全书页数；`renderPages: [LO, HI]`（含端点、零起始文件页）指定本轮渲染范围。
- 只有落在该范围内的 block 参与渲染与翻译：`zh-*.txt` 的行数必须等于**选中的 block 数**，而不是全部 block 数。其余页面生成为空锚点 `section.pr-page.pr-page-omitted`，于是 `0..pageCount-1`、源文件指纹和 Zotero 按钮契约始终完整，下一轮接着填即可。
- `scopeNote`：一句人话说明本轮范围，写进 MD 与 HTML 头部。**给出 `scopeNote` 后，构建器不再自动生成「本轮仅渲染 pdfPageIndex …」那行**，所以要自己写全（覆盖哪一部分、哪些页、全书还剩多少未做）——`renderPages` 和 overview 都只知道本轮的 block，报不出还剩多少。
- 抽取阶段可以先用 `extract_paddle.py --pages LO HI` 缩小 block 集合，但 `pages.json` 仍须覆盖全部页面。
- 每轮 HTML 指向同一份 PDF、同一个 md5；文件名带轮次范围（如 `（双语对照·第3章）.html`），不要覆盖上一轮产物。

## 报告前验证

```bash
python3 - <<'PY'
import json, re
from pathlib import Path
s = Path("<the>（双语对照）.html").read_text()
m = json.loads(re.search(r'id="parallel-reader-map">(.*?)</script>', s, re.S).group(1))
print("sections", s.count('data-pr-page="'), "expected", m["source"]["pageCount"])
print("blocks", len(re.findall(r'data-pr-id=', s)))
print("footnotes left as $^{", s.count("$^{"))
print("terms", s.count('class="pr-term'), "conclusions", s.count('class="pr-conclusion"'))
PY
```

也可运行 `scripts/verify.py`。要求：

- sections == pageCount，且 `data-pr-page` 恰好是连续的 `0..pageCount-1`；
- Abstract 前仅有题目与作者，无出版元数据或 logo 占位符；
- 所有学术脚注只出现于文末，引用／返回链接对应；
- 图表全部为清晰完整的原 PDF 截图，无译制表格或重复图注；
- 不存在遗留的 `$^{`；
- 找到截断点时，不得存在可见的参考文献标题或条目；
- 构建输出显示 `terms introduced=N/N`；
- 构建输出显示 `conclusions matched=N/N`。

`#parallel-reader-map` 除 `schema`／`source` 外还带一个 `content` 对象：`referencesOmitted`、`renderedPages`（分轮次时为 `[LO,HI]`，否则 `null`）、`lastRenderedBlock`、`footnotesAtEnd`。`verify.py` 用它核对；截断参考文献时缺 `lastRenderedBlock` 即失败。`verify.py` 另外只读地打印 md5 格式（须为 32 位小写十六进制）、空锚点数量与 `references omitted/included`。

**计数口径提醒**：`verify.py` 的 `terms`／`conclusions` 是全文子串计数，**包含页首图例里那两个示例标记**，因此会比正文实际标记数多 1–2。判断是否匹配一律以构建器输出的 `terms introduced=N/N` 和 `conclusions matched=N/N` 为准，不要把图例造成的差值当成漏标。

省略参考文献后，HTML block 数小于 Markdown/译文 block 数是预期行为，并非映射失败，因为页面锚点仍然完整。

采用两级验证预算：

- **核心验证（始终执行）：** 源文件 MD5/页数、连续页面 section、block 数、译文行数、未解决的脚注占位符、必需的术语/结论匹配，以及一次成功的本地 HTML 打开或渲染检查。
- **扩展诊断（仅在用户要求或核心检查失败时执行）：** 穷尽式术语频率表、对已验证副本反复比较文件哈希、完整无障碍树检查、多浏览器检查或额外视觉巡检。这些检查不得延误本已完整的交付。

最终文件复制到 PDF 旁边后，只需进行一次存在性/大小检查或一次哈希检查，不要重复多个等价比较。Zotero 按钮的真实行为必须由用户端确认，不得为此进行长时间的模拟 UI 测试。

运行确定性审计，不要为每篇论文重新编写分析器：

```bash
python3 scripts/audit.py --workdir <workdir> --out <workdir>/bilingual-audit.json
```

该脚本使用 `blocks.jsonl` 和按顺序排列的 `zh-*.txt`，从语言比例分母中排除检测到的参考文献、书目和元数据 block，并报告原始英文跨度诊断与候选学习单元代理。只检查其列出的离群项。通过后不要重复审计；除非该脚本失败，不得再编写第二套临时审计实现。

判定口径是确定性的，不要另行发明：参考文献起点用与 `build.py` 完全相同的标题正则（`References`／`Bibliography`／`Works Cited`／`参考文献`，拉丁文字不分大小写），之后的 block 全部计入 `reference`；含 URL／`doi:`／ORCID／版权标记，或「不足 160 字、无汉字、含 `©` 或两个以上 `|`」的短行计入 `metadata`；其余为 `prose`。`outlierBlocks` 只对源英文词数 ≥ 30、且保留率低于 `0.45` 或高于 `0.75` 的 block 报警——这是逐 block 的注意力提示，与上文的语料库软目标（55%–65%）口径不同，不要混用。

至少报告：

1. 保留英文 token 数 / 源英文 token 数；
2. 英文 token /（英文 token + 汉字数），明确标为次要的显示单位启发指标，而不是语言学意义上的比例；
3. 中文↔英文转换边界，以及每 100 个源词的转换次数；
4. 连续英文跨度数量、平均数、中位数和长度分布；
5. 单词跨度与多词跨度：既报告跨度数量占比，也报告其包含的英文 token 占比；
6. 候选学习单元及其出现次数，并明确指出：实际新颖度需要用户词表才能判断。

连续英文跨度的定义：在两个汉字之间未被汉字打断的连续英文词；仅有标点不产生新跨度。对于语义学习单元，如果一个正字法跨度包含多个相互独立、具有意义的术语或搭配，应将其拆分。原始跨度审计和语义单元审计必须分开。审计用于发现偏移，不能成为制造生硬译文的理由。

最后必须明确说明：页面映射只在结构层面得到证明；按钮是否能在 Zotero 中工作，仍需用户确认，因为 MD5 检查取决于用户实际打开的是哪一份 PDF。

## 禁止事项

- 不得复用其他论文的配置、页码标签或 MD5。
- 不得手工编辑生成后的 HTML；应修改配置或脚本并重新运行。
- PDF 解析仅使用上述 Paddle 异步入口；不调用 MinerU。页面 id 必须来自完整解析结果或已提供并核验的输入，不得猜测或补造。
- 不得向 HTML 添加滚动同步。定位按需触发，这是设计本身。
- 不得为了「让页面数好看」而调小 `pageCount`、删除空锚点或合并页面 section；缺页会让那一页永远无法定位。
- 分轮次交付时，不得把 `renderPages` 范围外的 block 译文写进 `zh-*.txt`；行数必须等于本轮选中 block 数。
