# Vireo refund evidence tool

A local Python/Streamlit prototype for reconciling ticket refunds and reviewing possible refund-plus-replacement cases. It preserves original reason codes, shows resolving-agent roster context, exports audit trails and saves a review decision locally. It does not execute payments, block refunds or reconcile to a bank ledger.

The public demo is entirely synthetic. Client inputs, derived outputs, source reviews and submission materials must stay outside public Git history. Nothing has been published by this project.

## Windows setup

Prerequisites: Windows 10/11, Python **3.12 (64-bit)** installed with the Python launcher, and an internet connection for the initial dependency installation. Commands below are PowerShell commands, run from the project folder. No environment activation is needed. The `.venv-win` name avoids a pre-existing Linux `.venv` in the assessment workspace.

```powershell
cd "C:\Users\techn\Downloads\TASK A"
py -3.12 -m venv .venv-win
.\.venv-win\Scripts\python.exe -m pip install -r requirements.txt -c requirements-lock.txt
.\.venv-win\Scripts\python.exe -m vireo.pipeline --input demo --out outputs/demo
.\.venv-win\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
```

Open `http://localhost:8501`. Defaults use `demo` and `outputs/demo`; the yellow banner identifies synthetic data. Use Ctrl+C in the terminal to stop the server. The tool needs no API key or internet after installation. Only five direct dependencies are used; the lock file pins the transitive versions actually tested.

## Supplied client pack

Keep the five CSV files, README.txt, email-thread.txt and support-policy.pdf in the workspace root, or in a private `input` folder. Download prefixes are accepted: the loader requires exactly one matching `*tickets.csv`, `*agents.csv`, `*orders.csv`, `*customers.csv` and `*products.csv` in the chosen input folder. It never modifies originals. Avoid combining demo and real CSVs in the same folder. CSVs are read as strings to retain raw values. PDF and email were read for policy/assumptions; runtime calculations load the five CSVs, not a new interpretation of policy.

For the supplied assessment pack and the included **private** frozen AI source review:

```powershell
.\.venv-win\Scripts\python.exe scripts/profile_pack.py
.\.venv-win\Scripts\python.exe -m vireo.pipeline --input . --out outputs/real --business-review private/business_review.json
.\.venv-win\Scripts\python.exe scripts/crosscheck.py --input . --out outputs/real
.\.venv-win\Scripts\python.exe -m vireo.evaluate --reference private/reference --out outputs/real
```

To open the real results directly:

```powershell
.\.venv-win\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --browser.gatherUsageStats false -- --input . --out outputs/real --business-review private/business_review.json
```

Alternatively, in the app set Input folder to `.`, Output folder to `outputs/real`, and Optional frozen AI business review JSON to `private/business_review.json`. Existing results open immediately; Load/rebuild recomputes them. A changed source invalidates its saved AI review by hash. A public clone has no client pack or frozen client reviews; omit `--business-review` to run rules-only on a new pack. That produces a different, explicitly provisional goal baseline. Do not reuse the submitted business claims for a new pack.

The profile helper is specific to this supplied root layout. For a private `input` layout the main pipeline supports `--input input`; adjust the helper's root when profiling a different pack. Review paths and outputs are local relative paths. Treat the app as a trusted single-user desktop utility, not a server exposed to others.

## Tests and evaluation

```powershell
.\.venv-win\Scripts\python.exe -m pytest -q
.\.venv-win\Scripts\python.exe -m vireo.evaluate --reference demo/reference --out outputs/demo
```

The demo evaluation is a plumbing check on six authored examples, **not** accuracy evidence. The real evaluation command above uses 60 frozen source-reviewed case groups. Selection seed, source packet, exact quotes, reviewer provenance and labels are under `private/reference/`; predictions and metrics are under `outputs/real/`. Thirty random groups and thirty challenge groups are reported separately. An AI assistant reviewed the text; no human reference validation is claimed. Rules were frozen before labels. Tests validate deterministic invariants and important edge cases; passing them does not establish classification accuracy.

The app test operates only on a temporary synthetic fixture. It verifies rendering, filtering and a local defer decision. No automated test impersonates a human review of client data. `pytest.ini` restricts collection to `tests/`.

## Financial and reporting choices

