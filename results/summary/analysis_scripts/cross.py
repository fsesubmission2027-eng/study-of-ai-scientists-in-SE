import json, statistics as S, collections, math
rows = json.load(open('/tmp/evalstat/all_runs.json'))
FWS = ['aris', 'deepscientist', 'evoscientist', 'ai_scientist', 'researchclaw', 'tiny_scientist', 'airesearcher']

# strict mean: all 6 axes, missing -> 0 (peer review normalized /10, idea (x-1)/4, EA as in fairness)
def axis_vals(r):
    v = {}
    v['completeness'] = r['comp_overall']
    v['idea'] = (r['idea_overall'] - 1) / 4 if r['idea_overall'] is not None else None
    v['peer'] = r['pr_overall'] / 10 if r['pr_overall'] is not None else None
    v['alignment'] = r['al_score']
    return v

for r in rows:
    v = axis_vals(r)
    r['strict4'] = S.mean([x or 0 for x in v.values()])

print('== strict4 (completeness, idea, peer, alignment; missing=0) vs fair_mean')
for fw in FWS:
    rs = [r for r in rows if r['framework'] == fw]
    print(f"{fw:15s} fair={S.mean(r['fair_mean'] for r in rs):.3f} strict4={S.mean(r['strict4'] for r in rs):.3f} fair_axes_mean={S.mean(r['fair_n_axes'] for r in rs):.2f}")

print('\n== per-task winner (by fair_mean) and by strict4')
tasks = sorted(set(r['task'] for r in rows))
win = collections.Counter(); win2 = collections.Counter(); tstat = []
for t in tasks:
    rs = [r for r in rows if r['task'] == t]
    b = max(rs, key=lambda r: r['fair_mean']); win[b['framework']] += 1
    b2 = max(rs, key=lambda r: r['strict4']); win2[b2['framework']] += 1
    tstat.append((t, S.mean(r['fair_mean'] for r in rs), max(r['fair_mean'] for r in rs), b['framework'],
                  sum(1 for r in rs if r['comp_complete']), sum(1 for r in rs if r['ea_success']),
                  S.mean([r['pr_overall'] for r in rs if r['pr_overall']] or [0])))
print('fair winners', win.most_common()); print('strict winners', win2.most_common())
tstat.sort(key=lambda x: x[1])
print('\n== tasks sorted by mean fair (task, mean, max, best_fw, #complete, #exp_success, mean APR)')
for x in tstat: print(f"{x[0][:45]:45s} {x[1]:.3f} {x[2]:.3f} {x[3]:14s} {x[4]} {x[5]} {x[6]:.2f}")

print('\n== venue')
for v in ['ASE', 'FSE', 'ICSE', 'ISSTA']:
    rs = [r for r in rows if r['venue'] == v]
    print(v, len(rs) // 7, f"fair={S.mean(r['fair_mean'] for r in rs):.3f} complete={sum(r['comp_complete'] for r in rs)}/{len(rs)} success={sum(bool(r['ea_success']) for r in rs)}/{len(rs)}",
          f"APR={S.mean([r['pr_overall'] for r in rs if r['pr_overall']]):.2f}")

def corr(a, b):
    p = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(p) < 8: return None, len(p)
    xs, ys = zip(*p)
    # spearman
    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i]); rk = [0] * len(v)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]: j += 1
            for k in range(i, j + 1): rk[s[k]] = (i + j) / 2
            i = j + 1
        return rk
    rx, ry = rank(xs), rank(ys)
    mx, my = S.mean(rx), S.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return (num / den if den else None), len(p)

print('\n== Spearman correlations')
pairs = [('pr_overall', 'idea_overall'), ('pr_overall', 'idea_novelty'), ('pr_overall', 'al_score'), ('pr_overall', 'ea_rp'),
         ('pr_overall', 'ea_idea_code'), ('pr_overall', 'ea_setup'), ('pr_overall', 'lit_recall'), ('pr_overall', 'l_cost_usd'),
         ('pr_overall', 'l_hours'), ('pr_overall', 'l_calls'), ('pr_overall', 'ea_ablation'),
         ('fair_mean', 'l_cost_usd'), ('fair_mean', 'l_hours'), ('fair_mean', 'l_calls'), ('fair_mean', 'l_tokens'),
         ('idea_overall', 'ea_idea_code'), ('idea_novelty', 'idea_feasibility'), ('al_score', 'ea_rp'), ('ea_idea_code', 'ea_setup')]
for a, b in pairs:
    c, n = corr([r.get(a) for r in rows], [r.get(b) for r in rows])
    print(f"{a:14s} ~ {b:16s} rho={c if c is None else round(c,3)} n={n}")

print('\n== Top 12 runs by fair_mean')
for r in sorted(rows, key=lambda r: -r['fair_mean'])[:12]:
    print(f"{r['fair_mean']:.3f} {r['framework']:13s} {r['task'][:40]:40s} APR={r['pr_overall']} idea={r['idea_overall']} align={r['al_score']} rp={r['ea_rp']}")
print('\n== Top 10 APR')
for r in sorted([r for r in rows if r['pr_overall']], key=lambda r: -r['pr_overall'])[:10]:
    print(f"{r['pr_overall']} {r['framework']:13s} {r['task'][:45]}")
print('\n== Bottom APR')
for r in sorted([r for r in rows if r['pr_overall']], key=lambda r: r['pr_overall'])[:8]:
    print(f"{r['pr_overall']} {r['framework']:13s} {r['task'][:45]} rp={r['ea_rp']} hiding={r['ea_hiding']}")

print('\n== cost-efficiency (ledger): USD per complete run, fair per USD')
for fw in FWS:
    rs = [r for r in rows if r['framework'] == fw and r['l_cost_usd'] is not None]
    tot = sum(r['l_cost_usd'] for r in rs); comp = sum(1 for r in rs if r['comp_complete'])
    print(f"{fw:15s} total=${tot:.1f} complete={comp} $/complete={tot/comp if comp else float('nan'):.2f} hours_total={sum(r['l_hours'] for r in rs):.1f}")

print('\n== alignment claim labels per fw')
for fw in FWS:
    rs = [r for r in rows if r['framework'] == fw and r['al_status'] == 'ok']
    print(fw, {k: sum(r[f'al_n_{k}'] or 0 for r in rs) for k in ['consistent', 'partial', 'conflicting', 'missing', 'incomparable']},
          'comparable_metrics', sum(1 for r in rs if r['al_has_comparable_metrics']), '/', len(rs))

print('\n== literature extra: verified/fake/lookup_failed sums; zero-ref runs')
for fw in FWS:
    rs = [r for r in rows if r['framework'] == fw and r['lit_status'] == 'ok']
    print(fw, 'verified', sum(r['lit_verified'] or 0 for r in rs), 'fake', sum(r['lit_fake'] or 0 for r in rs),
          'lookup_failed', sum(r['lit_lookup_failed'] or 0 for r in rs), 'runs_with_fab>0', sum(1 for r in rs if (r['lit_fab'] or 0) > 0))
json.dump(rows, open('/tmp/evalstat/all_runs.json', 'w'), indent=1, default=str)
