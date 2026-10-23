# JSON／Markdown 输入格式

所有文件页码均从 0 开始，必须明确覆盖原 PDF 的全部页面。原 PDF 用于计算 MD5、读取页数及裁切原图表；正文文本仍由兼容解析输入提供。无文本页也须出现在页面清单中，不能用推测补齐。

## JSON 与标准目录

- PaddleOCR：每页一条记录的列表，每条含 `prunedResult.parsing_res_list`（或直接含 `parsing_res_list`），block 字段为 `block_label` 和 `block_content`。使用已有 `extract_paddle.py` 适配；导入器在 `import.format=paddleocr-json` 下会自动调用它，不要手写另一套适配。长篇分轮次抽取可加 `--pages LO HI`：只保留该文件页范围内的 block，但 `pages.json` 仍覆盖全部页面，须与配置里的 `renderPages` 配对，锚点才不会缺。
- 历史 `page_idx` 列表：每条含 `page_idx`、`type`，文本位于 `text`。使用已有 `extract.py` 适配；每个 PDF 页面必须有明确记录，包括无正文页。
- 标准目录：同时包含 `blocks.jsonl` 和 `pages.json`。也可直接传入 `blocks.jsonl`，页面清单默认取相邻的 `pages.json`，可用 `--page-map` 指定。
- 标准 JSON：`{"blocks": [...], "pages": {...}}`，可附加 `source.md5`；提供的指纹必须匹配原 PDF。

标准 block 字段为 `id`（唯一的 `block-数字`）、`page`（整数）、`printed`（真实印刷页码或 null）、`level`（标题为 2，正文为 null）、`kind`（text 或 footnote）、`text`。不得把一个任意 JSON 文件的数组顺序直接解释为页面。

## 带页标记的源 MD

推荐使用以下显式标记；标记中的印刷页码是可选项：

```markdown
<!-- pr-page: 0 -->
# Article title

First paragraph.

Second paragraph with a note $^{1}$.

<!-- pr-page: 1; printed: 12 -->
## Section heading

Next paragraph.
```

也识别独立的 `<!-- pdfPageIndex=0 -->`，以及 `## PDF 第 1 页` 或 `## 第 1 页 · 印刷页 12` 这类文件页标题（标题中的文件页从 1 开始）。首个页面标记之前不得出现未归属页面的源文。不要把学术正文中的章节编号当页码。

无 ID 的 MD 按空行划分 block；围栏代码与独立 `$$` 公式内部的空行不拆 block。源文段落的换行归一为空格，标题映射为 level 2，Markdown 的数字脚注 `[^1]`／`[^1]:` 规范为 `$^{1}$`。分段只执行一次，随后冻结。MD 中的图片链接不是图片内容的识别结果。

若已经有 block ID，可使用下述标记；两个 block 标记之间的内容属于同一个 block，不能再按空行拆分：

```markdown
<!-- block-0001; source-page: 0 -->
Translated or source paragraph.
```

现有归档中的 `<!-- block-0001 · pdfPageIndex=0 · printed=1 -->` 同样可读。所有 ID、页码和顺序必须一致，不能手工重新编号。

## 普通 MD 的配套映射

没有内嵌页标记时，使用 `--page-map mapping.json`。映射须由可核验的上游页面信息产生，不能仅因段落数相同而从另一个 JSON 套用。

```json
{
  "schema": "parallel-reader-md-map-v1",
  "sourceSha256": "源MD文件的完整SHA256",
  "pages": {"0": {"printed": null}, "1": {"printed": "2"}},
  "blocks": [{"page": 0}, {"page": 1}]
}
```

`blocks` 与 MD 空行分段结果逐项对应，可附加已有 `id`、`kind`、`level`、`printed`。此例为两段、两页；实际清单须覆盖原 PDF 的完整页数。哈希不匹配、段落数不匹配、缺页或页码倒序均中止。

## 复用已确认译文

```bash
python3 scripts/import_source.py <源JSON或标准block目录> \
    --pdf <source.pdf> --workdir <workdir> \
    --translation-md <reviewed.md>
```

译文 MD 必须含每个 block 的 ID 与零起始文件页码，并完整覆盖源 block。导入器忽略映射区域之前的审阅稿标题／说明，去除 Markdown 标题与引用的显示标记，按源 block 顺序写出一行一个 block 的 `zh-01.txt`。原 MD 不改写。不能把缺少 ID 的普通译文、或已经截断参考文献的 MD 当成完整译文复用。已有 `zh-*.txt` 与导入译文不一致时中止，不覆盖。

导入器不会判断译文质量。复用以用户确认或既有合格校准与审计为前提；后续继续遵守主 Skill 的语言、审计和构建要求。
