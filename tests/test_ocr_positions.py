import copy
import unittest
from app.ocr_positions import parse_visible_positions, OcrParseError


def fixture():
    headers = ['操作', '证券代码', '证券名称', '股票余额', '实际数量', '可用余额', '冻结数量']
    centers = [20, 100, 200, 300, 400, 500, 600]
    def word(text, center, top):
        return {'text': text, 'left': center-20, 'top': top, 'width': 40, 'height': 20}
    lines = [{'words': [word(text, x, 10)]} for text, x in zip(headers, centers)]
    lines += [{'words': [word(text, x, 60)]} for text, x in
              [('000001', 100), ('测试证券', 200), ('200', 300), ('200', 400), ('100', 500), ('0', 600)]]
    return {'scale': 2, 'lines': lines}


class ParserSafetyTests(unittest.TestCase):
    def test_candidate_preserves_leading_zero_and_cannot_execute(self):
        r = parse_visible_positions(fixture())
        self.assertEqual(r['rows'][0]['code'], '000001')
        self.assertFalse(r['executable'])
        self.assertFalse(r['complete_portfolio'])
        self.assertFalse(r['verified'])

    def test_missing_header_is_not_empty_account(self):
        f = fixture()
        f['lines'] = f['lines'][1:3] + f['lines'][4:]
        with self.assertRaises(OcrParseError):
            parse_visible_positions(f)

    def test_unreadable_quantity_rejected(self):
        f = fixture()
        f['lines'][9]['words'][0]['text'] = '2OO'
        with self.assertRaises(OcrParseError):
            parse_visible_positions(f)

    def test_available_over_total_rejected(self):
        f = fixture()
        f['lines'][11]['words'][0]['text'] = '300'
        with self.assertRaises(OcrParseError):
            parse_visible_positions(f)

    def test_no_rows_does_not_mean_empty_account(self):
        f = fixture()
        f['lines'] = f['lines'][:7]
        with self.assertRaises(OcrParseError):
            parse_visible_positions(f)

    def test_duplicate_code_rejected(self):
        f = fixture()
        second = copy.deepcopy(f['lines'][7:])
        for line in second:
            for word in line['words']:
                word['top'] += 40
        f['lines'].extend(second)
        with self.assertRaises(OcrParseError):
            parse_visible_positions(f)

    def test_split_code_tokens_join_in_column_order(self):
        f = fixture()
        f['lines'][7]['words'] = [
            {'text':'000','left':80,'top':60,'width':20,'height':20},
            {'text':'001','left':100,'top':60,'width':20,'height':20}]
        self.assertEqual(parse_visible_positions(f)['rows'][0]['code'], '000001')


if __name__ == '__main__':
    unittest.main()
