# Paddle 异步解析入口

使用 v2 jobs 协议（PaddleOCR-VL-1.6），不混用旧同步 API 的 token 鉴权、Base64 payload 或页数设置。

运行前置条件见 [SKILL.md](../SKILL.md)「运行环境」及 [README.md](../README.md)：在独立 Python 环境中安装 `requirements.txt`，使用同一环境的解释器运行脚本。

- POST `https://paddleocr.aistudio-app.com/api/v2/ocr/jobs`：multipart 文件 `file`、`model` 和 JSON 字符串 `optionalPayload`；鉴权 `Authorization: bearer …`。
- 默认 `useDocOrientationClassify`、`useDocUnwarping`、`useChartRecognition` 均为 false，旋转、弯曲文档如需调整参数，另建工作目录，避免复用不兼容结果。
- 保存 `data.jobId`；GET 同地址加 `/jobId` 查询 pending/running/done/failed。只读网络失败最多重试一次，POST 不自动重试。
- done 后读取 `data.resultUrl.jsonUrl`，下载时不携带令牌。逐行解开 `result.layoutParsingResults`，核验完整页数和存在的零起始页面索引。

## 本地凭据

优先环境变量 `PADDLEOCR_ACCESS_TOKEN`，否则读取 `~/.config/parallel-reading-html/paddle-token`；文件权限应为 0600。不得输出令牌或写入可分享产物。

## 检查点和输出

工作目录的 `paddle/job.json` 保存原 PDF MD5、页数、模型、参数、jobId、状态。相同命令复用已下载结果或继续查询同一任务。若上传后响应丢失，脚本拒绝再次提交；核对控制台并将已接受任务的 jobId 恢复到检查点后续查。确认未接受任务后才可清除该失败提交的检查点并重新执行。failed、鉴权和配额问题须先解决，不循环提交。

`paddle/result.jsonl` 保留原始响应，`paddle/source.md` 是带真实文件页标记的原文，不是渐进式译文。全部页面提供 parsing_res_list 时另存 `paddle/pages.json` 并沿用 extract_paddle.py；否则统一采用逐页 Markdown 导入，不混合两套分段。若 Markdown 不符合导入契约，报告具体问题并保留原始结果，不虚构页面。

JSONL 中的页面按该任务结果顺序合并；若提供 page_index/page_idx 则必须与零起始顺序一致。返回页数或服务端 extractedPages 与原 PDF 不符时阻止翻译，不把缺失页补为空页。文件指纹始终来自原 PDF。

图片链接和布局诊断图保留在原始响应；脚本不下载 outputImages。沿用现有正文图表处理规则，交付时说明未进入 block 的内容。原文 MD 的远程图片链接不承诺永久有效。

## 后续阶段

解析导入成功后沿用 SKILL.md 的三段校准、全文转换、审计和 build/verify。在 PDF 旁交付渐进式双语 MD 与 HTML；用户明确要求先审阅 MD 时先交付该阶段结果。解析脚本本身不生成译文。

首次真实 PDF 调用前，仅离线验证不代表服务可用、额度充足或响应结构已实测。
