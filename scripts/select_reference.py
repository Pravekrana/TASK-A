"""Freeze 60 held-out case groups. Read source only for labeling, not predictions."""
import argparse,hashlib,json,random,re
from pathlib import Path
import pandas as pd
p=argparse.ArgumentParser();p.add_argument('--out',default='outputs/real');p.add_argument('--dest',default='private/reference');a=p.parse_args()
out=Path(a.out);dest=Path(a.dest);dest.mkdir(parents=True,exist_ok=True)
d=pd.read_csv(out/'clean_tickets.csv',dtype=str,keep_default_na=False)
d['case_key']=['order:'+o if o else 'ticket:'+t for o,t in zip(d.linked_order_id,d.ticket_id)]
# All source rows actually exposed during development, plus broad early-ID exclusion.
# Exact inspected development tickets and their whole order groups are excluded.
dev_path=Path('private/development_ticket_ids.json')
dev_ids=set(json.loads(dev_path.read_text())) if dev_path.exists() else set()
dev_keys=set(d[d.ticket_id.isin(dev_ids)].case_key)
population=sorted(set(d.case_key)-dev_keys)
rng=random.Random(9302026);random_keys=rng.sample(population,30)
remaining=[k for k in population if k not in random_keys]
def has(k,pattern):
 g=d[d.case_key==k];return any(re.search(pattern,r.customer_message+' '+r.agent_notes,re.I) for r in g.itertuples())
# Enrichment uses source strata, not predicted labels. Random set never replaced.
strata=[('refund_and_flag',lambda g:g.refund_minor.astype(int).gt(0).any() and g.replacement_issued.eq('Y').any()),('refund_text_without_flag',lambda g:g.refund_minor.astype(int).gt(0).any() and g.replacement_issued.eq('N').all() and any(re.search(r'replacement|rplc|new unit|new set|reship',r.customer_message+' '+r.agent_notes,re.I) for r in g.itertuples())),('negative_or_offer',lambda g:any(re.search(r'(?:replacement|rplc).{0,35}(?:not|offer|cancel|denied)|(?:no|not).{0,15}(?:replacement|rplc)',r.agent_notes,re.I) for r in g.itertuples())),('gw_other',lambda g:g.refund_reason_code.eq('GW-OTHER').any()),('short_notes',lambda g:g.agent_notes.str.len().lt(35).any()),('legacy',lambda g:g.source_system.eq('legacy_fd').any())]
groups={k:g for k,g in d.groupby('case_key')};chosen=list(random_keys);reasons={k:'random' for k in chosen}
for name,predicate in strata:
 eligible=sorted(k for k in remaining if k not in chosen and predicate(groups[k]))
 selected=rng.sample(eligible,min(5,len(eligible)))
 for k in selected:chosen.append(k);reasons[k]=name
if len(chosen)<60:
 for k in rng.sample(sorted(set(remaining)-set(chosen)),60-len(chosen)):chosen.append(k);reasons[k]='additional_random_challenge'
sourcecols=['ticket_id','created_at','source_system','order_id','linked_order_id','order_link_status','refund_minor','refund_reason_code','replacement_issued','customer_message','agent_notes']
packet=[]
for i,key in enumerate(chosen,1):
 g=groups[key];primary=g.sort_values('ticket_id').iloc[0].ticket_id
 packet.append({'sample_id':i,'case_key':key,'stratum':'random' if reasons[key]=='random' else 'challenge','selection_reason':reasons[key],'primary_ticket_id':primary,'tickets':g[sourcecols].to_dict('records')})
(dest/'source_packet.json').write_text(json.dumps(packet,indent=2,ensure_ascii=False),encoding='utf-8')
manifest={'seed':9302026,'random_n':30,'challenge_n':len(chosen)-30,'population':'Unique unambiguously linked order groups, or single tickets when order unresolved, excluding any group containing a ticket explicitly inspected in development. Whole migration duplicates collapsed before sampling; all linked tickets stay in same split. Legacy is an explicit challenge stratum.','eligible_groups':len(population),'excluded_development_groups':len(dev_keys),'detector_sha256':hashlib.sha256(Path('vireo/extract.py').read_bytes()).hexdigest(),'selection_sha256':hashlib.sha256((dest/'source_packet.json').read_bytes()).hexdigest(),'test_set_tuning':False,'labeler':'Codex GPT-6 AI-assisted source review, not human','labels_status':'pending'}
(dest/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2))
