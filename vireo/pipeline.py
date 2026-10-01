import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import pandas as pd
from .extract import cached_extract, VERSION

UNKNOWN='Unknown/unallocated'
POLICY='Policy v3.2 section 5 (effective 2025-04-01): no refund AND replacement for the same order; escalate to Team Lead and Finance. Replacement planning cost = unit cost + Rs 340.'

def locate(root,name):
    matches=list(Path(root).glob('*'+name))
    if len(matches)!=1:raise ValueError(f'Expected exactly one {name} in {root}; found {len(matches)}')
    return matches[0]

def money(value,source='helpdesk'):
    if not str(value).strip():return 0
    if source not in ['helpdesk','legacy_fd']:raise ValueError(f'Unknown monetary source {source}')
    n=Decimal(str(value))*(1 if source=='legacy_fd' else 100)
    if not n.is_finite() or n!=n.to_integral_value() or n<0:raise ValueError(f'Invalid money {value}')
    return int(n)

def deduplicate(raw):
    if raw.ticket_id.eq('').any():raise ValueError('Blank ticket identity')
    d=raw.copy();d['export_row']=range(2,len(d)+2)
    d['refund_minor']= [money(v,s) for v,s in zip(d.refund_amount_inr,d.source_system)]
    d['rank']=d.source_system.map({'helpdesk':0,'legacy_fd':1})
    d=d.sort_values(['ticket_id','rank','export_row'],kind='stable')
    chosen=d.drop_duplicates('ticket_id',keep='first').copy()
    selected=chosen.set_index('ticket_id').export_row.to_dict()
    audit=[]
    for tid,g in d.groupby('ticket_id',sort=False):
        conflicts=[c for c in raw.columns if g[c].nunique()>1]
        for r in g.to_dict('records'):
            audit.append({'ticket_id':tid,'export_row':r['export_row'],'source_system':r['source_system'],'raw_refund':r['refund_amount_inr'],'normalized_minor':r['refund_minor'],'retained_row':selected[tid],'decision':'retain' if r['export_row']==selected[tid] else 'discard','conflicting_fields':'|'.join(conflicts),'normalized_amount_conflict':g.refund_minor.nunique()>1,'rule':'helpdesk preferred; earliest export row within same source; no field merging'})
    return chosen.drop(columns='rank').reset_index(drop=True),pd.DataFrame(audit),d

def link_orders(tickets,orders):
    if orders.order_id.duplicated().any():raise ValueError('Nonunique order keys')
    byid=orders.set_index('order_id').to_dict('index')
    fallback={k:g for k,g in orders.groupby(['customer_id','sku'])}
    links=[]
    for r in tickets.to_dict('records'):
        oid=r['order_id'];o=byid.get(oid);status='unresolved_no_match';linked=''
        if oid:
            if o is None:status='direct_missing'
            elif (o['customer_id'],o['sku'])!=(r['customer_id'],r['product_sku']):status='direct_inconsistent'
            else:status='direct';linked=oid
        else:
            candidates=fallback.get((r['customer_id'],r['product_sku']))
            if candidates is not None:
                if len(candidates)==1:
                    o=candidates.iloc[0].to_dict();linked=o['order_id'];status='fallback_unique'
                else:status='fallback_ambiguous'
        # Dates are checked, never used to force an otherwise ambiguous fallback.
        future=False
        if linked:
            future=pd.to_datetime(o['order_date'])>pd.to_datetime(r['created_at'],errors='coerce')
            if future:status+=';order_after_ticket'
        links.append({'linked_order_id':linked,'order_link_status':status,'order_qty':int(o['qty']) if linked else 0,'order_value_minor':money(o['order_value_inr']) if linked else 0,'order_after_ticket':bool(future)})
    return pd.concat([tickets.reset_index(drop=True),pd.DataFrame(links)],axis=1)

