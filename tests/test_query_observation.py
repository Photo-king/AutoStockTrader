import unittest
from app.query_observation import describe_query
from app.access_policy import require_input_integrity


def snapshot(headers, body=None):
    def line(text, y):
        return {'words':[{'text':text,'left':10,'top':y,'width':100,'height':20}]}
    return {'scale':2,'lines':[line(h,10) for h in headers]+([line(body,60)] if body else [])}


class QuerySafetyTests(unittest.TestCase):
    def test_empty_grid_not_interpreted_as_no_trades(self):
        r=describe_query(snapshot(['证券代码','证券名称','成交时间']), 'trades')
        self.assertEqual(r['status'],'inconclusive')
        self.assertIsNone(r['row_count'])
        self.assertFalse(r['executable'])

    def test_cancelable_message_not_all_orders(self):
        r=describe_query(snapshot(['证券代码','证券名称','委托时间'],'当前没有可撤委托单'),'orders')
        self.assertEqual(r['coverage'],'cancelable_orders_only')
        self.assertFalse(r['complete_account'])

    def test_ocr_typo_not_accepted_as_empty(self):
        r=describe_query(snapshot(['证券代码','证券名称','委托时间'],'当前发有可撒委托单'),'orders')
        self.assertEqual(r['status'],'inconclusive')

    def test_other_page_not_reused(self):
        r=describe_query(snapshot(['证券代码','证券名称','委托时间']),'trades')
        self.assertNotIn('page_schema_observed',r)

    def test_history_not_treated_as_today(self):
        r=describe_query(snapshot(['证券代码','证券名称','委托时间','委托日期']),'orders')
        self.assertNotIn('page_schema_observed',r)

    def test_exact_empty_trade_message_still_not_complete_account(self):
        r=describe_query(snapshot(['证券代码','证券名称','成交时间'],'当前没有成交记录'),'trades')
        self.assertEqual(r['status'],'no_trade_rows_visible')
        self.assertFalse(r['verified'])
        self.assertIsNone(r['row_count'])


class IntegrityTests(unittest.TestCase):
    def test_medium_cannot_drive_high(self):
        with self.assertRaises(ValueError):
            require_input_integrity({'probe':{'status':'read','rid':8192},'targets':{'1':{'status':'read','rid':12288}}})

    def test_unknown_integrity_refused(self):
        with self.assertRaises(ValueError):
            require_input_integrity({'probe':{'status':'read','rid':12288},'targets':{'1':{'status':'unavailable'}}})

    def test_matching_integrity_allowed(self):
        require_input_integrity({'probe':{'status':'read','rid':12288},'targets':{'1':{'status':'read','rid':12288}}})

    def test_no_targets_refused(self):
        with self.assertRaises(ValueError):require_input_integrity({'probe':{'status':'read','rid':12288},'targets':{}})
