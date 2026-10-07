import json, statistics as S, collections
rows = json.load(open('/tmp/evalstat/all_runs.json'))
FWS = ['aris', 'deepscientist', 'evoscientist', 'ai_scientist', 'researchclaw', 'tiny_scientist', 'airesearcher']

NUM = [
    ('fair_mean', '综合 fair_mean (0-1)'),
    ('comp_overall', 'completeness.overall (0-1)'),
    ('comp_required', 'completeness.required (0-1)'),
    ('comp_bonus', 'completeness.bonus'),
    ('gate_idea', 'gate.idea'), ('gate_code', 'gate.code'), ('gate_results', 'gate.results'), ('gate_paper', 'gate.paper'),
    ('idea_overall', 'idea.overall (1-5)'), ('idea_novelty', 'idea.novelty (1-5)'),
    ('idea_feasibility', 'idea.feasibility (1-5)'), ('idea_clarity', 'idea.clarity (1-5)'),
    ('pr_overall', 'peer_review APR (1-10)'),
    ('al_score', 'alignment.score (0-1)'),
    ('lit_refs', 'lit.引用数'), ('lit_fab', 'lit.fabrication_rate (低好)'), ('lit_recall', 'lit.recall'),
    ('lit_precision', 'lit.precision'), ('lit_rec3', 'lit.recency_3y'), ('lit_rec5', 'lit.recency_5y'),
    ('ea_idea_code', 'EA.idea_code (1-5)'), ('ea_setup', 'EA.setup_coverage (0-1)'),
    ('ea_setup_ds', 'EA.setup.datasets'), ('ea_setup_bl', 'EA.setup.baselines'), ('ea_setup_mt', 'EA.setup.metrics'),
    ('ea_ablation', 'EA.ablation_coverage (0-1)'), ('ea_rp', 'EA.results_paper (1-5)'),
    ('duration_h', '运行时长(h)'), ('tokens', 'tokens'), ('cost_usd', '成本 USD'),
]
BOOL = [('comp_complete', 'complete=True'), ('ea_success', 'experiment_success'),
        ('ea_ablation_ok', 'ablation_ok'), ('ea_signif_ok', 'significance_ok'), ('ea_hiding', 'hiding_unfavorable')]


def stat(vals):
    v = [x for x in vals if x is not None and x != '']
    if not v: return dict(n=0)
    return dict(n=len(v), mean=S.mean(v), median=S.median(v), max=max(v), min=min(v))


def fmt(x, k):
    if x is None: return '-'
    if k == 'tokens': return f'{x/1e6:.2f}M'
    return f'{x:.3f}' if isinstance(x, float) else str(x)


out = []
for k, name in NUM:
    allst = stat([r.get(k) for r in rows])
    per = {fw: stat([r.get(k) for r in rows if r['framework'] == fw]) for fw in FWS}
    out.append((name, k, allst, per))

for name, k, a, per in out:
    print(f'## {name}')
    print(f"  ALL   n={a['n']:3d} mean={fmt(a.get('mean'),k)} med={fmt(a.get('median'),k)} max={fmt(a.get('max'),k)} min={fmt(a.get('min'),k)}")
    for fw, p in per.items():
        print(f"  {fw:15s} n={p['n']:2d} mean={fmt(p.get('mean'),k)} max={fmt(p.get('max'),k)} min={fmt(p.get('min'),k)}")

print('\n## BOOLEAN (true / non-null)')
for k, name in BOOL:
    def br(rs):
        v = [r.get(k) for r in rs if r.get(k) is not None]
        return f'{sum(1 for x in v if x)}/{len(v)}'
    print(f'{name:22s} ALL {br(rows):8s} ' + ' '.join(f'{fw}:{br([r for r in rows if r["framework"]==fw])}' for fw in FWS))

print('\n## STATUS distributions')
for k in ['idea_status', 'pr_status', 'al_status', 'al_direction', 'lit_status', 'lit_reason', 'paper_status',
          'ea_idea_code_status', 'ea_abl_status', 'ea_rp_status', 'idea_novelty_cat', 'ea_abl_study_type', 'returncode', 'bench_complete']:
    print(k)
    for fw in FWS:
        print('   ', fw, dict(collections.Counter(str(r.get(k)) for r in rows if r['framework'] == fw)))
json.dump(out, open('/tmp/evalstat/stats.json', 'w'), default=str)
