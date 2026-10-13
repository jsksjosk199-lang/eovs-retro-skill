#!/usr/bin/env python3
"""Flag common identifiers; never print the matched secret. Human review is required."""
import argparse
import json
import re
from pathlib import Path

PATTERNS = {
    'mobile_number': re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)'),
    'ipv4_address': re.compile(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])'),
    'email_address': re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}'),
    'absolute_user_path': re.compile(r'(?:[A-Za-z]:[\\/]|/(?:Users|home|mnt)/)[^\s\"\'<>]+'),
    'live_url': re.compile(r'https?://[^\s\"\'<>]+'),
    'credential_value': re.compile(r'(?i)(?:password|passwd|access_token|api_key|cookie|密码|口令)\s*[=:：]\s*[\"\']([^\"\'\s]{4,})[\"\']'),
}
TEXT_EXTENSIONS = {'.md', '.json', '.yaml', '.yml', '.py', '.txt', '.csv', '.html', '.js', '.toml'}


def safe_location(relative_path, forbidden):
    """A filename can itself be sensitive; never echo its identifiers."""
    label = relative_path
    for word in forbidden:
        if word:
            label = re.sub(re.escape(word), '[redacted]', label, flags=re.I)
    for regex in PATTERNS.values():
        label = regex.sub('[redacted]', label)
    return label


def scan(root, forbidden=()):
    root = Path(root).resolve()
    findings, count = [], 0
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        raw_rel = path.relative_to(root).as_posix()
        rel = safe_location(raw_rel, forbidden)
        if not path.resolve().is_relative_to(root):
            findings.append({'file': rel, 'kind': 'outside_root_link'})
            continue
        if '__pycache__' in path.parts or path.suffix.lower() in {'.pyc', '.pyo'}:
            findings.append({'file': rel, 'kind': 'compiled_cache_may_embed_private_paths'})
            continue
        for word in forbidden:
            if word and word.casefold() in raw_rel.casefold():
                findings.append({'file': rel, 'kind': 'forbidden_identifier_in_filename'})
        for kind, regex in PATTERNS.items():
            if regex.search(raw_rel):
                findings.append({'file': rel, 'kind': kind + '_in_filename'})
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            findings.append({'file': rel, 'kind': 'binary_requires_manual_metadata_and_visual_review'})
            continue
        text = path.read_text(encoding='utf-8-sig')
        count += 1
        for kind, regex in PATTERNS.items():
            for match in regex.finditer(text):
                if kind == 'ipv4_address' and not all(0 <= int(x) <= 255 for x in match.group().split('.')):
                    continue
                findings.append({'file': rel, 'kind': kind, 'line': text.count('\n', 0, match.start()) + 1})
        for word in forbidden:
            if word:
                start = text.casefold().find(word.casefold())
                if start >= 0:
                    findings.append({'file': rel, 'kind': 'forbidden_identifier', 'line': text.count('\n', 0, start) + 1})
    return {'status': 'findings' if findings else 'no_common_identifiers_found', 'text_files_scanned': count,
            'findings': findings, 'limits': '未检出不等于识别所有隐私；机构、昵称、头像、精确数字组合仍需人工审核'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('public_directory', type=Path)
    parser.add_argument('--denylist', type=Path)
    args = parser.parse_args()
    forbidden = json.loads(args.denylist.read_text(encoding='utf-8-sig')).get('forbidden', []) if args.denylist else []
    report = scan(args.public_directory, forbidden)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report['findings'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
