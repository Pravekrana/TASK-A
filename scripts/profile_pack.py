"""Read-only pack profile, including evidence for source-specific unit normalization."""
import csv, hashlib, json, re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

root=Path('.')
out=Path('private'); out.mkdir(exist_ok=True)
profile={}
allrows={}
for name in ['tickets','agents','orders','customers','products']:
 p=next(root.glob(f'*{name}.csv'))
 rows=list(csv.DictReader(p.open(encoding='utf-8-sig'))); allrows[name]=rows
 profile[name]={'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rows':len(rows),'columns':{k:{'blank':sum(not r[k] for r in rows),'distinct':len({r[k] for r in rows})} for k in rows[0]}}
g=defaultdict(list)
for r in allrows['tickets']:g[r['ticket_id']].append(r)
dups=[x for x in g.values() if len(x)>1]
profile['duplicate_conflicts']=dict(Counter(k for x in dups for k in x[0] if len({r[k] for r in x})>1))
profile['duplicates']={'groups':len(dups),'refund_pairs':sum(bool(x[0]['refund_amount_inr']) for x in dups),'all_refund_pairs_100x':all(Decimal(next(r['refund_amount_inr'] for r in x if r['source_system']=='legacy_fd'))==100*Decimal(next(r['refund_amount_inr'] for r in x if r['source_system']=='helpdesk')) for x in dups if x[0]['refund_amount_inr'])}
notes=[]
for r in allrows['tickets']:
 if r['source_system']=='legacy_fd' and r['refund_amount_inr']:
  for m in re.finditer(r'\bRs\.?\s*([0-9,]+(?:\.\d{1,2})?)',r['agent_notes'],re.I):
   amount=Decimal(m.group(1).replace(',',''))
   notes.append({'ticket_id':r['ticket_id'],'raw_amount':r['refund_amount_inr'],'note_rupees':str(amount),'paise_hypothesis_matches':Decimal(r['refund_amount_inr'])/100==amount,'rupees_hypothesis_matches':Decimal(r['refund_amount_inr'])==amount,'excerpt':m.group()})
profile['explicit_notes']={'n':len(notes),'paise_matches':sum(x['paise_hypothesis_matches'] for x in notes),'rupee_matches':sum(x['rupees_hypothesis_matches'] for x in notes)}
orders={r['order_id']:r for r in allrows['orders']}
comparisons=[]
for r in allrows['tickets']:
 if r['source_system']=='legacy_fd' and r['refund_amount_inr'] and r['order_id'] in orders:
  o=orders[r['order_id']]
  if (o['customer_id'],o['sku'])==(r['customer_id'],r['product_sku']):
   comparisons.append((Decimal(r['refund_amount_inr']),Decimal(o['order_value_inr'])))
profile['legacy_direct_order_values']={'n':len(comparisons),'raw_exceeds_order':sum(a>b for a,b in comparisons),'normalized_exceeds_order':sum(a/100>b for a,b in comparisons),'normalized_equals_order':sum(a/100==b for a,b in comparisons)}
times=[]
for x in g.values():
 r=next((r for r in x if r['source_system']=='helpdesk'),x[0])
 if not r['resolved_at']:continue
 c=datetime.fromisoformat(r['created_at']); d=datetime.fromisoformat(r['resolved_at'])
 migrated=c<datetime(2025,9,14)
 times.append({'ticket_id':r['ticket_id'],'source_system':r['source_system'],'reimported':len(x)>1,'migrated_by_creation':migrated,'created_at':r['created_at'],'resolved_at_raw':r['resolved_at'],'resolution_before_creation':d<c,'resolution_before_response':d<datetime.fromisoformat(r['first_response_at']),'plus_330_fixes_creation':d<c<=d+timedelta(minutes=330),'raw_resolution_month':d.strftime('%Y-%m'),'possible_ist_resolution_month':(d+timedelta(minutes=330)).strftime('%Y-%m')})
profile['timestamps']={label:{'n':len(rr),'before_creation':sum(r['resolution_before_creation'] for r in rr),'before_response':sum(r['resolution_before_response'] for r in rr),'plus330_fixes_creation':sum(r['plus_330_fixes_creation'] for r in rr),'month_changes_if_shifted':sum(r['raw_resolution_month']!=r['possible_ist_resolution_month'] for r in rr)} for label,rr in [('migrated',[r for r in times if r['migrated_by_creation']]),('reimported',[r for r in times if r['reimported']]),('current',[r for r in times if not r['migrated_by_creation']])]}
for name,rows in [('unit_note_evidence',notes),('timestamp_audit',times)]:
 with (out/f'{name}.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
(out/'pack_profile.json').write_text(json.dumps(profile,indent=2))
print(json.dumps({k:v for k,v in profile.items() if k not in allrows},indent=2))
