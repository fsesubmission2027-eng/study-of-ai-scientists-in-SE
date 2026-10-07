import json, os
from datetime import datetime

rows = json.load(open('/tmp/evalstat/all_runs.json'))
IN, CACHE, OUT, FX = 4.5, 0.15, 13.5, 7.2  # CNY / M tokens, off-peak
for r in rows:
    p = os.path.join(r['run_dir'], 'artifacts/usage_ledger.jsonl')
    r.update(l_calls=None, l_tokens=None, l_cost_usd=None, l_hours=None)
    if not os.path.exists(p):
        continue
    ts, tok, cost, n = [], 0, 0.0, 0
    for line in open(p):
        try:
            e = json.loads(line)
        except Exception:
            continue
        n += 1
        pt = e.get('prompt_tokens') or 0; ct = e.get('completion_tokens') or 0
        cached = ((e.get('raw_usage') or {}).get('prompt_tokens_details') or {}).get('cached_tokens') or 0
        tok += pt + ct
        cost += ((pt - cached) * IN + cached * CACHE + ct * OUT) / 1e6 / FX
        try:
            ts.append(datetime.fromisoformat(e['ts']).timestamp())
        except Exception:
            pass
    ts.sort()
    dur = sum(min(b - a, 3600) for a, b in zip(ts, ts[1:]))
    r.update(l_calls=n, l_tokens=tok, l_cost_usd=cost, l_hours=dur / 3600)
json.dump(rows, open('/tmp/evalstat/all_runs.json', 'w'), indent=1, default=str)

import statistics as S
FWS = ['aris', 'deepscientist', 'evoscientist', 'ai_scientist', 'researchclaw', 'tiny_scientist', 'airesearcher']
for fw in FWS:
    rs = [r for r in rows if r['framework'] == fw and r['l_calls']]
    f = lambda k: (S.mean(r[k] for r in rs), max(r[k] for r in rs), S.median(r[k] for r in rs))
    print(f"{fw:15s} n={len(rs)} calls(mean/max/med)={f('l_calls')[0]:.0f}/{f('l_calls')[1]}/{f('l_calls')[2]:.0f} "
          f"tok={f('l_tokens')[0]/1e6:.1f}M/{f('l_tokens')[1]/1e6:.0f}M usd={f('l_cost_usd')[0]:.2f}/{f('l_cost_usd')[1]:.2f} "
          f"hours={f('l_hours')[0]:.2f}/{f('l_hours')[1]:.2f}/{f('l_hours')[2]:.2f} lowcall(<=5)={sum(1 for r in rs if r['l_calls']<=5)}")
rs = [r for r in rows if r['l_calls']]
print('ALL', len(rs), sum(r['l_cost_usd'] for r in rs), sum(r['l_hours'] for r in rs), sum(r['l_tokens'] for r in rs) / 1e9)