def join_agents(tickets,agents):
    # ISO date comparison includes the assignment's final calendar day, with no fan-out.
    roster={key:g.to_dict('records') for key,g in agents.groupby('agent_id')}
    rows=[]
    for r in tickets.to_dict('records'):
        raw_date=r['resolved_at'] or r['created_at'];date=raw_date[:10]
        valid=[a for a in roster.get(r['agent_id'],[]) if date and a['from_date']<=date and (not a['to_date'] or date<=a['to_date'])]
        if len(valid)==1:
            a=valid[0];rows.append({'agent_name':a['name'],'roster_team':a['team'],'tier':a['tier'],'assignment_status':'valid_resolution_date' if r['resolved_at'] else 'creation_proxy'})
        else:rows.append({'agent_name':UNKNOWN,'roster_team':UNKNOWN,'tier':UNKNOWN,'assignment_status':'overlap' if len(valid)>1 else 'no_valid_assignment'})
    return pd.concat([tickets.reset_index(drop=True),pd.DataFrame(rows)],axis=1)

def aggregate(d,keys):
    x=d.copy();x['refund_ticket']=x.refund_minor.gt(0).astype(int)
    x['csat_numeric']=pd.to_numeric(x.csat_score,errors='coerce')
    x['completed']=x.status.isin(['resolved','closed']).astype(int)
    result=x.groupby(keys,dropna=False).agg(ticket_count=('ticket_id','size'),refund_count=('refund_ticket','sum'),refund_minor=('refund_minor','sum'),completed_count=('completed','sum'),csat_response_count=('csat_numeric','count'),csat_mean=('csat_numeric','mean')).reset_index()
    result['refund_rate_all_attributed_tickets']=result.refund_count/result.ticket_count
    result['csat_response_rate_all_tickets']=result.csat_response_count/result.ticket_count
    result['refund_inr']=result.refund_minor.map(lambda n:f'{int(n)//100}.{int(n)%100:02d}')
    return result

def exceptions(d,products):
    costs={r.sku:money(r.unit_cost_inr)+34000 for r in products.itertuples()}
    d=d.copy();d['case_key']=[('order:'+o) if o else ('ticket:'+t) for o,t in zip(d.linked_order_id,d.ticket_id)]
    cases=[]
    for key,g in d.groupby('case_key',sort=True):
        refunds=g[g.refund_minor>0]
        if refunds.empty:continue
        potential=g[g.screened | g.replacement_issued.eq('Y')]
        if potential.empty:continue
        complete=g[g.replacement_state.eq('completed') & ~g.text_conflict]
        same=complete[complete.refund_minor>0]
        if not complete.empty:
            status='evidence_supported' if not same.empty else 'cross_ticket_candidate'
        elif g.replacement_state.isin(['unknown','mentioned','requested']).any():status='unresolved_candidate'
        else:status='not_supported'
        if g.order_after_ticket.any() and status=='evidence_supported':status='unresolved_candidate'
        # One planned replacement per order at most; quantities >1 are deliberately not inferred.
        cost=costs.get(g.iloc[0].product_sku,0) if (g.product_sku.nunique()==1 and not complete.empty) else 0
        refund=int(refunds.refund_minor.sum());period=refunds.month.max()
        dates=pd.to_datetime(refunds.created_at,errors='coerce')
        post=bool(dates.notna().all() and (dates>=pd.Timestamp('2025-04-01')).all())
        uncertainty=[]
        if not key.startswith('order:'):uncertainty.append('Order unresolved; excluded from savings baseline to avoid duplicate remedies')
        if status=='cross_ticket_candidate':uncertainty.append('Different tickets share order; chronology and remedy purpose require review')
        if g.order_after_ticket.any():uncertainty.append('Order date after ticket creation')
        if g.flag_conflict.any():uncertainty.append('Structured replacement flag contradicts text')
        if len(g)>1:uncertainty.append('Multiple tickets; full order timeline must be reviewed')
        if (g.order_qty>1).any():uncertainty.append('Multi-unit order; one replacement planning unit only, quantity unverified')
        if not post:uncertainty.append('Pre-policy/unknown date; retrospective policy application is an assumption; excluded from goal')
        uncertainty.append('Notes are evidence, not dispatch ledger or customer entitlement verification')
        conservative=min(cost,refund) if status=='evidence_supported' and key.startswith('order:') and post else 0
        ev=[{'ticket_id':r.ticket_id,**e} for r in g.itertuples() for e in json.loads(r.replacement_evidence)]
        cases.append({'case_key':key,'linked_order_id':g.iloc[0].linked_order_id,'ticket_ids':'|'.join(g.ticket_id),'refund_ticket_ids':'|'.join(refunds.ticket_id),'replacement_ticket_ids':'|'.join(complete.ticket_id),'month':period,'period_basis':'latest refund-bearing ticket creation; one order once across archive','status':status,'refund_minor':refund,'estimated_replacement_minor':cost,'conservative_increment_minor':conservative,'policy_effective':post,'policy':POLICY,'uncertainty':'; '.join(uncertainty),'evidence':json.dumps(ev,ensure_ascii=False),'raw_flags':'|'.join(g.replacement_issued),'raw_codes':'|'.join(g.refund_reason_code),'review_status':'unreviewed'})
    cols=['case_key','linked_order_id','ticket_ids','refund_ticket_ids','replacement_ticket_ids','month','period_basis','status','refund_minor','estimated_replacement_minor','conservative_increment_minor','policy_effective','policy','uncertainty','evidence','raw_flags','raw_codes','review_status']
    return pd.DataFrame(cases,columns=cols)

