"""Final consistency and deliverable audit. Fails on mismatch; reports user-required items."""
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
from pypdf import PdfReader
p=Path('outputs/real');g=json.loads((p/'business_goal.json').read_text());quality=json.loads((p/'quality.json').read_text());ev=json.loads((p/'evaluation.json').read_text())
required=['app.py','README.md','requirements.txt','requirements-lock.txt','memo.md','memo.pdf','submission-form.md','docs/work-log.md','docs/walkthrough.md','docs/analysis.md','docs/publishing.md','prompts/source-review-v1.txt','private/reference/labels.json','private/reference/manifest.json','private/business_review.json','private/pack_profile.json','private/pytest-final.txt']
for name in required:assert Path(name).exists(),name
for name in ['monthly','monthly_reason','monthly_agent','monthly_reason_agent','quarterly_cx']:
 d=pd.read_csv(p/f'{name}.csv');assert int(d.refund_minor.sum())==quality['final_refund_minor'],name
bridge=pd.read_csv(p/'reconciliation.csv');assert int(bridge.iloc[-1].balance_minor)==quality['final_refund_minor'];assert int(bridge.change_minor.sum())==quality['final_refund_minor']
cases=pd.read_csv(p/'goal_cases.csv');assert len(cases)==g['baseline_order_count'];assert cases.case_key.is_unique
assert int(cases.quarter_refund_minor.sum())==g['candidate_refund_minor'];assert int(cases.goal_increment_minor.sum())==g['conservative_increment_minor'];assert g['conservative_increment_minor']//2==g['projected_quarterly_savings_minor']
assert len(PdfReader('memo.pdf').pages)==1
assert json.loads(Path('private/pdf-layout.json').read_text())['all_text_blocks_within_page']
pdf=PdfReader('memo.pdf').pages[0];pdftext=pdf.extract_text();font_sizes=[];positions=[]
def visitor(text,cm,tm,font,size):
 if text.strip():font_sizes.append(size);positions.append({'text':text.strip()[:50],'y_local':tm[5],'font_size':size})
pdf.extract_text(visitor_text=visitor)
assert min(font_sizes)>=10,'Unreadably small PDF body font'
for path in ['memo.md','submission-form.md','docs/analysis.md']:
 s=Path(path).read_text();assert f"{g['projected_quarterly_savings_minor']/100:,.0f}" in s,path
 assert f"{quality['final_refund_minor']/100:,.0f}" in s,path
 assert f"{g['baseline_rate']:.2%}" in s,path
assert f"{g['projected_quarterly_savings_minor']/100:,.0f}" in pdftext
for name,data in quality['input_manifest'].items():assert hashlib.sha256(Path(data['file']).read_bytes()).hexdigest()==data['sha256'],f'Original changed: {name}'
assert json.loads(Path('private/app-real-check.json').read_text())['real_data_rendered']
assert json.loads(Path('private/health-check.json').read_text())['observed_body']=='ok'
assert ev['test_set_tuning'] is False and ev['human_reviewed_cases']==0
assert sum(s['case_groups'] for s in ev['strata'].values())==60
assert json.loads((p/'independent_crosscheck.json').read_text())['monthly_exact_match']
tests=Path('private/pytest-final.txt').read_text();assert re.search(r'\d+ passed',tests) and not re.search(r'\d+ failed',tests)
markers=sorted(set(re.findall(r'USER_REQUIRED_[A-Z_]+',Path('submission-form.md').read_text())))
start=datetime.fromisoformat('2026-09-30T11:42:33+00:00');now=datetime.now(timezone.utc)
result={'verified_at_utc':now.isoformat(),'all_headline_numbers_agree':True,'all_required_local_deliverables_exist':True,'original_csv_hashes_unchanged':True,'financial_crosscheck_exact':True,'join_cardinality':[quality['join_rows_before'],quality['join_rows_after']],'pytest_summary':next(line for line in tests.splitlines() if re.search(r'\d+ passed',line)),'held_out_groups':60,'human_validated_reference_cases':0,'memo_pdf_pages':1,'memo_min_font_size_pt':min(font_sizes),'memo_word_count':len(pdftext.split()),'pdf_check':'A4, one page, text and 10.2pt minimum font verified; PyMuPDF 1.26.5 rendered preview visually inspected, all text blocks within page.','platform':'Linux Python 3.12 on Windows-mounted workspace; native Windows not executed','app_checks':'Streamlit AppTest load/filter/synthetic review-save passed; real-data AppTest result recorded separately; localhost health checked separately','not_tested':['native Windows execution','real browser visual QA','model API integration (not implemented)','multi-user concurrent review writes','bank/dispatch ledger reconciliation'],'human_actions_remaining':markers,'session_wall_minutes_so_far':(now-start).total_seconds()/60,'prior_effort':'Unknown; user must supply honest total including recording/review','submission_complete':False,'reason':'Recording, external links and actual total hours still required; human review pending. Nothing published.'}
Path('private/validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
