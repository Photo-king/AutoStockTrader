"""Conservative parsing of visible holdings OCR. Output is never executable."""
import re


class OcrParseError(ValueError):
    pass


def parse_visible_positions(ocr):
    scale = ocr.get('scale')
    if scale != 2:
        raise OcrParseError('Unsupported OCR image scale')
    words = [w for line in ocr['lines'] for w in line['words']]
    headers = []
    for line in ocr['lines']:
        group = sorted([w for w in line['words'] if w['top'] < 20*scale], key=lambda w: w['left'])
        if not group:
            continue
        left = min(w['left'] for w in group)
        right = max(w['left']+w['width'] for w in group)
        if right-left > 150*scale:
            raise OcrParseError('Merged or ambiguous header')
        headers.append({'text': ''.join(w['text'].strip() for w in group), 'center': (left+right)/2})
    headers.sort(key=lambda h: h['center'])
    required = {'code': '证券代码', 'name': '证券名称', 'total_quantity': '股票余额', 'available_quantity': '可用余额'}
    bounds = {}
    for field, label in required.items():
        matches = [i for i, h in enumerate(headers) if h['text'] == label]
        if len(matches) != 1:
            raise OcrParseError('Missing or ambiguous header: '+label)
        index = matches[0]
        if index == 0 or index == len(headers)-1:
            raise OcrParseError('Missing neighboring column boundary')
        bounds[field] = ((headers[index-1]['center']+headers[index]['center'])/2,
                         (headers[index]['center']+headers[index+1]['center'])/2)

    def in_column(word, field):
        center = word['left']+word['width']/2
        return bounds[field][0] < center < bounds[field][1]

    code_words = sorted([w for w in words if w['top'] >= 20*scale and in_column(w, 'code')],
                        key=lambda w: w['top']+w['height']/2)
    groups = []
    for word in code_words:
        y = word['top']+word['height']/2
        if not groups or abs(groups[-1]['y']-y) > 5*scale:
            groups.append({'y': y, 'words': [word]})
        else:
            groups[-1]['words'].append(word)
    if not groups:
        raise OcrParseError('No readable code rows; this does not establish an empty account')
    rows = []
    for group in groups:
        code = ''.join(w['text'] for w in sorted(group['words'], key=lambda w: w['left']))
        if not re.fullmatch(r'[0-9]{6}', code):
            raise OcrParseError('Unreadable security code')
        cells = {}
        for field in ('name', 'total_quantity', 'available_quantity'):
            cell = [w for w in words if in_column(w, field) and
                    abs(w['top']+w['height']/2-group['y']) <= 5*scale]
            cells[field] = ''.join(w['text'].strip() for w in sorted(cell, key=lambda w: w['left']))
        if not cells['name']:
            raise OcrParseError('Missing security name')
        for field in ('total_quantity', 'available_quantity'):
            if not re.fullmatch(r'[0-9]+', cells[field]):
                raise OcrParseError('Unreadable quantity: '+field)
            cells[field] = int(cells[field])
        if cells['available_quantity'] > cells['total_quantity']:
            raise OcrParseError('Available quantity exceeds total quantity')
        rows.append({'code': code, **cells})
    if len({row['code'] for row in rows}) != len(rows):
        raise OcrParseError('Duplicate visible security code')
    return {'status': 'visible_candidates_only', 'source': 'windows_native_ocr',
            'verified': False, 'executable': False, 'complete_portfolio': False, 'rows': rows}