def business(d,cases,review_path=None):
    # Pack coverage ends 30 Jun 2026. For demo or a different pack use last fully ended quarter by max creation day.
    maxdate=pd.to_datetime(d.created_at,errors='coerce').max()
    q=maxdate.to_period('Q')
    if maxdate.date()<q.end_time.date():q=q-1
    start=str(q.start_time.date());end=str(q.end_time.date())
    period=d[(d.created_at.str[:10]>=start)&(d.created_at.str[:10]<=end)]
    ref=period[period.refund_minor>0]
    # One linked refund order in this quarter once. Other-quarter events do not establish this quarter's numerator.
    eligible=set(ref[ref.linked_order_id.ne('') & ~ref.order_after_ticket].linked_order_id)
    supporting=period[(period.refund_minor>0)&period.replacement_state.eq('completed')&~period.text_conflict&~period.order_after_ticket]
    supported=set(supporting.linked_order_id)-{''}
    review_count=0
    if review_path:
        reviews=json.loads(Path(review_path).read_text())
        verified=set()
        lookup=d.set_index('ticket_id').to_dict('index')
        for review in reviews:
            tid=review['ticket_id'];row=lookup.get(tid)
            if row is None:continue
            payload={k:str(row[k]) if k=='refund_minor' else row[k] for k in ['customer_message','agent_notes','refund_minor','created_at']};payload['ticket_id']=tid
            digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
            if digest!=review['source_sha256']:raise ValueError('Business source review is stale: '+tid)
            for e in review['evidence']:
                if not e['quote'] or e['quote'] not in row[e['field']]:raise ValueError('Business review quote mismatch')
            if review['decision']=='support_candidate':verified.add(row['linked_order_id'])
        review_count=len(reviews);supported &= verified
    c=cases[cases.linked_order_id.isin(eligible & supported)&cases.conservative_increment_minor.gt(0)].copy()
    quarter_refunds=ref.groupby('linked_order_id').refund_minor.sum().to_dict()
    c['quarter_refund_minor']=c.linked_order_id.map(quarter_refunds)
    c['conservative_increment_minor']=[min(int(r),int(cost)) for r,cost in zip(c.quarter_refund_minor,c.estimated_replacement_minor)]
    completed=period.status.isin(['resolved','closed'])
    score=pd.to_numeric(period.loc[completed,'csat_score'],errors='coerce')
    n=len(c);den=len(eligible);inc=int(c.conservative_increment_minor.sum())
    return {'quarter':str(q),'start':start,'end':end,'tickets':len(period),'refund_tickets':len(ref),'refund_minor':int(ref.refund_minor.sum()),'baseline_order_count':n,'eligible_refund_orders':den,'baseline_rate':n/den if den else 0,'target_reduction_fraction':0.5,'proposed_target_rate':n/den*0.5 if den else 0,'target_horizon':'90 days after pilot launch','owner':'Neha Kulkarni, Support Operations, with Returns Desk Team Lead and Finance','candidate_refund_minor':int(c.quarter_refund_minor.sum()),'candidate_replacement_planning_minor':int(c.estimated_replacement_minor.sum()),'conservative_increment_minor':inc,'projected_quarterly_savings_minor':inc//2,'uncertainty_lower_savings_minor':0,'cases':c.case_key.tolist(),'csat_mean':float(score.mean()) if score.notna().any() else None,'csat_responses':int(score.notna().sum()),'csat_eligible_completed':int(completed.sum()),'csat_response_rate_completed':float(score.notna().sum()/completed.sum()) if completed.any() else None,'csat_response_rate_all_tickets':float(pd.to_numeric(period.csat_score,errors='coerce').notna().mean()),'csat_scores_on_incomplete_tickets':int(pd.to_numeric(period.loc[~completed,'csat_score'],errors='coerce').notna().sum()),'ai_source_review_count':review_count,'mode':'rules-only candidates with frozen AI-assisted source review for goal eligibility; no human validation' if review_path else 'rules-only; provisional, no human validation','assumption':'One legitimate remedy remains. Use min(recorded refund, one replacement unit cost + Rs 340) per eligible order as conservative avoidable increment. Assumes that second remedy was unnecessary and could be intercepted. Pilot removes 50% of this increment; actual realization can be zero. Not ledger reconciliation or achieved savings.'}

def run(root,out,cache=True,review_path=None):
    started=time.perf_counter();root=Path(root);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    frames={};manifest={}
    for name in ['tickets','agents','orders','customers','products']:
        p=locate(root,name+'.csv');frames[name]=pd.read_csv(p,dtype=str,keep_default_na=False)
        manifest[name]={'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rows':len(frames[name])}
    raw=frames['tickets'];d,audit,normalized=deduplicate(raw)
    naive=sum(money(v) for v in raw.refund_amount_inr)
    normalized_total=int(normalized.refund_minor.sum());final=int(d.refund_minor.sum())
    bridge=pd.DataFrame([{'stage':'Naive exported sum interpreted as rupees','change_minor':naive,'balance_minor':naive},{'stage':'Correct legacy paise to rupees','change_minor':normalized_total-naive,'balance_minor':normalized_total},{'stage':'Remove migration re-import copies','change_minor':final-normalized_total,'balance_minor':final},{'stage':'Final ticket refund total (not bank ledger)','change_minor':0,'balance_minor':final}])
    d=link_orders(d,frames['orders']);d=join_agents(d,frames['agents'])
    for key,table in [('customer_id','customers'),('sku','products')]:
        if frames[table][key].duplicated().any():raise ValueError(f'Nonunique {table} keys')
    d['customer_known']=d.customer_id.isin(frames['customers'].customer_id)
    d['product_known']=d.product_sku.isin(frames['products'].sku)
    d['refund_reason_raw']=d.refund_reason_code
    d['reason_bucket']=d.refund_reason_code.replace('',UNKNOWN)
    d['agent_bucket']=d.agent_id.replace('',UNKNOWN)
    d['month']=pd.to_datetime(d.created_at,errors='coerce').dt.strftime('%Y-%m').fillna('Unknown date')
    d['reporting_date_basis']='creation month as exported IST; refund timing proxy'
    d['migrated_by_creation']=pd.to_datetime(d.created_at,errors='coerce')<pd.Timestamp('2025-09-14')
    cache_dir=out/'cache' if cache else None
    if cache_dir:cache_dir.mkdir(exist_ok=True)
    results=[];hits=0
    for r in d.to_dict('records'):
        e,hit=cached_extract(r,cache_dir);hits+=hit
        results.append({k:json.dumps(v,ensure_ascii=False) if isinstance(v,list) else v for k,v in e.items()})
    d=pd.concat([d,pd.DataFrame(results)],axis=1)
    assert len(d)==raw.ticket_id.nunique() and d.ticket_id.is_unique
    tables={'monthly':aggregate(d,['month']),'monthly_reason':aggregate(d,['month','reason_bucket']),'monthly_agent':aggregate(d,['month','agent_bucket','agent_name','roster_team','tier']),'monthly_reason_agent':aggregate(d,['month','reason_bucket','agent_bucket','roster_team','tier']),'quarterly_cx':aggregate(d.assign(quarter=pd.to_datetime(d.created_at,errors='coerce').dt.to_period('Q').astype(str)),['quarter'])}
    for t in tables.values():assert int(t.refund_minor.sum())==final
    cases=exceptions(d,frames['products']);baseline=business(d,cases,review_path)
    goal_cases=cases[cases.case_key.isin(baseline['cases'])].copy()
    qr=d[(d.created_at.str[:10]>=baseline['start'])&(d.created_at.str[:10]<=baseline['end'])&(d.refund_minor>0)].groupby('linked_order_id').refund_minor.sum().to_dict()
    goal_cases['quarter_refund_minor']=goal_cases.linked_order_id.map(qr).astype('int64')
    goal_cases['goal_increment_minor']=[min(int(r),int(c)) for r,c in zip(goal_cases.quarter_refund_minor,goal_cases.estimated_replacement_minor)]
    assert int(goal_cases.quarter_refund_minor.sum())==baseline['candidate_refund_minor']
    assert int(goal_cases.goal_increment_minor.sum())==baseline['conservative_increment_minor']
    goal_cases.to_csv(out/'goal_cases.csv',index=False)
    for name,t in {**tables,'clean_tickets':d,'dedup_audit':audit,'reconciliation':bridge,'exceptions':cases}.items():t.to_csv(out/f'{name}.csv',index=False)
    elapsed=time.perf_counter()-started
    quality={'export_rows':len(raw),'unique_tickets':len(d),'discarded_rows':len(raw)-len(d),'refund_tickets':int(d.refund_minor.gt(0).sum()),'final_refund_minor':final,'join_rows_before':raw.ticket_id.nunique(),'join_rows_after':len(d),'order_link_status':d.order_link_status.value_counts().to_dict(),'assignment_status':d.assignment_status.value_counts().to_dict(),'missing_created_dates':int(d.month.eq('Unknown date').sum()),'missing_resolved_dates':int(d.resolved_at.eq('').sum()),'flag_conflicts':int(d.flag_conflict.sum()),'exception_statuses':cases.status.value_counts().to_dict(),'unknown_reasons':int(d.reason_inferred.eq('unknown').sum()),'input_manifest':manifest}
    usage={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'mode':'rules-only','rules_version':VERSION,'provider':None,'runtime_model':None,'api_calls':0,'tokens':0,'retries':0,'paid_inference_spend_inr':0,'tickets':len(d),'screened':int(d.screened.sum()),'screening_fraction':float(d.screened.mean()),'cache_hits':hits,'cache_misses':len(d)-hits,'elapsed_seconds':elapsed,'seconds_per_ticket':elapsed/len(d),'monthly_volume':650*52/12,'estimated_monthly_processing_seconds':elapsed/len(d)*650*52/12,'hosting':'Local machine; hardware/electricity not metered. No hosting purchased.','development_ai':'Codex GPT-6 assistance; subscription/usage cost and tokens unavailable; excluded from runtime spend.'}
    for name,obj in [('business_goal',baseline),('quality',quality),('usage_last',usage)]: (out/f'{name}.json').write_text(json.dumps(obj,indent=2,default=int),encoding='utf-8')
    with (out/'run_history.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(usage)+'\n')
    print(json.dumps({'quality':quality,'goal':baseline,'usage':usage},indent=2,default=int))
    return d,cases,baseline

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',default='demo');p.add_argument('--out',default='outputs/demo');p.add_argument('--no-cache',action='store_true');p.add_argument('--business-review',default=None);a=p.parse_args();run(a.input,a.out,not a.no_cache,a.business_review)
