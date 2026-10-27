"""Describe a query screenshot without inferring account-wide emptiness."""
KNOWN_HEADERS = {'证券代码','证券名称','委托时间','成交时间','委托数量','成交数量','委托价格',
                 '成交价格','成交均价','成交金额','合同编号','撤消数量','交易市场','操作','备注'}
EMPTY_MESSAGES = {
    'orders': {'当前没有可撤委托单': ('no_cancelable_orders_visible', 'cancelable_orders_only'),
               '当前没有委托记录': ('no_order_rows_visible', 'current_view_only')},
    'trades': {'当前没有成交记录': ('no_trade_rows_visible', 'current_view_only'),
               '当前没有成交数据': ('no_trade_rows_visible', 'current_view_only')}
}


def describe_query(ocr, page):
    if page not in ('orders','trades'):
        raise ValueError('Only read-only query pages are supported')
    scale=ocr.get('scale')
    if scale not in (2,3):
        raise ValueError('Unsupported image scale')
    headers=[];body=[]
    for line in ocr.get('lines',[]):
        words=sorted(line['words'],key=lambda w:w['left'])
        header=''.join(w['text'].strip() for w in words if w['top']<20*scale)
        content=''.join(w['text'].strip() for w in words if w['top']>=20*scale)
        if header:headers.append(header)
        if content:body.append(content)
    matches=sorted(label for label in KNOWN_HEADERS if any(label in line for line in headers))
    result={'page_requested':page,'status':'inconclusive','executable':False,'verified':False,
            'complete_account':False,'exact_header_matches':matches,'row_count':None,
            'coverage':'unknown','reason':'No authoritative record extraction'}
    if any('委托日期' in line or '成交日期' in line for line in headers):
        result['reason']='Dated history schema observed; current-day page not established'
        return result
    discriminator='委托时间' if page=='orders' else '成交时间'
    if not {'证券代码','证券名称',discriminator}.issubset(matches):
        result['reason']='Expected page headers are missing; do not reuse another query table'
        return result
    result['page_schema_observed']=True
    for text in body:
        if text in EMPTY_MESSAGES[page]:
            result['status'],result['coverage']=EMPTY_MESSAGES[page][text]
            result['reason']='Exact empty-message observation only; filters and trading date remain unverified'
            return result
    result['reason']='Expected basic headers observed; body is unreadable or records require further parsing'
    return result
