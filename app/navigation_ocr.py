"""Locate only three read-only query labels; do not guess OCR spelling."""
LABELS={'holdings':'资金股份','orders':'当日委托','trades':'当日成交'}


def find_query_labels(raw, left, top):
    scale=raw['scale']
    if scale not in (2,3):raise ValueError('Unsupported navigation OCR scale')
    targets=[]
    for line in raw['lines']:
        words=sorted(line['words'],key=lambda w:w['left'])
        text=''.join(w['text'].strip() for w in words)
        matched=[label for label in LABELS.values() if text.endswith(label) and len(text)-len(label)<=2]
        if len(matched)!=1:continue
        label=matched[0];suffix=[];count=0
        for word in reversed(words):
            suffix.insert(0,word);count+=len(word['text'].strip())
            if count>=len(label):break
        if ''.join(w['text'].strip() for w in suffix)!=label:continue
        targets.append({'label':label,'rect':[left+min(w['left'] for w in suffix)/scale,
            top+min(w['top'] for w in suffix)/scale,
            left+max(w['left']+w['width'] for w in suffix)/scale,
            top+max(w['top']+w['height'] for w in suffix)/scale]})
    return targets
