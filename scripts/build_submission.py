"""Generate private submission materials from verified outputs, never synthetic data."""
import json
from datetime import datetime,timezone
from pathlib import Path
from xml.sax.saxutils import escape
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
from pypdf import PdfReader

root=Path('.');p=root/'outputs/real'
def read(name):return json.loads((p/name).read_text())
def rupees(minor):return f'{int(minor)/100:,.0f}'
g=read('business_goal.json');q=read('quality.json');ev=read('evaluation.json');cross=read('independent_crosscheck.json');profile=json.loads(Path('private/pack_profile.json').read_text())
assert q['unique_tickets']>100 and g['ai_source_review_count']==45, 'Real verified inputs and frozen business review required'
challenge=ev['strata']['challenge'];random=ev['strata']['random']
quarter=pd.read_csv(p/'quarterly_cx.csv').set_index('quarter');before=quarter.loc['2025Q3'];after=quarter.loc['2025Q4'];cx_delta=after.csat_mean-before.csat_mean
runs=[json.loads(s) for s in (p/'run_history.jsonl').read_text().splitlines()]
cold=json.loads(Path('outputs/final-cold/usage_last.json').read_text());cached=runs[-1];incremental=read('incremental_benchmark.json')
monthly=650*52/12
cost={'mode':'No runtime model/provider. Rules-only extraction; frozen Codex GPT-6 source reviews supplement goal eligibility.','final_cold_full_pack':cold,'cached_full_pack':cached,'incremental_extraction':incremental,'monthly_tickets':monthly,'screening_fraction':cold['screening_fraction'],'monthly_screened_equivalent':monthly*cold['screening_fraction'],'cache_observation':'Final cached elapsed exceeded final cold elapsed despite all hits; local file I/O and run conditions dominate. No cache speedup claimed.','monthly_api_spend_inr':0,'arithmetic':'2,816.6667 tickets/month × 0 runtime model calls/ticket × no applicable provider price = Rs 0 inference API spend. No paid inference calls. This is not a total operating-cost claim.','estimated_cold_processing_seconds_at_monthly_volume':cold['elapsed_seconds']/cold['tickets']*monthly,'price_source':'Not applicable: no model price or currency conversion used. Measured local mode as of '+datetime.now(timezone.utc).date().isoformat(),'unavailable_costs':['Codex subscription/development usage','human review time/rate','local hardware/electricity','future hosting'],'hosting':'Existing local machine; no hosting purchase or deployment.','monthly_review_workload_scenario':'At the measured screening fraction, about '+str(round(monthly*cold['screening_fraction']))+' tickets/month could enter broad screening, before order grouping. Not all require review. No measured review time or assumed staffing savings.'}
(p/'cost_report.json').write_text(json.dumps(cost,indent=2))
statement=f"Reduce evidence-supported refund-plus-replacement orders from {g['baseline_order_count']} of {g['eligible_refund_orders']} linked refund orders ({g['baseline_rate']:.2%}) to a proposed {g['proposed_target_rate']:.2%} within 90 days, worth approximately Rs {rupees(g['projected_quarterly_savings_minor'])} per quarter under the assumptions below."
paragraphs=[
('To Arjun Mehta · Finance Controller','Task 1 V5 — Vireo Audio, Set C | Decision memo | 30 September 2026'),
('Refunds now reconcile',f"Across January 2025–June 2026, the exported sum read as rupees is Rs {float(cross['naive_inr']):,.0f}. Correcting legacy paise gives Rs {float(cross['unit_corrected_inr']):,.0f}; removing 638 migration copies leaves Rs {rupees(q['final_refund_minor'])} across 11,600 tickets. Every monthly, original-reason and resolving-agent breakdown agrees. April–June 2026 refunds are Rs {rupees(g['refund_minor'])}. Creation month is a reporting proxy; no payment ledger is supplied."),
('Target the second remedy',f"{statement} The {g['baseline_order_count']} cases have Rs {rupees(g['candidate_refund_minor'])} of recorded quarterly refunds and Rs {rupees(g['candidate_replacement_planning_minor'])} of estimated replacement cost. These are provisional source-supported candidates, not confirmed losses. Rules identified candidates; AI reviewed both text fields, excluding one contradictory record and one prior-quarter event."),
('What the saving assumes',f"Retain the refund as the legitimate remedy and avoid one replacement: product unit cost plus Rs 340 shipping, with no refurbishment recovery. The estimate is capped at the smaller remedy cost per order, totalling Rs {rupees(g['conservative_increment_minor'])}. A proposed 50% reduction yields Rs {rupees(g['projected_quarterly_savings_minor'])}; realized savings could be zero if entitlement, completion or interception assumptions fail. This is a pilot target, not achieved savings."),
('Action and customer safeguard',f"Neha Kulkarni should own a 90-day Returns Desk pilot: check the shared order remedy record before a second remedy, then escalate conflicts to the Team Lead and Finance under policy §5. Preserve one legitimate remedy and a prompt response. Maintain CSAT of {g['csat_mean']:.2f}/5 ({g['csat_responses']} responses from {g['csat_eligible_completed']} completed tickets; {g['csat_response_rate_completed']:.1%} response rate). Avoid blanket refund cuts or blaming Returns Desk for doing its job."),
('Limits before acting',f"Human confirmation and dispatch/entitlement checks remain necessary. The 30-case challenge sample gave {challenge['TP']} true alerts, {challenge['FP']} false alert and {challenge['FN']} misses; the random sample missed its only positive. AI labels are provisional. Legacy resolution timezone is unresolved. The Q3–Q4 2025 CSAT change is only {cx_delta:+.2f} in this creation-cohort export, not the email’s +0.4; that comparison cannot establish causation. SLA credits are separate."),
]
md='# '+paragraphs[0][0]+'\n\n'+paragraphs[0][1]+'\n\n'+'\n\n'.join('**'+title+'.** '+text for title,text in paragraphs[1:])+'\n\nEvidence: outputs/real/{reconciliation,monthly,monthly_reason,monthly_agent,goal_cases}.csv; evaluation.json; private/business_review.json.\n'
Path('memo.md').write_text(md,encoding='utf-8')
styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='MemoBody',fontName='Helvetica',fontSize=10.2,leading=13.1,spaceAfter=8));styles.add(ParagraphStyle(name='MemoTitle',fontName='Helvetica-Bold',fontSize=17,leading=21,textColor=colors.HexColor('#15394c'),spaceAfter=7))
flow=[Paragraph(escape(paragraphs[0][0]),styles['MemoTitle']),Paragraph(escape(paragraphs[0][1]),styles['MemoBody']),Spacer(1,6)]
for title,text in paragraphs[1:]:flow.append(Paragraph('<b>'+escape(title)+'.</b> '+escape(text),styles['MemoBody']))
flow.append(Paragraph('Evidence: reconciliation, monthly summaries and goal_cases.csv; evaluation.json; private business source-review audit.',styles['MemoBody']))
SimpleDocTemplate('memo.pdf',pagesize=A4,rightMargin=42,leftMargin=42,topMargin=36,bottomMargin=36,title='Vireo refund decision memo',author='Assessment submission').build(flow)
r=PdfReader('memo.pdf');assert len(r.pages)==1,f'Memo must be one page, got {len(r.pages)}'
assert '43' in r.pages[0].extract_text() and rupees(g['projected_quarterly_savings_minor']) in r.pages[0].extract_text()

