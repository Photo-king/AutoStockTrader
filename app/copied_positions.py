"""Strict parsing of freshly copied broker TSV, without numeric guesses."""
import csv
from decimal import Decimal
import io
import re


class TableParseError(ValueError):
    pass


def decimal_value(raw):
    text=raw.strip()
    if not re.fullmatch(r'[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?',text):
        raise TableParseError('Invalid table number')
    return Decimal(text.replace(',',''))


def parse_copied_positions(text):
    table=[row for row in csv.reader(io.StringIO(text),delimiter='\t') if any(cell.strip() for cell in row)]
    if not table:raise TableParseError('No table; cannot infer an empty account')
    headers=[cell.strip() for cell in table[0]]
    nonempty=[h for h in headers if h]
    if len(nonempty)!=len(set(nonempty)):raise TableParseError('Duplicate column label')
    fields={'code':'证券代码','name':'证券名称','total_quantity':'股票余额','available_quantity':'可用余额'}
    if not set(fields.values()).issubset(headers):raise TableParseError('Missing holdings schema')
    rows=[]
    for cells in table[1:]:
        if len(cells)!=len(headers):raise TableParseError('Column count mismatch')
        record={h:cells[i].strip() for i,h in enumerate(headers) if h}
        code=record['证券代码']
        if not re.fullmatch(r'[0-9]{6}',code):raise TableParseError('Invalid security code')
        if not record['证券名称']:raise TableParseError('Missing security name')
        row={'code':code,'name':record['证券名称']}
        for field in ('total_quantity','available_quantity'):
            value=decimal_value(record[fields[field]])
            if value<0 or value!=value.to_integral_value():raise TableParseError('Invalid share quantity')
            row[field]=int(value)
        if row['available_quantity']>row['total_quantity']:raise TableParseError('Available exceeds total')
        if '市值' in record:
            market=decimal_value(record['市值'])
            if market<0:raise TableParseError('Negative market value')
            row['market_value']=str(market)
        rows.append(row)
    if len({r['code'] for r in rows})!=len(rows):raise TableParseError('Duplicate security code')
    return {'status':'copied_table_candidates' if rows else 'header_only_unverified',
            'source':'fresh_broker_clipboard','rows':rows,'verified':False,'executable':False,
            'complete_portfolio':False}
