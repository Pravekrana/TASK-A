"""Versioned, conservative rules. This module is NOT an LLM."""
import hashlib
import json
import re

VERSION = 'rules-v1.0'
PROMPT_VERSION = 'source-review-v1'
REPL = r'(?:replacement|replacemnt|rplc|repl\b|new (?:unit|one|set)|fresh unit|reship(?:ped|ment)?)'
REFUND = r'(?:refund|rfnd|reversed the payment|amount (?:returned|back)|credited full amount|\bFR\b)'

# Ordered semantic concepts, separate from the original dropdown codes.
REASONS = [
 ('duplicate_or_failed_payment', r'double (?:charg|debit)|(?:charged|deducted|paid|payment).{0,25}twice|duplicate (?:payment|charg)|amount deducted|failed (?:order|payment)|payment failed|debited.{0,30}(?:no order|order.*fail)'),
 ('cancellation',r'cancel(?:led|lation| order| my order|ling)|cancellation'),
 ('price_adjustment',r'coupon|price (?:drop|adjust|difference)|discount.*(?:not|apply|applied)'),
 ('delivery_or_transit',r'lost in transit|damaged in transit|wrong (?:variant|product|item)|incorrect product|different (?:thing|product)|(?:order|ord|shipment|package|parcel).{0,20}(?:not delivered|not (?:received|rcvd)|delayed)|delivery delay|dlvry delay|marked.{0,12}delivered|tracking.*(?:not|stuck)|dent.{0,25}box|rto conf'),
 ('return_or_refund_followup',r'(?:refund|rfnd).{0,20}(?:pending|delay|not (?:credited|received)|status)|waiting for my refund|(?:pickup|pickp|pkp).{0,15}(?:missed|pending|not done|not.*show)|reverse (?:pickup|pkp)|nobody came.*pickup|still waiting.*refund'),
 ('product_fault',r'not charging|not taking charge|battery drain|left bud|left earbud|right earbud|no audio|silent|intermittent disconnect|pairing fail|bluetooth.*(?:fails|not)|not powering|no power|touch not responding|mic not working|not wake up|goes silent|not connect|stopped working|not turning on|dead on arrival'),
 ('warranty',r'warranty|\bwty\b'),
]

def segments(text):
    return [x.strip() for x in re.split(r'[\n|;]|\s--\s|(?<=[.!?])\s+', text) if x.strip()]

def screen(row):
    # Broad: flag OR a replacement term in either field, with no refund requirement.
    return row.get('replacement_issued') == 'Y' or bool(re.search(REPL, row.get('customer_message','')+' '+row.get('agent_notes',''), re.I))

def extract(row):
    evidence=[]; observations=[]
    for field in ['customer_message','agent_notes']:
        for s in segments(row.get(field,'')):
            if not re.search(REPL,s,re.I):continue
            state='mentioned'
            neg = re.search(r'(?:no|not|never|without|didn.t|did not).{0,22}'+REPL+'|'+REPL+r'.{0,20}(?:not (?:sent|shipped|issued)|denied|declined|cancelled|canceled)',s,re.I)
            if re.search(REPL+r'.{0,20}cancel|cancel.{0,15}'+REPL,s,re.I):state='cancelled'
            elif neg:state='denied'
            elif re.search(r'offer|option|either|instead|opted',s,re.I):state='offered'
            elif re.search(r'tomorrow|will (?:send|ship|dispatch)|going out|also sending|to be (?:sent|shipped)',s,re.I):state='requested'
            elif field=='customer_message':
                if re.search(r'(?:received|got|delivered).{0,25}'+REPL+'|'+REPL+r'.{0,20}(?:received|arrived|delivered)',s,re.I):state='completed'
                else:state='requested'
            elif re.search(REPL+r'.{0,22}(?:dispatched|shipped|sent|given|delivered|issued)|(?:dispatched|shipped|sent|issued).{0,22}'+REPL+r'|reshipped|both.{0,30}(?:replacement|rplc).{0,8}given',s,re.I):state='completed'
            elif re.search(r'raised|approved|arranged|\brma\b',s,re.I):state='requested'
            observations.append(state); evidence.append({'field':field,'quote':s,'label':state})
    completed='completed' in observations
    contradictory=completed and any(s in observations for s in ['denied','cancelled'])
    if contradictory:state='unknown'
    elif completed:state='completed'
    else:state=next((s for s in ['cancelled','denied','offered','requested','mentioned'] if s in observations),'unknown' if row.get('replacement_issued')=='Y' else 'none')
    flag_conflict=(row.get('replacement_issued')=='N' and completed) or (row.get('replacement_issued')=='Y' and state in ['denied','cancelled','offered','none'])
    reason='unknown'; reason_evidence=[]
    # Closing notes first, customer opening next. Intake category is never a target.
    for field in ['agent_notes','customer_message']:
        for label,pattern in REASONS:
            matched=next((s for s in segments(row.get(field,'')) if re.search(pattern,s,re.I)),None)
            if matched:
                reason=label; reason_evidence=[{'field':field,'quote':matched,'label':label}];break
        if reason!='unknown':break
    result={'mode':'rules-only','version':VERSION,'replacement_state':state,'reason_inferred':reason,'replacement_evidence':evidence,'reason_evidence':reason_evidence,'text_conflict':contradictory,'flag_conflict':flag_conflict,'needs_review':state in ['unknown','mentioned','requested'] or flag_conflict or contradictory or reason=='unknown','screened':screen(row)}
    validate_evidence(row,result)
    return result

def validate_evidence(row,result):
    for e in result['replacement_evidence']+result['reason_evidence']:
        if e['field'] not in ['customer_message','agent_notes'] or not e['quote'] or e['quote'] not in row.get(e['field'],''):
            raise ValueError('Evidence must be an exact nonempty excerpt of a source field')

def cached_extract(row,cache_dir=None):
    payload={k:row.get(k,'') for k in ['customer_message','agent_notes','replacement_issued']}
    key=hashlib.sha256(json.dumps([VERSION,PROMPT_VERSION,payload],sort_keys=True).encode()).hexdigest()
    path=cache_dir/f'{key}.json' if cache_dir else None
    if path and path.exists():
        result=json.loads(path.read_text());validate_evidence(row,result);return result,True
    result=extract(row)
    if path:path.write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    return result,False