analysis=f'''# Financial method, scope and limits

Generated from actual outputs. No bank or dispatch ledger exists. Business findings use supplied records, never demo fixtures.

## Reconciliation and units

Naive export interpreted as rupees: Rs {float(cross['naive_inr']):,.0f}. Unit correction: Rs {float(cross['unit_corrected_inr'])-float(cross['naive_inr']):,.0f}. Unit-corrected gross: Rs {float(cross['unit_corrected_inr']):,.0f}. Re-import removal: Rs {float(cross['duplicate_removed_inr']):,.0f}. Final: Rs {rupees(q['final_refund_minor'])}. All 18 monthly rows and every reason/agent aggregate match exactly. Independent csv/Decimal code does not import the pipeline.

All 125 refund-bearing migration pairs show 100× legacy values; 371 explicit Rs-note amounts match the paise hypothesis and none match rupees. Of 509 legacy direct, consistent order links, all raw values exceed order values, none normalized do, 377 normalized match the order value. Approximate email quarterly total is only a sanity check: archive average Rs {q['final_refund_minor']/100/6:,.0f}, not a forced target. Original raw amounts remain in clean_tickets; originals have SHA-256 hashes in quality.json.

Deduplication is ticket-ID-only: helpdesk preferred, then lowest original row number within source. Conflicts are logged without field merging. In this pack conflicts occur only in source_system (638 pairs) and raw refund amount (125). No legitimate separate ticket is removed because an order/customer is shared. Negative/refund reversals are not supported by this pack-specific parser; unexpected negative amounts fail rather than being silently misclassified.

## Dates, joins and missing information

Creation month as exported IST is the explicit reporting proxy. No payment date exists. There are {q['missing_resolved_dates']} missing resolution timestamps, zero missing creation timestamps. All raw resolution timestamps are kept. Policy §9 says migrated event logs stored UTC, while standard exports display IST; all re-imported timestamp fields match their legacy counterparts. No negative resolution-before-creation/response intervals were observed. Adding 330 minutes hypothetically changes 36 migrated resolution months, including 5 re-imports; this is sensitivity, not evidence that the shift is correct. Creation-month results are unaffected. Raw resolution dates still select agent assignments, so a timezone boundary could matter if assignments change; current roster is 44 unique IDs with one assignment each.

Order links: {json.dumps(q['order_link_status'])}. The 707 ambiguous customer/product fallbacks stay unresolved; 308 linked orders occur after the ticket date and are excluded from the goal. No direct customer/SKU mismatch found. Those dates are another reason not to treat the order data as a verified ledger. Roster matches never multiply rows: {q['join_rows_before']} before and {q['join_rows_after']} after joins. 1,332 first-routed teams differ from resolving-agent roster teams. Returns Desk owns refunds by design (§6); rates are refund-bearing tickets / all tickets attributed to that agent, including unresolved tickets. This is not a Tier 1/Tier 2 productivity comparison.

## Business case

{statement}

Baseline is {g['start']}–{g['end']}, the latest fully covered calendar quarter. Denominator: {g['eligible_refund_orders']} distinct, unambiguously linked, date-consistent refund orders with any recorded refund in quarter. All quarter tickets: {g['tickets']}; refund-bearing tickets: {g['refund_tickets']}; recorded refund cash: Rs {rupees(g['refund_minor'])}. Orders without usable links are excluded from this rate, not silently assumed safe.

Numerator: {g['baseline_order_count']} order groups with positive refund and source evidence of a completed replacement on the same quarter ticket, plus a matching frozen AI source review. Archive-level cross-ticket candidates remain reviewable, but are excluded from this conservative goal because chronology/entitlement is unresolved. One order, one planning replacement unit; even qty=2 orders do not imply two replacements. Quantity is uncertain; the model neither multiplies replacement cost by order qty nor assumes refurbishment recovery.

The pipeline originally surfaced 45 goal candidates by latest refund order month. Review excluded one contradictory dispatched/out-of-stock note and one December 2025 event moved into Q2 by a subsequent refund. The aggregation now requires completion evidence on a refund-bearing quarter ticket. private/business_review.json contains all 45 actual AI source reviews; source hashes prevent silent reuse on changed input. This is selection-based review by the same coding assistant, not an independent validation sample. Reviewed findings remain provisional: no human has confirmed these client cases.

Rs {rupees(g['candidate_refund_minor'])} is recorded quarterly refund cash on these orders. Rs {rupees(g['candidate_replacement_planning_minor'])} is estimated replacement planning cost. Rs {rupees(g['conservative_increment_minor'])} is the candidate avoidable increment, capped by min(refund, one unit cost + 340) per order. Here every cap selects replacement cost, so the scenario retains the refund and avoids the replacement. Do not add refund and replacement as savings. Fifty percent reduction is a proposed pilot hypothesis, not a proven feasible threshold, allowing half for legitimate remedies, uncertainty and interception failures, not a measured intervention success rate. Projected Rs {rupees(g['projected_quarterly_savings_minor'])}/quarter is before unmeasured review/implementation costs; sensitivity is Rs 0 to this target. No outcome is yet achieved. Escalation owner: Neha Kulkarni, Returns Desk TL and Finance; no automatic denial.

## Customer experience and policy

CSAT safeguard uses completed tickets only: {g['csat_mean']:.4f}/5, {g['csat_responses']}/{g['csat_eligible_completed']} responses ({g['csat_response_rate_completed']:.2%}). {g['csat_scores_on_incomplete_tickets']} additional scores occur on open/pending Q2 tickets; excluded from this guardrail, preserved in all-ticket summary tables. Those tables have 1,039 scores and mean 3.4610 for Q2. Monitor response rate and customer remedy delays, not only mean scores.

The email's unspecified Q4 is interpreted as calendar Q4 2025. Q3/Q4 all-score means: {before.csat_mean:.4f} ({int(before.csat_response_count)} responses) vs {after.csat_mean:.4f} ({int(after.csat_response_count)} responses), delta {cx_delta:+.4f}. All-ticket response rates {before.csat_response_rate_all_tickets:.2%} vs {after.csat_response_rate_all_tickets:.2%}. Recorded refunds rise from Rs {rupees(before.refund_minor)} to Rs {rupees(after.refund_minor)}; tickets rise {int(before.ticket_count):,} to {int(after.ticket_count):,}. Refund-ticket rate moves {before.refund_rate_all_attributed_tickets:.2%} to {after.refund_rate_all_attributed_tickets:.2%}. The +0.4 CSAT claim is not reproduced by this comparison; timing, cohorts and survey selection differ. Neither a change in policy nor causation is proven or disproven. Checking second remedies targets avoidable duplication without indiscriminately suppressing the intended customer-experience refunds.

Policy v3.2 effective 1 April 2025 governs the latest baseline. Earlier archive candidates are a retrospective assumption and excluded from goal eligibility. Notes claiming approval or SOP exceptions cannot change §5. Raw GW-OTHER/intake tags are not truth. No SLA store credits, contact costs or staffing savings enter the cash/refund business case.

## Text quality and AI

Frozen rules read both source fields and retain exact excerpts, raw flags and code. Codex GPT-6 performed narrow source extraction for the held-out labels and goal review. No runtime provider is integrated; no paid inference calls, retries or runtime tokens. The submitted financial foundation is deterministic; business eligibility includes a frozen AI review. Live classification results remain rules-only. No model-mode accuracy is claimed.

Held-out sample: 60 groups / 100 source tickets, seed 9302026, excluding 60 development groups, keeping all linked tickets together after migration deduplication. Random population: 7,986 order/unresolved-ticket groups (not refund-only tickets). Thirty random and thirty enriched challenge groups. Legacy, flags, no flags, GW-OTHER and terse cases are included. Labels were written after reading source material without copying predictions. Labeler is the same AI coding assistant; no human validation and shared-model bias remain.

Random: TP {random['TP']}, FP {random['FP']}, FN {random['FN']}, TN {random['TN']}; precision undefined (no positive alerts), recall 0/1. Challenge: TP {challenge['TP']}, FP {challenge['FP']}, FN {challenge['FN']}, TN {challenge['TN']}; precision {challenge['precision']:.2%}, recall {challenge['recall']:.2%}. Binary sample errors 1/30 random and 3/30 challenge. Abstentions count as no alert for end-to-end recall. No population error rate is claimed from the challenge set. Random recall's 95% Wilson interval is 0–79.3%; challenge precision 48.7–97.4%, recall 40.9–92.9%.

Reason accuracy across earliest-ticket labels: random {random['reason_correct']}/30 ({random['reason_accuracy_all_primary_tickets']:.1%}), challenge {challenge['reason_correct']}/30 ({challenge['reason_accuracy_all_primary_tickets']:.1%}). Reason coverage {random['reason_coverage']:.1%}/{challenge['reason_coverage']:.1%}; conditional accuracy {random['reason_accuracy_when_not_abstaining']:.1%}/{challenge['reason_accuracy_when_not_abstaining']:.1%}. For refund-bearing primary tickets specifically: random {random['refund_primary_reason_correct']}/{random['refund_primary_reason_cases']}, challenge {challenge['refund_primary_reason_correct']}/{challenge['refund_primary_reason_cases']}. Do not hide abstentions by quoting only conditional accuracy. Detection abstentions {random['detection_abstentions']}/30 and {challenge['detection_abstentions']}/30. Twenty random and eight challenge groups outside the broad screen were reviewed: no positive screening miss observed, too few to establish complete coverage.

Concrete errors: missed hyphenated 're-shipped'; mistaken purchased 'replacement case' for a remedy; missed 'New piece dispatched'; completed shipment correctly extracted but excluded by future-order date inconsistency. The classifier also confuses warranty/return logistics with the underlying product fault. Detector remained frozen after evaluation. Business-quarter aggregation was corrected after separate candidate review; this is disclosed and does not change the saved text rules or their held-out metrics.

## Cost and verification

Final cold pack: {cold['tickets']} tickets, {cold['elapsed_seconds']:.2f}s, {cold['cache_hits']} hits/{cold['cache_misses']} misses. Latest cached run: {cached['elapsed_seconds']:.2f}s, {cached['cache_hits']} hits/{cached['cache_misses']} misses. These include local file I/O and vary by machine; no SLA promise. Requested monthly scenario {monthly:.2f} tickets, screening {cold['screening_fraction']:.2%}, approximately {monthly*cold['screening_fraction']:.0f} broadly screened tickets/month. Cold elapsed scaled linearly: {cost['estimated_cold_processing_seconds_at_monthly_volume']:.2f}s/month; not a measured monthly deployment. API inference Rs 0; development AI, review labor, hardware/electricity and any future hosting unmeasured. Incremental benchmark is extraction of 100 existing rows as new cache inputs; report updates still run the full pipeline.

Commands, unit/UI tests, exact independent cross-check, evaluation, localhost health and PDF validation are recorded in private/validation.json. Native Windows execution, real browser visual QA, real payment prevention, production security and human review are not claimed. Review records are single-user append-only JSONL; no concurrent transaction guarantees.
'''
Path('docs/analysis.md').write_text(analysis,encoding='utf-8')
form=f'''# Task 1 V5 — Vireo Audio: Support Tickets, Set C

**Submission status: INCOMPLETE until all USER_REQUIRED fields below are supplied and publication/sharing is explicitly authorized.** No original submission-form.md was supplied. These questions preserve the requested form headings.

## 1. What did you build, and what business outcome does it move? State the number and the money.

A working local Streamlit tool: monthly refunds by original reason and resolving agent, exact reconciliation, evidence review with saved decisions, and a quantified pilot. Final 18-month refunds Rs {rupees(q['final_refund_minor'])}; Q2 2026 Rs {rupees(g['refund_minor'])}. {statement} Provisional AI source review supports the baseline, not human adjudication. Preserve the refund and avoid one replacement; Rs {rupees(g['conservative_increment_minor'])} estimated incremental exposure, 50% proposed reduction. See memo.pdf and outputs/real/goal_cases.csv.

## 2. What does one run cost, and what would a month cost at roughly 650 tickets a week? Show the arithmetic; state whether there were paid calls.

No paid runtime inference calls: provider/model none, calls/tokens/retries 0, API spend Rs 0. One final cold run processed {cold['tickets']:,} tickets in {cold['elapsed_seconds']:.2f}s; cached run {cached['elapsed_seconds']:.2f}s with {cached['cache_hits']:,} hits. Monthly: 650 × 52 ÷ 12 = {monthly:,.2f} tickets. {monthly:,.2f} × 0 API calls/ticket = 0 paid calls. Broad screening fraction {cold['screening_fraction']:.2%}, approximately {monthly*cold['screening_fraction']:.0f}/month; cheap rules still read every ticket. Linear local processing estimate {cost['estimated_cold_processing_seconds_at_monthly_volume']:.2f}s/month from cold timing; not hosted performance. Incremental extraction and rerun measurements are in cost_report.json. Codex development subscription/usage, human review and hardware/power are unmeasured, not free. No hosting purchased; no provider pricing assumption is used.

## 3. How do you know it works? Sample size, checking method, error rate and failure cases.

Deterministic tests check integer money, dedup conflicts, join cardinality/ambiguity, assignment dates, unknown buckets, CSAT, sum reconciliation, negation/offers/contradictions/terse notes, quote validation and local UI decisions. See private/pytest-final.txt for actual passing test count. Independent CSV + Decimal calculation agrees with every monthly total and the bridge. Real and synthetic commands executed in a fresh Linux Python 3.12 environment; localhost app health returned ok. Windows instructions are provided but native Windows was not executed.

Text evaluation: 60 held-out groups, 100 source tickets, 30 random + 30 challenge; Codex GPT-6 source-reviewed labels, zero human-validated cases. Random TP0 FP0 FN1 TN29: one error/30, precision undefined, recall 0/1. Challenge TP6 FP1 FN2 TN21: 3 errors/30, precision 85.7%, recall 75%. Do not generalize the enriched error rate or tiny random-positive sample. Reason accuracy: {random['reason_correct']}/30 random, {challenge['reason_correct']}/30 challenge; coverage {random['reason_coverage']:.1%}/{challenge['reason_coverage']:.1%}. Refund-bearing primary-ticket reason correctness separately: {random['refund_primary_reason_correct']}/{random['refund_primary_reason_cases']} random and {challenge['refund_primary_reason_correct']}/{challenge['refund_primary_reason_cases']} challenge. Detection abstentions 5/30 and 7/30. Reviewed 28 groups outside broad screening; no positive screening miss in this small sample. Failures include 're-shipped', 'new piece dispatched', purchased replacement case, and future-order date exclusion. Frozen classifier, no test-set tuning; business period aggregation was corrected separately after candidate review. Human review queue prepared.

## 4. Did you change, narrow or push back on the client's ask? What, when and why?

Kept the monthly original-reason/agent summary and reconciling totals. After reading the pack, narrowed the actionable analysis to duplicated compensation, respecting the intentional generous-refund decision and Returns Desk's role. Did not turn agent amounts into a worst-agent ranking. Chose creation-month proxy because no refund-payment timestamp exists and legacy resolution timezone cannot safely be fixed. During validation excluded contradictory and prior-quarter candidate evidence from the business baseline. Declined to equate RMA raised or a customer request with a completed replacement. No paid runtime integration without authorization; shipped explicit rules-only behavior and frozen AI source reviews.

## 5. What is wrong with what you are handing us? Specific bugs, shortcuts and known inaccuracies.

Rules miss spelling variants and some terse actions and misread product names; reason-label coverage is weak. Labels and business reviews are AI-assisted by the coding assistant, not independent humans. No dispatch or bank ledger, so neither confirmed losses nor paid-out refunds are proven. 707 ambiguous fallback links and 308 orders after ticket dates limit order-level conclusions. Forty-nine Q2 scores appear on incomplete tickets and are excluded from the completed-ticket CSAT guardrail. Legacy resolution timezone remains uncertain. Replacement quantity assumed one planning unit; entitlement and multi-unit fulfillment unknown. Source-review overlay is frozen, not live AI; omit it and the goal differs. Saved reviews do not automatically update business savings. Single-user JSONL is not transactional for simultaneous reviewers. No browser visual QA or native Windows execution claim.

## 6. What did you deliberately leave out, and why that rather than something else?

Staffing, SLA-credit optimization, broad category analytics, forecasting, separate frontend/backend, deployment, authentication, vector databases and fine-tuning. They would consume the five-hour assessment allowance without strengthening the requested cash reconciliation or the chosen preventable increment. Live provider integration was omitted to avoid unauthorized paid calls and untested accuracy claims. Human approval, ledger checks and recording are not fabricated to fill the gap.

## 7. Anything you built or found that nobody asked for?

Source fingerprints, a full retain/discard audit, independent monthly cross-check, order-date inconsistency reporting, evidence-bound review history and a synthetic-only public release builder. The email's claimed +0.4 Q4 CSAT improvement is not reproduced: the Q3–Q4 creation-cohort all-score change is {cx_delta:+.4f}; this is not a causal conclusion.

## 8. What did you use AI for? Tools/models, where they helped or wasted time, what was discarded, and the three-minute recording link.

Codex GPT-6 helped write and debug Python, read policy and ticket language, extract provisional reasons/actions with exact evidence, author the 60-group reference set and review 45 business candidates. Runtime tool has no LLM/provider and made no paid API calls. AI source judgments are provisional; use the human-review queue. Tools: pandas, Streamlit, pytest, pypdf, reportlab, Python stdlib. Real issues: unavailable pdftotext, sandbox dependency/network restrictions, slow per-row roster conversions and unrestricted test discovery; those approaches were revised. One actual source-review instruction is saved in prompts/source-review-v1.txt; no fictional prompt iterations or external model responses. Rules were not tuned after held-out evaluation. docs/work-log.md records actual changes.

Recording: **USER_REQUIRED_RECORDING_LINK**. docs/walkthrough.md is a script only; the actual <=3-minute recording must still be made by the user. Keep personal details/secrets off-screen; no slides.

## 9. Your Public Google Drive Link.

**USER_REQUIRED_PUBLIC_DRIVE_LINK**. No upload or permission change performed. Review the intended sharing audience and authorized contents first; never put raw client files in a public code repository.

## 10. Someone picks this up on Monday and you are unreachable: the three things they need to know.

1. Follow README Windows commands; public demo is synthetic. For the submission use real inputs plus private/business_review.json, then tests, crosscheck and evaluation. All file paths are relative; no API key needed.
2. Integer money/identity reconciliation is independently checked. Creation month is a proxy; refund, replacement planning cost and SLA credits are different things. Agent role context matters.
3. This is a review aid, not a payment block. Human-check the queue, order links, completion and entitlement before acting. Source-review hashes prevent stale reuse; changed inputs require renewed review. Private data/outputs/caches stay out of Git.

## 11. Honest hours spent: one number.

**USER_REQUIRED_TOTAL_HOURS**. User must enter one honest total including prior effort, review, recording and submission. Session wall time is logged separately; it cannot establish the user's total assessment effort. Do not infer effort from download timestamps.

## 12. Public GitHub repository URL.

**USER_REQUIRED_PUBLIC_GITHUB_URL**. Nothing published. Run scripts/prepare_public.py, inspect public-release, then explicitly authorize publishing. Exact steps are in docs/publishing.md.
'''
Path('submission-form.md').write_text(form,encoding='utf-8')
print('Generated memo.md, one-page memo.pdf, docs/analysis.md, submission-form.md and cost_report.json from real evidence.')
