"""A synthetic evaluation fixture, never used for real accuracy or money."""
import csv,hashlib,json
from pathlib import Path
p=Path('demo/reference');p.mkdir(exist_ok=True)
rows=[r for r in csv.DictReader(Path('demo/tickets.csv').open()) if r['source_system']=='helpdesk']
packet=[];labels=[]
for i,r in enumerate(rows,1):
 r={**r,'linked_order_id':r['order_id'],'refund_minor':str(int(r['refund_amount_inr'] or 0)*100)}
 key='order:'+r['order_id'];packet.append({'sample_id':i,'case_key':key,'stratum':'synthetic','primary_ticket_id':r['ticket_id'],'tickets':[r]})
 labels.append({'sample_id':i,'case_key':key,'stratum':'synthetic','reason':'product_fault','duplicate_compensation_evidence':i==1,'evidence':[{'ticket_id':r['ticket_id'],'field':'customer_message','quote':'item stopped working'}],'uncertainty':'Synthetic fixture, not a real case or accuracy sample.'})
for name,obj in [('source_packet',packet),('labels',labels),('manifest',{'labeler':'Synthetic fixture author','population':'Six deliberately authored synthetic demo orders; no population inference','eligible_groups':6,'seed':None,'detector_sha256':hashlib.sha256(Path('vireo/extract.py').read_bytes()).hexdigest()})]: (p/(name+'.json')).write_text(json.dumps(obj,indent=2))
