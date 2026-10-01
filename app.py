"""Streamlit app. No model credentials or network services required."""
import argparse
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from vireo.pipeline import run,aggregate
from vireo.reviews import save_review,read_reviews,evidence_hash

parser=argparse.ArgumentParser(add_help=False)
parser.add_argument('--input',default='demo');parser.add_argument('--out',default='outputs/demo');parser.add_argument('--business-review',default='')
args,_=parser.parse_known_args()
st.set_page_config(page_title='Vireo — Refund evidence',layout='wide')
st.title('Vireo · Refund evidence')
st.caption('Rules-only prototype • recorded ticket refunds, not bank-ledger payments • local review')
root=st.sidebar.text_input('Input folder',args.input)
out=st.sidebar.text_input('Output folder',args.out)
review_path=st.sidebar.text_input('Optional frozen AI business review JSON',args.business_review)
if st.sidebar.button('Load supplied CSVs / rebuild',type='primary'):
    try:
        with st.spinner('Reconciling and extracting evidence…'):run(root,out,review_path=review_path or None)
        st.success('Rebuilt successfully')
    except Exception as e:st.error(str(e));st.stop()
p=Path(out)
if not (p/'clean_tickets.csv').exists():
    st.info('Use demo + outputs/demo for synthetic data, or . + outputs/real for the supplied pack. Click Load to start.');st.stop()
d=pd.read_csv(p/'clean_tickets.csv',keep_default_na=False)
cases=pd.read_csv(p/'exceptions.csv',keep_default_na=False)
goal=json.loads((p/'business_goal.json').read_text())
quality=json.loads((p/'quality.json').read_text())
if d.ticket_id.astype(str).str.startswith('DEMO-').all():st.warning('SYNTHETIC DEMO — these records are not business findings.')
st.caption('Creation month, as exported in IST, is a reporting proxy. No refund-payment timestamp exists. Legacy resolution timezone is unresolved; no timestamp shift applied.')
tabs=st.tabs(['Monthly refunds','Exception review','Business goal','Validation and cost'])
def table_download(frame,name):
    st.dataframe(frame,hide_index=True,width='stretch')
    st.download_button('Download '+name,frame.to_csv(index=False).encode('utf-8-sig'),name+'.csv','text/csv',key=name)
with tabs[0]:
    a,b,c=st.columns(3)
    months=a.multiselect('Creation month',sorted(d.month.unique()))
    reasons=b.multiselect('Original reason code',sorted(d.reason_bucket.unique()))
    teams=c.multiselect('Resolving agent roster team',sorted(d.roster_team.unique()))
    agent_ids=st.multiselect('Resolving agent ID',sorted(d.agent_bucket.unique()))
    f=d.copy()
    for col,values in [('month',months),('reason_bucket',reasons),('roster_team',teams),('agent_bucket',agent_ids)]:
        if values:f=f[f[col].isin(values)]
    st.metric('Recorded refunds — filtered',f"Rs {f.refund_minor.sum()/100:,.2f}")
    st.caption(f'{len(f):,} attributed tickets; {(f.refund_minor>0).sum():,} refund-bearing tickets. Refund rate denominator includes all tickets attributed to that agent, including open/pending records. No productivity ranking.')
    breakdown=st.radio('Breakdown',['Monthly','Original reason','Resolving agent','Reason × agent'],horizontal=True)
    keys={'Monthly':['month'],'Original reason':['month','reason_bucket'],'Resolving agent':['month','agent_bucket','agent_name','roster_team','tier'],'Reason × agent':['month','reason_bucket','agent_bucket','roster_team','tier']}[breakdown]
    table_download(aggregate(f,keys),'filtered_summary')
    st.info('Returns Desk processes refunds by design. assigned_team is first routing; roster_team describes the resolving agent. Compare roles with context; do not compare Tier 1 and Tier 2 productivity.')
    st.subheader('Whole-pack reconciliation')
    bridge=pd.read_csv(p/'reconciliation.csv');bridge['change_inr']=bridge.change_minor/100;bridge['balance_inr']=bridge.balance_minor/100
    table_download(bridge,'reconciliation')
