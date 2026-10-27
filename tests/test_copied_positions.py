import unittest
from app.copied_positions import parse_copied_positions, TableParseError

HEADER='证券代码\t证券名称\t股票余额\t可用余额\t市值\t\n'


class CopiedPositionsTests(unittest.TestCase):
    def test_exact_text_retains_code_and_values(self):
        r=parse_copied_positions(HEADER+'000001\t测试证券\t1,200\t200\t12,345.60\t\n')
        self.assertEqual(r['rows'][0]['code'],'000001')
        self.assertEqual(r['rows'][0]['total_quantity'],1200)
        self.assertEqual(r['rows'][0]['market_value'],'12345.60')
        self.assertFalse(r['executable'])
        self.assertFalse(r['complete_portfolio'])

    def test_missing_column_rejected(self):
        with self.assertRaises(TableParseError):
            parse_copied_positions(HEADER+'000001\t测试证券\t200\t100\n')

    def test_invalid_grouping_not_silently_fixed(self):
        with self.assertRaises(TableParseError):
            parse_copied_positions(HEADER+'000001\t测试证券\t1,00\t0\t100.00\t\n')

    def test_available_exceeds_total_rejected(self):
        with self.assertRaises(TableParseError):
            parse_copied_positions(HEADER+'000001\t测试证券\t100\t200\t100.00\t\n')

    def test_header_only_not_verified_empty_account(self):
        r=parse_copied_positions(HEADER)
        self.assertEqual(r['status'],'header_only_unverified')
        self.assertFalse(r['verified'])

    def test_duplicate_schema_rejected(self):
        with self.assertRaises(TableParseError):parse_copied_positions(HEADER.replace('市值','证券代码'))

    def test_duplicate_position_rejected(self):
        line='000001\t测试证券\t100\t100\t100.00\t\n'
        with self.assertRaises(TableParseError):parse_copied_positions(HEADER+line+line)

    def test_fractional_shares_rejected(self):
        with self.assertRaises(TableParseError):
            parse_copied_positions(HEADER+'000001\t测试证券\t100.5\t100\t100.00\t\n')
