"""Entirely synthetic, no client rows or identifying facts."""
import csv
from pathlib import Path
p=Path('demo');p.mkdir(exist_ok=True)
def write(name,rows):
 with (p/(name+'.csv')).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
write('agents',[dict(agent_id='DEMO-A',name='Demo Agent',site='Demo site',team='Returns Desk',shift='Morning',tier='1',from_date='2020-01-01',to_date='')])
write('customers',[dict(customer_id='DEMO-C'+str(i),name='Synthetic Customer '+str(i),city='Demo City',state='XX',signup_date='2025-01-01',care_plus='N') for i in range(1,7)])
write('products',[dict(sku='DEMO-SKU',product_name='Synthetic Headphones',family='headphones',launch_date='2024-01-01',unit_cost_inr='400',retail_price_inr='1000',warranty_months='12')])
write('orders',[dict(order_id='DEMO-O'+str(i),customer_id='DEMO-C'+str(i),sku='DEMO-SKU',order_date='2025-01-01',channel='demo',qty='1',order_value_inr='1000',lot_code='DEMO') for i in range(1,7)])
rows=[]
notes=['Refund issued; replacement dispatched as goodwill.','Replacement was offered, customer chose refund.','Replacement not sent. Refund issued.','Replacement raised; waiting for dispatch.','New unit shipped under DOA.','No refund; resolved with instructions.']
for i,n in enumerate(notes,1):
 rows.append(dict(ticket_id='DEMO-T'+str(i),created_at='2026-06-'+('30' if i==6 else f'{i:02d}')+' 09:00',first_response_at='2026-06-'+('30' if i==6 else f'{i:02d}')+' 09:10',resolved_at='2026-06-'+('30' if i==6 else f'{i:02d}')+' 11:00',status='resolved',channel='email',customer_id='DEMO-C'+str(i),order_id='DEMO-O'+str(i),product_sku='DEMO-SKU',category='Other',priority='Normal',assigned_team='Email Frontline',agent_id='DEMO-A',transfers='1',csat_score='4' if i%2 else '',refund_amount_inr='1000' if i<5 else '',refund_reason_code='GW-OTHER' if i<5 else '',replacement_issued='Y' if i in [1,3,4,5] else 'N',customer_message='Synthetic example: item stopped working. Please help.',agent_notes=n,source_system='helpdesk'))
rows.append({**rows[0],'source_system':'legacy_fd','refund_amount_inr':'100000'})
write('tickets',rows)
(p/'README.txt').write_text('SYNTHETIC DEMO ONLY. No business findings derive from this fixture. The included rule demonstrates mutual exclusivity of refund and replacement; it is not a copy of client policy.\n')
