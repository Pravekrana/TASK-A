"""Time actual incremental text extraction only; not an incremental ledger updater."""
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from vireo.extract import cached_extract
p=Path('outputs/real');d=pd.read_csv(p/'clean_tickets.csv',dtype=str,keep_default_na=False).sample(n=100,random_state=930)
cache=Path('outputs/incremental/cache');cache.mkdir(parents=True,exist_ok=True)
runs=[]
for label in ['incremental_100_first_pass','incremental_100_repeat']:
 start=time.perf_counter();hits=0
 for row in d.to_dict('records'):
  _,hit=cached_extract(row,cache);hits+=hit
 elapsed=time.perf_counter()-start;runs.append({'run':label,'tickets':100,'cache_hits':hits,'cache_misses':100-hits,'elapsed_seconds':elapsed,'per_ticket_seconds':elapsed/100,'api_calls':0,'tokens':0,'spend_inr':0})
result={'scope':'100 existing archive tickets sampled to simulate newly encountered inputs in a separate cache. Measured extraction only, not a financial incremental-update feature; rebuilding reports still reads the full pack. First pass is cold only if cache_misses=100.','runs':runs}
(p/'incremental_benchmark.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
