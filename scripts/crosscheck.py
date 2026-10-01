"""Independent stdlib/Decimal calculation: does not import the pipeline."""
import argparse,csv,json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--input',default='.');p.add_argument('--out',default='outputs/real');a=p.parse_args()
root=Path(a.input);out=Path(a.out)
rows=list(csv.DictReader(next(root.glob('*tickets.csv')).open(encoding='utf-8-sig')))
chosen={}
for r in rows:
 key=r['ticket_id']
 if key not in chosen or (chosen[key]['source_system']=='legacy_fd' and r['source_system']=='helpdesk'):chosen[key]=r
monthly=defaultdict(Decimal)
for r in chosen.values():
 value=Decimal(r['refund_amount_inr'] or '0')/(100 if r['source_system']=='legacy_fd' else 1)
 monthly[r['created_at'][:7] or 'Unknown date']+=value
actual={r['month']:Decimal(r['refund_inr']) for r in csv.DictReader((out/'monthly.csv').open())}
assert dict(monthly)==actual, (dict(monthly),actual)
naive=sum(Decimal(r['refund_amount_inr'] or '0') for r in rows)
unit=sum(Decimal(r['refund_amount_inr'] or '0')/(100 if r['source_system']=='legacy_fd' else 1) for r in rows)
final=sum(monthly.values())
bridge=list(csv.DictReader((out/'reconciliation.csv').open()))
assert [Decimal(r['balance_minor'])/100 for r in bridge]==[naive,unit,final,final]
result={'method':'Independent csv.DictReader + Decimal, no pipeline import','raw_rows':len(rows),'unique_ids':len(chosen),'naive_inr':str(naive),'unit_corrected_inr':str(unit),'final_inr':str(final),'duplicate_removed_inr':str(unit-final),'monthly_exact_match':True,'months':{k:str(v) for k,v in sorted(monthly.items())}}
(out/'independent_crosscheck.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
