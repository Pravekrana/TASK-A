"""Reproducible comparison to frozen AI-assisted source labels, NOT human ground truth."""
import argparse,hashlib,json,math
from pathlib import Path
import pandas as pd
from .extract import extract,screen

def wilson(k,n):
    if not n:return None
    z=1.96;p=k/n;den=1+z*z/n;center=(p+z*z/(2*n))/den;delta=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,center-delta),min(1,center+delta)]

def evaluate(reference,out):
    reference=Path(reference);out=Path(out)
    packet=json.loads((reference/'source_packet.json').read_text());labels=json.loads((reference/'labels.json').read_text());manifest=json.loads((reference/'manifest.json').read_text())
    digest=hashlib.sha256(Path('vireo/extract.py').read_bytes()).hexdigest()
    if digest!=manifest['detector_sha256']:raise ValueError('Detector changed since holdout freeze; disclose tuning and create a new held-out set')
    cases=pd.read_csv(out/'exceptions.csv',keep_default_na=False).set_index('case_key').to_dict('index')
    rows=[]
    for case,label in zip(packet,labels):
        assert case['case_key']==label['case_key']
        source={r['ticket_id']:r for r in case['tickets']}
        for e in label['evidence']:assert e['quote'] and e['quote'] in source[e['ticket_id']][e['field']]
        inferred=extract(source[case['primary_ticket_id']]);pred=cases.get(case['case_key'],{})
        screened=any(screen(r) for r in case['tickets'])
        positive=pred.get('status') in ['evidence_supported','cross_ticket_candidate']
        truth=label['duplicate_compensation_evidence']
        abstain=pred.get('status')=='unresolved_candidate'
        rows.append({'sample_id':case['sample_id'],'case_key':case['case_key'],'stratum':case['stratum'],'ticket_count':len(case['tickets']),'reference_positive':truth,'predicted_positive':positive,'confusion':'TP' if truth and positive else 'FN' if truth else 'FP' if positive else 'TN','detection_abstained':abstain,'screened':screened,'screening_miss':truth and not screened,'reference_reason':label['reason'],'predicted_reason':inferred['reason_inferred'],'primary_has_refund':int(source[case['primary_ticket_id']]['refund_minor'])>0,'reason_correct':label['reason']==inferred['reason_inferred'],'reason_abstained':inferred['reason_inferred']=='unknown','legacy_in_group':any(r['source_system']=='legacy_fd' for r in case['tickets']),'gw_other_in_group':any(r['refund_reason_code']=='GW-OTHER' for r in case['tickets']),'y_flag_in_group':any(r['replacement_issued']=='Y' for r in case['tickets']),'uncertainty':label['uncertainty']})
    frame=pd.DataFrame(rows);stats={}
    for stratum,g in frame.groupby('stratum'):
        tp=int(g.confusion.eq('TP').sum());fp=int(g.confusion.eq('FP').sum());fn=int(g.confusion.eq('FN').sum());tn=int(g.confusion.eq('TN').sum());reason_covered=g[~g.reason_abstained];refund_reasons=g[g.primary_has_refund]
        stats[stratum]={'case_groups':len(g),'source_tickets':int(g.ticket_count.sum()),'TP':tp,'FP':fp,'FN':fn,'TN':tn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,'precision_wilson_95':wilson(tp,tp+fp),'recall_wilson_95':wilson(tp,tp+fn),'binary_error_rate_in_sample':(fp+fn)/len(g),'detection_abstentions':int(g.detection_abstained.sum()),'detection_coverage':float((~g.detection_abstained).mean()),'refund_primary_reason_cases':len(refund_reasons),'refund_primary_reason_correct':int(refund_reasons.reason_correct.sum()),'refund_primary_reason_accuracy':float(refund_reasons.reason_correct.mean()) if len(refund_reasons) else None,'reason_correct':int(g.reason_correct.sum()),'reason_accuracy_all_primary_tickets':float(g.reason_correct.mean()),'reason_abstentions':int(g.reason_abstained.sum()),'reason_coverage':len(reason_covered)/len(g),'reason_accuracy_when_not_abstaining':float(reason_covered.reason_correct.mean()) if len(reason_covered) else None,'outside_screen_groups':int((~g.screened).sum()),'end_to_end_screening_misses':int(g.screening_miss.sum()),'legacy_groups':int(g.legacy_in_group.sum()),'gw_other_groups':int(g.gw_other_in_group.sum()),'y_flag_groups':int(g.y_flag_in_group.sum())}
    result={'labeler':manifest['labeler'],'provisional':True,'human_reviewed_cases':0,'detector_version_frozen_sha256':digest,'test_set_tuning':False,'population':manifest['population'],'eligible_groups':manifest['eligible_groups'],'sampling_seed':manifest['seed'],'strata':stats,'interpretation':'Positive means source evidence of recorded refund plus completed replacement on a linked order/ticket, not verified avoidable cost or policy adjudication. Unresolved predictions are abstentions and count as non-alerts for end-to-end binary recall. Random set estimates only the stated group population; challenge errors are not population rates. Single AI author also built rules: shared bias, no independent human validation. Small sample, especially few random positives. Reason labels evaluate earliest ticket per group, not always refund-bearing. No tuning on test labels.','failure_examples':frame[(frame.confusion.isin(['FP','FN'])) | (~frame.reason_correct)].to_dict('records')}
    out.mkdir(parents=True,exist_ok=True);(out/'evaluation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');frame.to_csv(out/'evaluation_cases.csv',index=False)
    queue=frame[(frame.confusion.isin(['FP','FN'])) | frame.detection_abstained | frame.reason_abstained].copy()
    queue['review_priority']=queue.confusion.map({'FN':0,'FP':0,'TN':1,'TP':1})
    queue=queue.sort_values(['review_priority','sample_id']).head(12)
    queue['human_decision']='PENDING';queue.to_csv(out/'human_review_queue.csv',index=False)
    print(json.dumps({'strata':stats,'classification_failures':frame[frame.confusion.isin(['FP','FN'])].to_dict('records')},indent=2))
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',default='private/reference');p.add_argument('--out',default='outputs/real');a=p.parse_args();evaluate(a.reference,a.out)
