#!/usr/bin/env python3
"""Parse private OCR without printing holdings or treating OCR as an order source."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ocr_positions import parse_visible_positions, OcrParseError

root = Path(__file__).resolve().parents[1]
report = json.loads((root / 'reports/desktop-report.json').read_text())
ocr = json.loads((root / '.local/query-ocr-private.json').read_text())
try:
    if not ocr.get('observed_at') or ocr['observed_at'] != report.get('captured_at') or (report.get('ocr_inspection') or {}).get('status') != 'recognized':
        raise OcrParseError('OCR does not match current successful capture')
    result = parse_visible_positions(ocr)
except OcrParseError as exc:
    result = {'status': 'unreadable', 'reason': str(exc), 'executable': False, 'complete_portfolio': False}
report = json.loads((root / 'reports/desktop-report.json').read_text())
result['observed_at'] = ocr.get('observed_at')
(root / '.local/positions-ocr-candidates.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print('OCR parse status:', result['status'])
print('Visible candidate rows:', len(result.get('rows', [])))
print('Executable:', result['executable'])
if 'reason' in result:
    print('Reason:', result['reason'])
