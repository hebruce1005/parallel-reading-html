#!/usr/bin/env python3
"""Render an evidence-based research overview before the mapped PDF pages."""
import argparse
import json
import re
from pathlib import Path


def esc(value: str) -> str:
    return (value.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def render(config: dict) -> str:
    o = config.get('overview')
    if not isinstance(o, dict):
        raise ValueError('config requires an overview object')
    kind = o.get('type')
    required = {'puzzle': '研究困惑', 'method': '研究方法', 'conclusion': '研究结论'}
    if kind == 'theory':
        required.update({'contribution': '关键理论贡献', 'argument': '论证过程'})
    elif kind == 'quantitative':
        required.update({'data': '数据来源', 'regression': '量化与回归方法'})
    elif kind == 'qualitative':
        required.update({'caseSelection': '案例选择', 'comparison': '案例比较方法'})
    else:
        raise ValueError('overview.type must be theory, quantitative, or qualitative')
    missing = [key for key in required if not isinstance(o.get(key), str) or not o[key].strip()]
    if missing:
        raise ValueError('overview missing: ' + ', '.join(missing))
    rows = '\n'.join(f'<div class="pr-overview-item"><h3>{label}</h3><p>{esc(o[key])}</p></div>'
                     for key, label in required.items())
    return '<section class="pr-overview" aria-label="研究概览">\n<h2>研究概览</h2>\n' + rows + '\n</section>'


def update_html(html: str, config: dict) -> str:
    overview = render(config)
    if '.pr-overview {' not in html:
        css = (Path(__file__).parent / 'assets' / 'reading.css').read_text()
        rules = '\n'.join(line for line in css.splitlines() if line.startswith(('.pr-overview ', '.pr-overview h2', '.pr-overview-item')))
        html = html.replace('</style>', rules + '\n</style>', 1)
    if re.search(r'<section class="pr-overview".*?</section>', html, re.S):
        return re.sub(r'<section class="pr-overview".*?</section>', overview, html, count=1, flags=re.S)
    marker = '</header>'
    if html.count(marker) != 1:
        raise ValueError('expected one document header')
    return html.replace(marker, marker + '\n' + overview, 1)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--html', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    args = p.parse_args()
    args.html.write_text(update_html(args.html.read_text(), json.loads(args.config.read_text())))
