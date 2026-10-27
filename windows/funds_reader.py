"""Read validated funds-page Static values; never read Edit controls."""
import ctypes as C
from ctypes import wintypes as W
from decimal import Decimal, InvalidOperation
import re

FIELDS = {
    'cash_balance': ('资金余额', 1012), 'frozen_cash': ('冻结金额', 1013),
    'available_cash': ('可用金额', 1016), 'withdrawable_cash': ('可取金额', 1017),
    'stock_market_value': ('股票市值', 1014), 'position_pnl': ('持仓盈亏', 1027),
    'daily_pnl': ('当日盈亏', 1026), 'total_assets': ('总资产', 1015)
}


def read_funds(user, panel):
    user.GetParent.argtypes = [W.HWND]; user.GetParent.restype = W.HWND
    children = [c for c in panel['children'] if c['visible'] and c['class'] == 'Static']
    values = {}
    for field, (label, value_id) in FIELDS.items():
        labels = [c for c in children if c.get('label') == label]
        candidates = [c for c in children if c['control_id'] == value_id]
        if len(labels) != 1 or len(candidates) != 1:
            raise ValueError('Missing or ambiguous funds control: '+field)
        a, b = labels[0], candidates[0]
        if user.GetParent(a['handle']) != user.GetParent(b['handle']):
            raise ValueError('Funds label/value scope mismatch')
        if abs((a['rect'][1]+a['rect'][3])-(b['rect'][1]+b['rect'][3])) > 8 or b['rect'][0]<a['rect'][2]:
            raise ValueError('Funds label/value layout mismatch')
        text=C.create_unicode_buffer(256); result=C.c_size_t()
        if not user.SendMessageTimeoutW(b['handle'],13,len(text),C.addressof(text),2,300,C.byref(result)):
            raise ValueError('Funds value unreadable')
        raw=text.value.strip()
        if not re.fullmatch(r'[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]{1,4})?',raw):
            raise ValueError('Invalid funds number: '+field)
        try:values[field]=Decimal(raw.replace(',',''))
        except InvalidOperation:raise ValueError('Invalid decimal funds value')
    if any(values[f]<0 for f in ['cash_balance','frozen_cash','available_cash','withdrawable_cash','stock_market_value','total_assets']):
        raise ValueError('Negative unsigned funds value')
    consistent=abs(values['cash_balance']+values['stock_market_value']-values['total_assets'])<=Decimal('.02')
    return {'status':'read_only_observation','values':{k:str(v) for k,v in values.items()},
            'cash_plus_market_equals_assets':consistent,'executable':False,'broker_identity_verified':False}
