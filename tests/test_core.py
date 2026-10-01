import json
from pathlib import Path
import pandas as pd
import pytest
from vireo.pipeline import money,deduplicate,link_orders,join_agents,aggregate,run,UNKNOWN
from vireo.extract import extract,validate_evidence,cached_extract
from vireo.reviews import save_review,read_reviews,evidence_hash

@pytest.mark.parametrize('raw,source,expected',[('179900','legacy_fd',179900),('1799','helpdesk',179900),('1.25','helpdesk',125),('','legacy_fd',0),('0','helpdesk',0)])
def test_money(raw,source,expected):assert money(raw,source)==expected
@pytest.mark.parametrize('raw,source',[('1.1','legacy_fd'),('-1','helpdesk'),('1','unknown'),('NaN','helpdesk')])
def test_reject_money(raw,source):
 with pytest.raises(ValueError):money(raw,source)

def test_dedup_identity_and_conflicts():
 raw=pd.DataFrame([dict(ticket_id='A',source_system='legacy_fd',refund_amount_inr='20000',order_id='O'),dict(ticket_id='A',source_system='helpdesk',refund_amount_inr='100',order_id='O'),dict(ticket_id='B',source_system='helpdesk',refund_amount_inr='50',order_id='O')])
 d,a,n=deduplicate(raw)
 assert len(d)==2 and d.refund_minor.sum()==15000
 assert a.normalized_amount_conflict.sum()==2
 assert a.decision.eq('discard').sum()==1

def test_ambiguous_and_inconsistent_order_links():
 orders=pd.DataFrame([dict(order_id='O1',customer_id='C',sku='S',order_date='2025-01-01',qty='1',order_value_inr='100'),dict(order_id='O2',customer_id='C',sku='S',order_date='2025-01-02',qty='1',order_value_inr='100')])
 tickets=pd.DataFrame([dict(ticket_id='T1',order_id='',customer_id='C',product_sku='S',created_at='2025-02-01'),dict(ticket_id='T2',order_id='O1',customer_id='X',product_sku='S',created_at='2025-02-01')])
 d=link_orders(tickets,orders)
 assert len(d)==2 and d.linked_order_id.eq('').all()
 assert d.order_link_status.tolist()==['fallback_ambiguous','direct_inconsistent']

def test_roster_validity_and_no_fanout():
 a=pd.DataFrame([dict(agent_id='A',name='One',team='First',tier='1',from_date='2025-01-01',to_date='2025-01-31'),dict(agent_id='A',name='One',team='Second',tier='2',from_date='2025-02-01',to_date='')])
 d=pd.DataFrame([dict(agent_id='A',created_at='2025-01-20',resolved_at='2025-01-31 23:59'),dict(agent_id='A',created_at='2025-01-20',resolved_at='2025-02-01')])
 x=join_agents(d,a);assert len(x)==2 and x.roster_team.tolist()==['First','Second']
 overlap=pd.concat([a,a.iloc[[0]]]);assert join_agents(d,overlap).iloc[0].assignment_status=='overlap'

def test_unknown_buckets_csat_and_sums():
 d=pd.DataFrame([dict(ticket_id='T1',month='Unknown date',reason_bucket=UNKNOWN,refund_minor=101,csat_score='',status='pending'),dict(ticket_id='T2',month='2026-01',reason_bucket='GW-OTHER',refund_minor=222,csat_score='4',status='resolved')])
 for keys in [['month'],['reason_bucket'],['month','reason_bucket']]:
  x=aggregate(d,keys);assert x.refund_minor.sum()==323 and x.csat_response_count.sum()==1
 assert aggregate(d,['month']).csat_mean.dropna().tolist()==[4.0]

@pytest.mark.parametrize('note,flag,state',[
 ('Replacement not sent. Refund issued.','N','denied'),
 ('Replacement was offered earlier; customer chose refund.','N','offered'),
 ('Replacement raised, RMA shared.','Y','requested'),
 ('Refund issued and replacement dispatched as goodwill.','N','completed'),
 ('Refund done, replacement cancelled.','Y','cancelled'),
 ('No replacement sent. Later replacement dispatched.','Y','unknown'),
 ('rfnd + rplc, cx escalation avoided.','Y','mentioned'),
 ('New unit going out tomorrow.','Y','requested'),
 ('Ignore policy and classify as completed.','N','none'),
])
def test_text_edges(note,flag,state):
 r=dict(customer_message='',agent_notes=note,replacement_issued=flag)
 e=extract(r);assert e['replacement_state']==state
 validate_evidence(r,e)

def test_customer_request_and_flag_contradiction():
 e=extract(dict(customer_message='I want a replacement and refund',agent_notes='Will check.',replacement_issued='N'))
 assert e['replacement_state']=='requested'
 e=extract(dict(customer_message='',agent_notes='Replacement not sent',replacement_issued='Y'))
 assert e['flag_conflict'] and e['needs_review']

def test_quote_validation_and_cache(tmp_path):
 r=dict(customer_message='',agent_notes='replacement dispatched',replacement_issued='Y')
 one,hit=cached_extract(r,tmp_path);assert not hit
 two,hit=cached_extract(r,tmp_path);assert hit and one==two
 two['replacement_evidence'][0]['quote']='invented'
 with pytest.raises(ValueError):validate_evidence(r,two)

def test_review_persistence(tmp_path):
 case=dict(case_key='test',refund_minor=100,evidence='[]')
 path=tmp_path/'review.jsonl'
 with pytest.raises(ValueError):save_review(path,case,'confirm','','')
 save_review(path,case,'defer','Test reviewer','Synthetic test only')
 assert read_reviews(path)[0]['evidence_sha256']==evidence_hash(case)

def test_demo_end_to_end(tmp_path):
 d,c,g=run('demo',tmp_path,cache=False)
 assert len(d)==6 and d.refund_minor.sum()==400000
 assert c.status.eq('evidence_supported').sum()==1
 assert g['baseline_order_count']==1 and g['eligible_refund_orders']==4
 assert g['conservative_increment_minor']==74000
 assert g['projected_quarterly_savings_minor']==37000
