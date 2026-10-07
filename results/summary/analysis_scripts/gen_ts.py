import json, statistics as S, collections
rows = json.load(open('/tmp/evalstat/all_runs.json'))
FWS = ['aris', 'deepscientist', 'evoscientist', 'ai_scientist', 'researchclaw', 'tiny_scientist', 'airesearcher']
NAMES = {'aris': 'ARIS', 'deepscientist': 'DeepScientist', 'evoscientist': 'EvoScientist', 'ai_scientist': 'AI-Scientist v2',
         'researchclaw': 'ResearchClaw', 'tiny_scientist': 'TinyScientist', 'airesearcher': 'AI-Researcher'}


def cell(rs, k, d=2, pct=False):
    v = [r[k] for r in rs if r.get(k) is not None]
    if not v: return '0 / — / —'
    f = (lambda x: f'{x*100:.0f}%') if pct else (lambda x: f'{x:.{d}f}')
    return f'{len(v)} / {f(S.mean(v))} / {f(max(v))}'


def bcell(rs, k):
    v = [r[k] for r in rs if r.get(k) is not None]
    return f'{sum(1 for x in v if x)}/{len(v)}' if v else '0/0'


def table(spec):
    out = []
    for label, k, *opt in spec:
        d = opt[0] if opt else 2
        line = [label, cell(rows, k, d)]
        for fw in FWS:
            line.append(cell([r for r in rows if r['framework'] == fw], k, d))
        out.append(line)
    return out


T = {}
T['comp'] = table([('综合 fair_mean (0-1)', 'fair_mean'), ('严格综合 strict4 (0-1，缺轴记0)', 'strict4'),
                   ('完成度总分 (0-1)', 'comp_overall'), ('必需产物分 (0-1)', 'comp_required'), ('加分产物分', 'comp_bonus'),
                   ('门: idea', 'gate_idea'), ('门: code', 'gate_code'), ('门: results', 'gate_results'), ('门: paper (PDF=1, 仅TeX/JSON=0.5)', 'gate_paper')])
T['idea'] = table([('Idea 总分', 'idea_overall'), ('新颖性 Novelty', 'idea_novelty'), ('可行性 Feasibility', 'idea_feasibility'), ('清晰度 Clarity', 'idea_clarity')])
T['peer'] = table([('Stanford APR 总分 (1-10)', 'pr_overall')])
T['align'] = table([('结论对齐分 (0-1)', 'al_score')])
T['lit'] = table([('引用条数', 'lit_refs', 1), ('编造率 (越低越好；“最高”=最差)', 'lit_fab'), ('召回率 recall', 'lit_recall'),
                  ('精确率 precision', 'lit_precision'), ('近 3 年占比', 'lit_rec3'), ('近 5 年占比', 'lit_rec5')])
T['exp'] = table([('idea↔代码一致性 (1-5)', 'ea_idea_code'), ('设置覆盖率 (0-1)', 'ea_setup'), ('  · 数据集覆盖', 'ea_setup_ds'),
                  ('  · 基线覆盖', 'ea_setup_bl'), ('  · 指标覆盖', 'ea_setup_mt'), ('消融覆盖 (0-1)', 'ea_ablation'),
                  ('结果↔论文一致性 (1-5)', 'ea_rp')])
T['cost'] = table([('LLM 调用次数', 'l_calls', 0), ('有效运行时长 (h)', 'l_hours'), ('Token (M)', 'l_tok_m', 1), ('成本 (USD)', 'l_cost_usd')])
for r in rows:
    r['l_tok_m'] = r['l_tokens'] / 1e6 if r.get('l_tokens') is not None else None
T['cost'] = table([('LLM 调用次数', 'l_calls', 0), ('有效运行时长 (h)', 'l_hours'), ('Token (M)', 'l_tok_m', 1), ('成本 (USD)', 'l_cost_usd')])

B = []
for label, k in [('complete=True（四门全满且有 PDF）', 'comp_complete'), ('实验成功 experiment_success', 'ea_success'),
                 ('消融达标 ablation_ok', 'ea_ablation_ok'), ('显著性达标 significance_ok', 'ea_signif_ok'),
                 ('隐藏不利结果嫌疑 hiding', 'ea_hiding')]:
    B.append([label, bcell(rows, k)] + [bcell([r for r in rows if r['framework'] == fw], k) for fw in FWS])
T['bool'] = B

# ranking
rank = []
for fw in FWS:
    rs = [r for r in rows if r['framework'] == fw]
    rank.append(dict(name=NAMES[fw], fair=round(S.mean(r['fair_mean'] for r in rs), 3), strict=round(S.mean(r['strict4'] for r in rs), 3),
                     complete=round(sum(r['comp_complete'] for r in rs) / 34, 3)))
rank.sort(key=lambda x: -x['fair'])
T['rank'] = rank

# tasks
tasks = sorted(set(r['task'] for r in rows))
tl = []
for t in tasks:
    rs = [r for r in rows if r['task'] == t]
    b = max(rs, key=lambda r: r['fair_mean']); w = min(rs, key=lambda r: r['fair_mean'])
    aprs = [r['pr_overall'] for r in rs if r['pr_overall']]
    tl.append([t[:44], f"{S.mean(r['fair_mean'] for r in rs):.3f}", f"{NAMES[b['framework']]} {b['fair_mean']:.2f}",
               f"{NAMES[w['framework']]} {w['fair_mean']:.2f}", str(sum(r['comp_complete'] for r in rs)),
               str(sum(bool(r['ea_success']) for r in rs)), f"{S.mean(aprs):.2f}" if aprs else '—'])
tl.sort(key=lambda x: float(x[1]))
T['tasks'] = tl
json.dump(T, open('/tmp/evalstat/ts_data.json', 'w'), ensure_ascii=False)
print(json.dumps(T['rank'], ensure_ascii=False))
print(sum(1 for r in rows if (r['lit_fab'] or 0) >= 0.5), 'fab>=0.5 runs')
print(collections.Counter(r['framework'] for r in rows if (r['lit_fab'] or 0) >= 0.5))
# CSV export of flat rows
import csv
keys = list(rows[0].keys())
for r in rows:
    for k in r:
        if k not in keys: keys.append(k)
with open('/tmp/evalstat/all_runs.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, keys); w.writeheader(); w.writerows(rows)