- Normalize helpdesk rupees to integer paise; legacy values already represent paise. The supplied-pack hypothesis was checked against cross-source duplicates, explicit Rs notes and order values. Do not blindly reuse this mapping for a new source. Unknown source names, negative money and fractional minor units fail explicitly.
- Deduplicate **ticket_id** only. Prefer helpdesk, then earliest exported row in that source. Do not merge fields. Preserve every retain/discard decision and conflicting fields; separate tickets sharing an order stay separate.
- Month means **ticket creation month as displayed in IST**, a proxy, not refund payment month. Missing/invalid creation dates use `Unknown date`. Missing reasons/agent IDs stay in unknown buckets. Raw legacy resolution timestamps are not shifted; both source labels can describe migrated records.
- Resolve agent assignments by agent_id and inclusive assignment validity dates at raw resolution date, or creation date when resolution is absent. Overlaps/unmatched assignments stay unknown. First-routed `assigned_team` is not the resolving agent's `roster_team`. Agent tables are not a productivity ranking; Returns Desk owns refunds by design.
- Use customer_id + product_sku fallback only when there is exactly one order. Retain ambiguous/direct-mismatched links unresolved. Flag orders after ticket creation and exclude them from the savings goal. Customer/product keys are checked; joins cannot multiply ticket rows.
- `refund_reason_raw` and replacement flags remain unchanged. Inferred semantic reasons are separate and can abstain. Full notes/messages may contain personal details; keep the source-text expander closed during a public recording.
- Exceptions distinguish source evidence, cross-ticket candidates, unresolved candidates and unsupported mentions. One order is counted at most once per baseline quarter. Review confirmation is an escalation judgment, never a payment action. Saved decisions do not silently alter the observed baseline.
- Candidate refunds, estimated replacement cost and conservative incremental cost are separate. One planning replacement unit per order; order qty is not assumed to equal replacement qty. No refurbishment recovery. Preserve one legitimate remedy. SLA store credits are excluded.
- Policy v3.2 applies from 1 April 2025. Earlier candidates are descriptive/retrospective only and excluded from the goal. Entitlement, dispatch and cash settlement still require operational review.
- CSAT excludes blanks. The goal guardrail uses scored resolved/closed tickets and reports completed-ticket response rate. Quarterly comparison exports retain all recorded scores and all-ticket response rates, including the separately disclosed status anomalies.

## AI mode and operating cost

Runtime mode is **rules-only**. It reads both fields, labels replacement states and validates exact excerpts. It has no live model provider, no model key, no paid inference calls, and no tested or untested API integration hidden behind the fallback. `prompts/source-review-v1.txt` records the instruction used for actual AI-assisted source review in the coding session. Frozen AI labels supplement human review; they are not a live model mode and cannot generalize to newly arrived tickets automatically.

No client data is sent by this tool to an external model. The coding assistant used Codex GPT-6 for coding, source extraction and provisional review; its subscription/development usage cost and tokens are unavailable, not zero. Do not claim model-mode accuracy for the rules. Future paid API usage would need user authorization, redaction, response validation and separately measured evaluation/cost; it was deliberately not implemented.

Rules are cached by input text, raw flag, rules version and source-review prompt version. `--no-cache` bypasses that cache. Cache files contain source excerpts and stay private. `run_history.jsonl` records actual elapsed wall time, hits/misses, screening fraction and zero runtime model calls/tokens/retries. Broad screening identifies possible replacement language/flags; cheap rules still read all tickets. Cost scenario is **650 × 52 ÷ 12 = 2,816.67 tickets/month**. API spend is zero; hardware, power, hosting and reviewer time are not metered or priced as free. See the generated private cost report for actual measured runs and incremental extraction timing.

## Outputs and handoff

`outputs/real/` contains:

- `monthly.csv`, `monthly_reason.csv`, `monthly_agent.csv`, `monthly_reason_agent.csv`: exact reconciled summary tables; `refund_minor` is authoritative integer paise, `refund_inr` is display rupees.
- `reconciliation.csv`, `dedup_audit.csv`, `clean_tickets.csv`, `quality.json`, `independent_crosscheck.json`: financial bridge, traceability and integrity checks.
- `exceptions.csv`: archive-wide order/ticket evidence; its total is not a quarterly savings measure. `goal_cases.csv` uses **quarter_refund_minor** and **goal_increment_minor** to reconcile the quarterly goal exactly.
- `business_goal.json`, `quarterly_cx.csv`, `evaluation.json`, `evaluation_cases.csv`, `human_review_queue.csv`, `usage_last.json`, `run_history.jsonl`, `cost_report.json`.
- `reviews/decisions.jsonl`: append-only local review trail with evidence hashes. Single-user use; not a multi-user transactional database. CSV exports with free text should be opened as text/imported with formula interpretation disabled in spreadsheet software.

Private materials: `memo.md`, `memo.pdf`, `submission-form.md`, `docs/analysis.md`, `docs/work-log.md`, `docs/walkthrough.md`, `private/validation.json`. The memo/report generator reads actual output files. Do not run it over demo data and present that as the client submission.

```powershell
.\.venv-win\Scripts\python.exe scripts/build_submission.py
.\.venv-win\Scripts\python.exe scripts/verify_submission.py
.\.venv-win\Scripts\python.exe scripts/prepare_public.py
```

`public-release/` is an allowlisted, synthetic-only source copy for inspection. Nothing is uploaded or submitted. Public-sharing instructions are in `docs/publishing.md`. `USER_REQUIRED` fields in the form must be resolved before submission: true total hours, recording link, Google Drive link and GitHub URL. A script is not a recording.

## What was actually verified

The submission was built in the shared Windows-mounted workspace using a fresh **Linux-side Python 3.12** environment. Pinned installs, real and demo pipelines, exact independent totals, pytest, Streamlit AppTest, evaluation and a localhost HTTP health check were executed. PDF page count, content and layout checks are recorded in validation evidence; a PyMuPDF 1.26.5 preview was visually inspected (temporary verification-only dependency). Native Windows execution and an end-user browser visual check are not claimed. The commands above are Windows-compatible equivalents; use the final validation report for exact test counts/results. Model-mode integration, production deployment, bank/dispatch ledger reconciliation and human label validation were not performed.