with tabs[1]:
    st.write('Source evidence is provisional. Confirm means a reviewer supports escalation; it does not block a payment or deny a customer remedy.')
    status=st.multiselect('Evidence status',sorted(cases.status.unique()),default=[s for s in ['evidence_supported','cross_ticket_candidate','unresolved_candidate'] if s in set(cases.status)])
    visible=cases[cases.status.isin(status)] if status else cases
    table_download(visible[['case_key','ticket_ids','month','status','refund_minor','estimated_replacement_minor','conservative_increment_minor']],'exception_queue')
    if len(visible):
        key=st.selectbox('Review case',visible.case_key.tolist());case=visible[visible.case_key==key].iloc[0].to_dict()
        st.write(case['policy']);st.warning(case['uncertainty'])
        if review_path and Path(review_path).exists():
            ai_reviews=[r for r in json.loads(Path(review_path).read_text()) if r['case_key']==key]
            if ai_reviews:
                st.caption('Frozen AI-assisted source review — provisional, not a human decision')
                st.json(ai_reviews)
        st.write(f"Recorded refund: Rs {case['refund_minor']/100:,.2f}; replacement planning cost: Rs {case['estimated_replacement_minor']/100:,.2f}. These are separate amounts, not combined savings.")
        st.json(json.loads(case['evidence']))
        related=d[d.ticket_id.isin(case['ticket_ids'].split('|'))]
        st.dataframe(related[['ticket_id','order_id','linked_order_id','order_link_status','refund_amount_inr','source_system','refund_minor','refund_reason_raw','reason_inferred','replacement_issued','replacement_state','flag_conflict']],hide_index=True)
        st.caption('Customer text may contain personal details. Keep this panel collapsed during a public recording.')
        with st.expander('Both source fields and inferred-reason evidence'):
            for r in related.to_dict('records'):
                st.write(r['ticket_id']);st.text(r['customer_message']);st.text(r['agent_notes']);st.json(json.loads(r['reason_evidence']))
        trail=read_reviews(p/'reviews'/'decisions.jsonl');prior=[r for r in trail if r['case_key']==key]
        if prior:
            st.write('Latest saved review',prior[-1])
            if prior[-1]['evidence_sha256']!=evidence_hash(case):st.warning('Evidence changed since this review; review again.')
        with st.form('review'):
            decision=st.radio('Decision',['defer','confirm','reject'],horizontal=True)
            reviewer=st.text_input('Reviewer name or initials');note=st.text_area('Rationale / required follow-up')
            if st.form_submit_button('Save locally'):
                try:save_review(p/'reviews'/'decisions.jsonl',case,decision,reviewer,note);st.success('Saved to local append-only review trail. Financial baseline remains provisional.')
                except ValueError as e:st.error(str(e))
        if trail:table_download(pd.DataFrame(trail),'saved_reviews')
with tabs[2]:
    st.caption('Baseline mode: '+goal['mode'])
    st.subheader(f"Proposed 90-day pilot · {goal['quarter']} baseline")
    st.write(f"Reduce evidence-supported refund-plus-replacement orders from {goal['baseline_order_count']} / {goal['eligible_refund_orders']} linked refund orders ({goal['baseline_rate']:.2%}) to a proposed {goal['proposed_target_rate']:.2%} within 90 days, worth approximately Rs {goal['projected_quarterly_savings_minor']/100:,.0f} per quarter under the stated assumptions.")
    st.write('Owner: '+goal['owner'])
    st.write('Action: Returns Desk checks a shared order remedy record before approving a second remedy, then escalates conflicts to the Team Lead and Finance. Preserve one legitimate remedy and a prompt customer response.')
    st.write(goal['assumption'])
    st.write(f"Candidate refund cash Rs {goal['candidate_refund_minor']/100:,.0f}; estimated replacement planning cost Rs {goal['candidate_replacement_planning_minor']/100:,.0f}; conservative increment Rs {goal['conservative_increment_minor']/100:,.0f}. Projected realization range Rs 0–{goal['projected_quarterly_savings_minor']/100:,.0f}; no savings achieved by this offline tool.")
    if goal['csat_mean'] is not None:st.write(f"Customer safeguard: maintain measured CSAT {goal['csat_mean']:.2f}/5 ({goal['csat_responses']} responses), monitoring response rate ({goal['csat_response_rate_completed']:.1%} of completed tickets) and remedy delays. Blank scores excluded.")
    st.caption('50% is a proposed pilot target, not a causal estimate: allow half the increment for legitimate exceptions, completion uncertainty and intervention misses. Latest quarter cases must still be reviewed. SLA store credits and contact costs are excluded.')
    table_download(pd.read_csv(p/'goal_cases.csv') if (p/'goal_cases.csv').exists() else cases[cases.case_key.isin(goal['cases'])],'goal_supporting_cases')
    table_download(pd.read_csv(p/'quarterly_cx.csv'),'quarterly_cx')
with tabs[3]:
    st.json(quality)
    if (p/'evaluation.json').exists():st.json(json.loads((p/'evaluation.json').read_text()))
    else:st.info('No reference-set evaluation in this output folder. Unit tests are not classification accuracy.')
    st.json(json.loads((p/'usage_last.json').read_text()))
    st.caption('No paid runtime model calls. Rules caching reduces local work only. Development AI subscription cost is unavailable, not free. Monthly scenario: 650 × 52 ÷ 12 = 2,816.67 tickets; local hardware/electricity and human review are unpriced.')
