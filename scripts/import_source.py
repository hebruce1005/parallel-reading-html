#!/usr/bin/env python3
"""Import existing page-mapped JSON/Markdown. Never OCR or extract PDF text."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGE_COMMENT = re.compile(r'^<!--\s*(?:pr-page\s*:\s*|pdfPageIndex\s*=\s*)(\d+)(?:\s*;\s*printed\s*:\s*([^>]+?))?\s*-->$')
PAGE_HEADING = re.compile(r'^#{1,6}\s+(?:PDF\s*第\s*(\d+)\s*页|第\s*(\d+)\s*页\s*·\s*印刷页\s*\S+)(?:\s*[（(].*[）)])?\s*$')
BLOCK_COMMENT = re.compile(r'^<!--\s*(block-\d+)\s*[;·]\s*(?:source-page\s*:\s*|pdfPageIndex\s*=\s*)(\d+).*?-->$')
FOOTNOTE = re.compile(r'\$\s*\^\{([^}]*)\}\s*\$')


def fail(message):
    raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path, algorithm='sha256'):
    return hashlib.new(algorithm, Path(path).read_bytes()).hexdigest()


def pdf_pages(path):
    try:
        import pymupdf
        with pymupdf.open(path) as doc:
            return len(doc)
    except ImportError:
        try:
            from pypdf import PdfReader
            return len(PdfReader(path).pages)
        except ImportError:
            result = subprocess.run(['pdfinfo', str(path)], capture_output=True, text=True, check=True)
            match = re.search(r'^Pages:\s+(\d+)', result.stdout, re.M)
            if not match:
                fail('无法读取 PDF 页数；需要 pymupdf、pypdf 或 pdfinfo（不执行 OCR）。')
            return int(match.group(1))


def page_number(value):
    if type(value) is not int or value < 0:
        fail(f'文件页码必须是从零开始的非负整数：{value!r}')
    return value


def folio(value):
    if value is None:
        return None
    value = str(value).strip()
    return value if re.fullmatch(r'\d{1,4}', value) and int(value) > 0 else None


def normalize_text(text):
    text = FOOTNOTE.sub(r'$^{\1}$', text)
    text = re.sub(r'\[\^(\d+)\]:?', lambda m: '$^{' + m.group(1) + '}$', text)
    return re.sub(r'\s+', ' ', text).strip()


def markdown(path, mapped=True, translation=False):
    """Page comments/headings or explicit block markers; blank lines split unkeyed prose."""
    records, pages, lines = [], {}, []
    current_page, current_id, fence = None, None, None
    seen_ids = set()
    preamble = []

    def flush():
        nonlocal lines, current_id
        raw = '\n'.join(lines).strip()
        lines = []
        if not raw:
            if current_id:
                fail(f'Markdown 中 {current_id} 没有文本。')
            return
        if mapped and current_page is None:
            if translation:
                preamble.append(raw)
                return
            fail('MD 正文位于首个页面标记之前；请提供明确页标记或绑定该 MD 的页面映射。')
        level = 2 if re.match(r'^#{1,6}\s+', raw) else None
        kind = 'footnote' if re.match(r'^\[\^\d+\]:', raw) else 'text'
        raw = re.sub(r'^#{1,6}\s+', '', raw)
        raw = re.sub(r'^> ?', '', raw, flags=re.M)
        records.append({'id': current_id, 'page': current_page, 'printed': None,
                        'level': level, 'kind': kind, 'text': normalize_text(raw)})
        current_id = None

    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        stripped = line.strip()
        if fence:
            lines.append(line)
            if (fence == '$$' and stripped == '$$') or (fence != '$$' and stripped.startswith(fence)):
                fence = None
            continue
        if stripped.startswith(('```', '~~~')) or stripped == '$$':
            fence = stripped[:3] if stripped != '$$' else '$$'
            lines.append(line)
            continue
        pc, ph, bc = PAGE_COMMENT.fullmatch(stripped), PAGE_HEADING.fullmatch(stripped), BLOCK_COMMENT.fullmatch(stripped)
        if pc or ph or bc:
            flush()
            if bc:
                current_id, page = bc.group(1), int(bc.group(2))
                if current_id in seen_ids:
                    fail(f'Markdown block ID 重复：{current_id}')
                seen_ids.add(current_id)
                if current_page is not None and page < current_page:
                    fail('Markdown 页面顺序倒退。')
            else:
                page = int(pc.group(1)) if pc else int(ph.group(1) or ph.group(2)) - 1
                if page in pages and page != current_page:
                    fail('Markdown 页面标记重复或倒序。')
            if current_page is not None and page < current_page:
                fail('Markdown 页面顺序倒退。')
            current_page = page_number(page)
            pages.setdefault(str(page), {'printed': None})
            if pc and pc.group(2):
                pages[str(page)]['printed'] = folio(pc.group(2).strip())
            if ph:
                printed = re.search(r'印刷页(?:码)?\s*(\d+)', stripped)
                if printed:
                    pages[str(page)]['printed'] = folio(printed.group(1))
            continue
        if not stripped and current_id is None:
            flush()
        else:
            lines.append(line)
    if fence:
        fail('Markdown 的代码围栏或独立公式围栏未闭合。')
    flush()
    if translation and any(r['id'] is None for r in records):
        fail('译文 MD 必须为每个 block 提供 ID 与文件页码，不能靠段落数量猜测对应关系。')
    return records, pages


def run_extractor(script, source):
    with tempfile.TemporaryDirectory(prefix='parallel-reader-import-') as tmp:
        run = subprocess.run([sys.executable, str(HERE / script), str(source), '--workdir', tmp], capture_output=True, text=True)
        if run.returncode:
            fail(run.stderr.strip() or run.stdout.strip())
        blocks = [json.loads(x) for x in (Path(tmp) / 'blocks.jsonl').read_text().splitlines() if x.strip()]
        return blocks, read_json(Path(tmp) / 'pages.json')


def validate(blocks, pages, count, canonical=False):
    if not isinstance(pages, dict) or set(pages) != {str(i) for i in range(count)}:
        fail('页面映射必须明确覆盖 PDF 的 0..pageCount-1；缺失页不得自动当作空页。')
    if any(not isinstance(v, dict) for v in pages.values()):
        fail('pages.json 每个页面值必须是对象。')
    pages = {k: {'printed': folio(v.get('printed'))} for k, v in pages.items()}
    if not isinstance(blocks, list) or not blocks:
        fail('输入没有可用的正文 block。')
    ids, previous = set(), -1
    for index, block in enumerate(blocks):
        if not isinstance(block, dict) or (canonical and not block.get('id')):
            fail('标准 block 必须是对象且包含已有 ID。')
        p = page_number(block.get('page'))
        if p >= count or p < previous:
            fail('block 页码越界或源文顺序倒退。')
        previous = p
        bid = block.get('id') or f'block-{index + 1:04d}'
        if not re.fullmatch(r'block-\d+', bid) or bid in ids:
            fail(f'block ID 无效或重复：{bid}')
        ids.add(bid)
        if not isinstance(block.get('text'), str) or not block['text'].strip():
            fail(f'{bid} 缺少正文文本。')
        if block.get('kind', 'text') not in ('text', 'footnote'):
            fail(f'{bid} 的 kind 不受支持；须明确转换为 text 或 footnote。')
        if not canonical:
            block['text'] = FOOTNOTE.sub(r'$^{\1}$', block['text'])
        block.update(id=bid, printed=(folio(block.get('printed')) if canonical else folio(block.get('printed')) or pages[str(p)]['printed']),
                     level=block.get('level'), kind=block.get('kind', 'text'))
    return blocks, pages


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source', type=Path, help='Existing JSON/JSONL, page-marked MD, or blocks.jsonl directory')
    ap.add_argument('--pdf', type=Path, required=True, help='Used only for MD5 and page count')
    ap.add_argument('--workdir', type=Path, required=True)
    ap.add_argument('--page-map', type=Path, help='Explicit mapping for plain MD or canonical JSONL')
    ap.add_argument('--translation-md', type=Path, help='Reviewed translation with block ID/page markers; source remains required')
    args = ap.parse_args()
    count, md5 = pdf_pages(args.pdf), digest(args.pdf, 'md5')
    source, pages, provenance = args.source.resolve(), None, {}
    if source.is_dir() or source.suffix.lower() == '.jsonl':
        block_file = source / 'blocks.jsonl' if source.is_dir() else source
        blocks = [json.loads(x) for x in block_file.read_text().splitlines() if x.strip()]
        pages = read_json(args.page_map or block_file.with_name('pages.json'))
        previous_manifest = block_file.with_name('run-manifest.json')
        if previous_manifest.exists():
            origin = read_json(previous_manifest).get('source', {})
            if origin.get('md5') and origin['md5'] != md5:
                fail('源 block 的 manifest 对应另一份 PDF。')
        fmt = 'canonical-blocks'
        provenance['sourceSha256'] = digest(block_file)
    elif source.suffix.lower() == '.md':
        if args.page_map:
            mapping = read_json(args.page_map)
            if mapping.get('schema') != 'parallel-reader-md-map-v1' or mapping.get('sourceSha256') != digest(source):
                fail('MD 配套映射缺少正确 schema 或 sourceSha256；拒绝猜测 JSON 与 MD 的对应关系。')
            blocks, marked_pages = markdown(source, mapped=False)
            if marked_pages:
                fail('带页标记的 MD 请直接导入；不要同时提供逐段映射。')
            assignments = mapping.get('blocks', [])
            if len(blocks) != len(assignments):
                fail('MD 段落数与配套映射中的 block 数不一致。')
            for b, a in zip(blocks, assignments):
                b.update({k: a[k] for k in ('id', 'page', 'printed', 'kind', 'level') if k in a})
            pages = mapping.get('pages')
        else:
            blocks, pages = markdown(source)
        fmt = 'markdown'
        provenance['sourceSha256'] = digest(source)
    else:
        data = read_json(source)
        if isinstance(data, dict) and 'blocks' in data and 'pages' in data:
            origin = data.get('source', {})
            if origin.get('md5') and origin['md5'] != md5:
                fail('JSON 指纹对应另一份 PDF。')
            blocks, pages, fmt = data['blocks'], data['pages'], 'canonical-json'
        elif isinstance(data, list) and data and all(isinstance(p, dict) and isinstance((p.get('prunedResult') or p).get('parsing_res_list'), list) for p in data):
            if len(data) != count:
                fail('PaddleOCR JSON 的逐页记录数与 PDF 页数不一致。')
            blocks, pages = run_extractor('extract_paddle.py', source)
            fmt = 'paddleocr-json'
        elif isinstance(data, list) and data and all(isinstance(b, dict) and 'page_idx' in b for b in data):
            indices = {page_number(b['page_idx']) for b in data}
            if indices != set(range(count)):
                fail('page_idx JSON 未明确覆盖全部 PDF 页，不能推断缺失页为空页。')
            blocks, printed = run_extractor('extract.py', source)
            pages = {str(i): printed.get(str(i), {'printed': None}) for i in range(count)}
            fmt = 'page-idx-json'
            provenance['omittedNonTextItems'] = sum(not (b.get('text') or '').strip() and b.get('type') in ('table','chart','image') for b in data)
        else:
            fail('未知 JSON 结构；支持 PaddleOCR 逐页结果、page_idx 列表或 {blocks, pages}，不得猜测页码字段。')
        provenance['sourceSha256'] = digest(source)
    blocks, pages = validate(blocks, pages, count, canonical=fmt.startswith('canonical'))
    translation = None
    if args.translation_md:
        translated, _ = markdown(args.translation_md, translation=True)
        if [(b['id'], b['page']) for b in translated] != [(b['id'], b['page']) for b in blocks]:
            fail('译文 MD 的 block ID、顺序或页码与源 block 不一致；不能复用。')
        translation = '\n'.join(b['text'] for b in translated) + '\n'
    w = args.workdir
    manifest_path = w / 'run-manifest.json'
    manifest = read_json(manifest_path) if manifest_path.exists() else {}
    origin = manifest.get('source', {})
    if origin.get('md5') and origin['md5'] != md5:
        fail('目标工作目录属于另一份 PDF；请另选目录。')
    if list(w.glob('zh-*.txt')) and not origin.get('md5'):
        fail('目标目录已有无源指纹的译文；请另选目录并显式核验后复用。')
    block_text = '\n'.join(json.dumps(b, ensure_ascii=False) for b in blocks) + '\n'
    page_text = json.dumps(pages, ensure_ascii=False, indent=1) + '\n'
    pending = {'blocks.jsonl': block_text, 'pages.json': page_text}
    for name, content in pending.items():
        path = w / name
        if path.exists() and path.read_text() != content:
            actual = [json.loads(x) for x in path.read_text().splitlines()] if name.endswith('.jsonl') else read_json(path)
            expected = blocks if name.endswith('.jsonl') else pages
            if actual != expected:
                fail(f'{name} 与已有契约不同；拒绝覆盖或重分段，请另选目录。')
    if translation is not None:
        existing = sorted(w.glob('zh-*.txt'))
        if existing:
            old = '\n'.join(line for p in existing for line in p.read_text().splitlines() if line.strip()) + '\n'
            if old != translation:
                fail('已有译文与提供的 MD 不同；拒绝覆盖。')
        else:
            pending['zh-01.txt'] = translation
    w.mkdir(parents=True, exist_ok=True)
    for name, content in pending.items():
        if not (w / name).exists():
            (w / name).write_text(content)
    manifest.setdefault('completedBatches', [])
    manifest.setdefault('source', {}).update(pdf=str(args.pdf.resolve()), md5=md5, pageCount=count)
    manifest['blockContract'] = {**manifest.get('blockContract', {}), 'count': len(blocks), 'sha256': digest(w / 'blocks.jsonl')}
    manifest['import'] = {'format': fmt, 'sourcePath': str(source), **provenance, 'pdfUse': 'fingerprint and page count only', 'translationMd': str(args.translation_md.resolve()) if args.translation_md else None}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'Imported {fmt}: pages={count} blocks={len(blocks)} md5={md5}')
    for page in range(count):
        items = [b for b in blocks if b['page'] == page]
        print(f'  page={page} printed={pages[str(page)]["printed"]} blocks={len(items)} chars={sum(len(b["text"]) for b in items)}')
    if provenance.get('omittedNonTextItems'):
        print(f'NOTE: {provenance["omittedNonTextItems"]} table/chart/image items lack text and were omitted; consult the source PDF.')
    if translation is not None:
        print(f'Reused reviewed translation: {len(blocks)} lines; no translation generated.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f'IMPORT FAILED: {exc}', file=sys.stderr)
        sys.exit(1)
