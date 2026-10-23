#!/usr/bin/env python3
"""Submit/resume PaddleOCR asynchronous jobs, validate all pages, then import."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlparse
import requests
from import_source import digest, pdf_pages

JOB_URL = 'https://paddleocr.aistudio-app.com/api/v2/ocr/jobs'
MODEL = 'PaddleOCR-VL-1.6'
TOKEN_FILE = Path.home() / '.config/parallel-reading-html/paddle-token'
OPTIONS = {'useDocOrientationClassify': False, 'useDocUnwarping': False, 'useChartRecognition': False}


def save(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def normalize(raw, count):
    pages = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        result = json.loads(line)['result']
        items = result['layoutParsingResults']
        if not isinstance(items, list):
            raise ValueError('layoutParsingResults must be a list')
        pages.extend(items)
    if len(pages) != count:
        raise ValueError(f'Incomplete result: expected {count} pages, received {len(pages)}; translation blocked')
    for i, page in enumerate(pages):
        if not isinstance(page, dict) or not isinstance(page.get('markdown', {}).get('text'), str):
            raise ValueError(f'Page {i}: missing Markdown text')
        pruned = page.get('prunedResult', page)
        # Where the API supplies explicit zero-based indices, verify their order.
        for obj in (page, pruned):
            for key in ('page_index', 'page_idx'):
                if obj.get(key) is not None and obj[key] != i:
                    raise ValueError(f'Page order mismatch at {i}: {key}={obj[key]}')
    return pages


def fetch(session, url, headers, deadline):
    for attempt in range(2):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Time budget reached; rerun the same command to resume')
        try:
            r = session.get(url, headers=headers, timeout=min(45, remaining), allow_redirects=False)
            if r.status_code == 429 or r.status_code >= 500:
                if attempt == 0:
                    time.sleep(min(5, max(0, deadline-time.monotonic())))
                    continue
            if r.status_code != 200:
                raise ValueError(f'GET failed: HTTP {r.status_code}; checkpoint retained')
            return r
        except requests.RequestException:
            if attempt:
                raise ValueError('Network read failed twice; checkpoint retained') from None
    raise ValueError('Read failed')


def run(args):
    if args.max_seconds <= 0:
        raise ValueError('--max-seconds must be positive')
    deadline = time.monotonic() + args.max_seconds
    pdf = args.pdf.resolve()
    count, md5 = pdf_pages(pdf), digest(pdf, 'md5')
    w = args.workdir.resolve()
    manifest = w / 'run-manifest.json'
    if manifest.exists() and json.loads(manifest.read_text()).get('source', {}).get('md5') not in (None, md5):
        raise ValueError('Work directory belongs to another PDF')
    cache = w / 'paddle'
    cache.mkdir(parents=True, exist_ok=True)
    checkpoint = cache / 'job.json'
    identity = {'md5': md5, 'pageCount': count, 'model': MODEL, 'endpoint': JOB_URL, 'options': OPTIONS}
    state = json.loads(checkpoint.read_text()) if checkpoint.exists() else {'source': identity}
    if state.get('source') != identity:
        raise ValueError('Cached job does not match PDF/model/options; use a different work directory')
    raw_path = cache / 'result.jsonl'
    if not raw_path.exists():
        token = os.environ.get('PADDLEOCR_ACCESS_TOKEN') or (TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else '')
        if not token:
            raise ValueError('Configure PADDLEOCR_ACCESS_TOKEN or ~/.config/parallel-reading-html/paddle-token')
        headers = {'Authorization': f'bearer {token}'}
        session = requests.Session()
        if not state.get('jobId'):
            if state.get('submissionAttempted'):
                raise ValueError('Previous submission outcome unknown; recover its jobId before retrying to avoid duplicate jobs')
            state['submissionAttempted'] = True
            save(checkpoint, state)
            # Never retry a POST automatically: the server may already have accepted it.
            try:
                with pdf.open('rb') as f:
                    response = session.post(JOB_URL, headers=headers,
                        data={'model': MODEL, 'optionalPayload': json.dumps(OPTIONS)},
                        files={'file': (pdf.name, f, 'application/pdf')},
                        timeout=min(60, args.max_seconds), allow_redirects=False)
            except requests.RequestException:
                raise ValueError('Submission outcome unknown; checkpoint saved; do not resubmit blindly') from None
            if response.status_code != 200:
                state['submissionHttpStatus'] = response.status_code
                save(checkpoint, state)
                raise ValueError(f'Submission failed: HTTP {response.status_code}; no automatic resubmission')
            state['jobId'] = response.json()['data']['jobId']
            save(checkpoint, state)
        print(f"Paddle job: {state['jobId']}; resuming/checking", flush=True)
        while True:
            data = fetch(session, f"{JOB_URL}/{state['jobId']}", headers, deadline).json()['data']
            status = data['state']
            state['state'] = status
            save(checkpoint, state)
            print(f"state={status}; progress={data.get('extractProgress', {}).get('extractedPages', '?')}/{count}", flush=True)
            if status == 'failed':
                raise ValueError('Paddle job failed; inspect the job in the provider console; no automatic resubmission')
            if status == 'done':
                extracted = data.get('extractProgress', {}).get('extractedPages')
                if extracted is not None and extracted != count:
                    raise ValueError(f'Server extracted {extracted}/{count} pages; translation blocked')
                url = data['resultUrl']['jsonUrl']
                if urlparse(url).scheme != 'https':
                    raise ValueError('Result download must use HTTPS')
                raw = fetch(session, url, {}, deadline).text  # Never forward bearer token to result storage.
                normalize(raw, count)
                tmp = cache / 'result.jsonl.tmp'
                tmp.write_text(raw)
                tmp.replace(raw_path)
                break
            if status not in ('pending', 'running'):
                raise ValueError(f'Unknown job state: {status}')
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Time budget reached; rerun the same command to resume')
            time.sleep(min(5, remaining))
    pages = normalize(raw_path.read_text(), count)
    source_md = cache / 'source.md'
    source_md.write_text('\n\n'.join(f'<!-- pr-page: {i} -->\n\n{p["markdown"]["text"]}' for i, p in enumerate(pages)) + '\n')
    structured = all(isinstance(p.get('prunedResult', p).get('parsing_res_list'), list) for p in pages)
    if structured:
        source = cache / 'pages.json'
        save(source, pages)
    else:
        # Do not mix segmentation methods across pages; use complete per-page Markdown.
        source = source_md
        print('Structured blocks unavailable on some pages; using all page-marked Markdown')
    subprocess.run([sys.executable, str(Path(__file__).with_name('import_source.py')),
                    str(source), '--pdf', str(pdf), '--workdir', str(w)], check=True)
    print(f'Parsing and import complete. Raw JSONL and source Markdown: {cache}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('pdf', type=Path)
    p.add_argument('--workdir', type=Path, required=True)
    p.add_argument('--max-seconds', type=int, default=900, help='Bounded parsing budget; same command resumes saved job')
    args = p.parse_args()
    try:
        run(args)
    except (ValueError, KeyError, TypeError, OSError, TimeoutError, subprocess.SubprocessError):
        # Avoid exception bodies containing credentials, signed URLs or raw response content.
        exc = sys.exc_info()[1]
        message = str(exc) if isinstance(exc, (ValueError, TimeoutError)) and not isinstance(exc, json.JSONDecodeError) else type(exc).__name__
        print(f'PADDLE STOPPED: {message}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
