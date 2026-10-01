"""Create an allowlisted source copy only. Never runs git, uploads or publishes."""
import hashlib,json,re,shutil
from pathlib import Path
root=Path('.');dest=root/'public-release';dest.mkdir(exist_ok=True)
files=[Path(p) for p in ['app.py','README.md','requirements.txt','requirements-lock.txt','pytest.ini','.gitignore']]
for directory,glob in [('vireo','*.py'),('tests','*.py'),('scripts','*.py'),('prompts','*.txt'),('demo','*.csv'),('demo','*.txt'),('demo/reference','*.json')]:files+=list(Path(directory).glob(glob))
private_helpers={'build_submission.py','verify_submission.py','save_reference_labels.py','benchmark_incremental.py'}
files=[f for f in files if not (f.parent==Path('scripts') and f.name in private_helpers)]
files.append(Path('docs/publishing.md'))
allowed={str(p).replace('\\','/') for p in files}
# Fail rather than silently publishing stale/unexpected files from an earlier staging run.
existing={str(p.relative_to(dest)).replace('\\','/') for p in dest.rglob('*') if p.is_file()}
unexpected=existing-allowed-{'PUBLIC_MANIFEST.json'}
if unexpected:raise ValueError(f'Unexpected files in public-release; inspect before preparing: {sorted(unexpected)}')
manifest=[]
for p in files:
 text=p.read_text(encoding='utf-8')
 if re.search(r'\b(?:TK-\d{6}|VR\d{6}|C10\d{4}|A30\d{2})\b',text):raise ValueError(f'Possible client identifier in {p}')
 target=dest/p;target.parent.mkdir(parents=True,exist_ok=True)
 if p==Path('README.md'):
  start=text.index('Private materials:');end=text.index('## What was actually verified',start)
  text=text[:start]+'Private assessment materials and their report-generation helpers are excluded from this public package. The client handoff contains the memo, form, source reviews and validation evidence. See docs/publishing.md for sharing steps. This source copy has not itself been published.\n\n'+text[end:]
  target.write_text(text,encoding='utf-8')
 else:shutil.copy2(p,target)
 manifest.append({'path':str(p).replace('\\','/'),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
(dest/'PUBLIC_MANIFEST.json').write_text(json.dumps({'purpose':'Synthetic-only local staging, not published','files':manifest},indent=2))
print(f'Prepared {len(files)} allowlisted files in public-release/. No git or network operation performed.')
