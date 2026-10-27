import unittest
from app.navigation_ocr import find_query_labels


def ocr(text, scale=2):
    return {'scale':scale,'lines':[{'words':[{'text':c,'left':i*10*scale,'top':20*scale,
        'width':10*scale,'height':10*scale} for i,c in enumerate(text)]}]}


class NavigationTests(unittest.TestCase):
    def test_exact_query_with_leading_icon(self):
        self.assertEqual(find_query_labels(ocr('囗当日委托'),100,200)[0]['label'],'当日委托')

    def test_summary_query_not_same_as_today(self):
        self.assertEqual(find_query_labels(ocr('当日委托汇总查询'),0,0),[])

    def test_typo_not_guessed(self):
        self.assertEqual(find_query_labels(ocr('资金股伤'),0,0),[])

    def test_scale_conversion_consistent(self):
        self.assertEqual(find_query_labels(ocr('资金股份',2),10,20),
                         find_query_labels(ocr('资金股份',3),10,20))
