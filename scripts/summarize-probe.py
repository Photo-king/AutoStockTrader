#!/usr/bin/env python3
"""Print non-sensitive capability findings from the latest desktop probe."""
import collections
import json
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'reports/desktop-report.json'
r = json.loads(path.read_text(encoding='utf-8-sig'))
if 'error' in r:
    raise SystemExit(r['error'])
print('Checked:', r['checked_at'])
print('Desktop session:', r['probe_session'])
print('Input desktop accessible:', r['input_desktop_accessible'])
print('Screen:', r['screen'])
for pid in r['target_pids']:
    windows = [w for w in r['windows'] if w['pid'] == pid]
    visible = [w for w in windows if w['visible']]
    substantial = [w for w in visible if w['rect'][2] - w['rect'][0] >= 400
                   and w['rect'][3] - w['rect'][1] >= 250]
    print('PID', pid, '| visible windows:', len(visible), '| full panels:', len(substantial))
    for w in substantial:
        print('  Class:', w['class'], '| rect:', w['rect'])
        print('  Child controls:', dict(collections.Counter(c['class'] for c in w['children'])))
for field in ['integrity','navigation_inspection','funds_inspection','query_inspection','positions_inspection','copy_inspection']:
    if r.get(field) is not None:
        print(field + ':', r[field])
print('This probe does not establish broker login, readable balances, order execution, or unattended reliability.')
