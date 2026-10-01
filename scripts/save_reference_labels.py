"""Validate and serialize actual source-review labels; never calls the detector."""
import hashlib,importlib.util,json
from pathlib import Path
root=Path('private/reference')
spec=importlib.util.spec_from_file_location('reviewed',root/'reviewed_labels_spec.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
packet=json.loads((root/'source_packet.json').read_text());labels=[]
for number,reason,field,quote,state,both,rep_tid,rep_field,rep_quote,uncertainty in m.SPECS:
 case=packet[number-1];tickets={r['ticket_id']:r for r in case['tickets']};primary=case['primary_ticket_id']
 assert quote in tickets[primary][field],(number,quote)
 ev=[dict(ticket_id=primary,field=field,quote=quote,purpose='reason')]
 if rep_tid:
  tid='TK-'+rep_tid;assert rep_quote in tickets[tid][rep_field],(number,rep_quote)
  ev.append(dict(ticket_id=tid,field=rep_field,quote=rep_quote,purpose='replacement'))
 labels.append(dict(sample_id=number,case_key=case['case_key'],stratum=case['stratum'],primary_ticket_id=primary,reason=reason,replacement_state=state,duplicate_compensation_evidence=both,evidence=ev,uncertainty=uncertainty,labeler='Codex GPT-6 AI-assisted source review',human_reviewed=False,provisional=True))
assert len(labels)==60
(root/'labels.json').write_text(json.dumps(labels,indent=2,ensure_ascii=False),encoding='utf-8')
manifest=json.loads((root/'manifest.json').read_text());manifest['labels_status']='60 source-reviewed provisional AI-assisted labels; no human validation';manifest['labels_sha256']=hashlib.sha256((root/'labels.json').read_bytes()).hexdigest();(root/'manifest.json').write_text(json.dumps(manifest,indent=2))
print('Validated 60 labels and all exact source quotes; no detector predictions used.')
