"""Append-only, local single-user review trail, bound to evidence content."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path

def evidence_hash(case):
    return hashlib.sha256(json.dumps({k:case[k] for k in ['case_key','refund_minor','evidence']},sort_keys=True,default=str).encode()).hexdigest()

def save_review(path,case,decision,reviewer,note):
    if decision not in ['confirm','reject','defer']:raise ValueError('Invalid review decision')
    if not reviewer.strip() or not note.strip():raise ValueError('Reviewer and rationale are required')
    record={'case_key':case['case_key'],'decision':decision,'reviewer':reviewer.strip(),'note':note.strip(),'evidence_sha256':evidence_hash(case),'timestamp_utc':datetime.now(timezone.utc).isoformat()}
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
    return record

def read_reviews(path):
    path=Path(path)
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []
