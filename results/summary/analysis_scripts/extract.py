import json, glob, os, csv

ROOT = os.environ.get('BENCH_EVALS_ROOT', os.path.expanduser('~/ai_scientist_evals'))
rows = []
for f in sorted(glob.glob(f'{ROOT}/*/*/evaluation.json')):
    d = json.load(open(f))
    task = f.split('/')[-3]
    run = f.split('/')[-2]
    r, s = d['results'], d['scores']
    c = r['completeness']
    rd = c['run_dir']
    row = dict(task=task, venue=task.split('-')[0], run=run, framework=d['framework'])
    # completeness
    row.update(
        comp_overall=s['completeness']['overall_score'],
        comp_required=s['completeness']['required_score'],
        comp_bonus=s['completeness']['bonus_score'],
        comp_complete=s['completeness']['complete'],
        gate_idea=c['gate_scores']['idea'], gate_code=c['gate_scores']['code'],
        gate_results=c['gate_scores']['results'], gate_paper=c['gate_scores']['paper'],
        paper_status=(c['required'].get('paper') or {}).get('status'),
        missing=';'.join(c.get('missing') or []),
    )
    for b, v in (c.get('bonus') or {}).items():
        row[f'bonus_{b}'] = v is not None
    # idea
    ig = s['idea_generation']
    row.update(idea_status=ig['status'], idea_overall=ig['overall_score'],
               idea_novelty=ig['dimensions'].get('novelty'),
               idea_feasibility=ig['dimensions'].get('feasibility'),
               idea_clarity=ig['dimensions'].get('clarity'),
               idea_novelty_cat=ig.get('novelty_category'))
    # peer review
    pr = s['peer_review']
    row.update(pr_status=pr['status'], pr_overall=pr['overall_score'] if pr['status'] == 'ok' else None,
               pr_scale=pr.get('score_scale'))
    # alignment
    al = s['alignment']
    row.update(al_status=al['status'], al_score=al['overall_alignment_score'],
               al_direction=al['direction_consistency'])
    ac = r['alignment'].get('comparison') or {}
    labels = [x.get('label') for x in ac.get('claim_alignment', [])]
    for lab in ['consistent', 'partial', 'conflicting', 'missing', 'incomparable']:
        row[f'al_n_{lab}'] = labels.count(lab) if ac else None
    row['al_has_comparable_metrics'] = (ac.get('summary') or {}).get('has_comparable_metrics')
    # literature
    lr = r['literature_review']
    ls = s['literature_review']
    row.update(lit_status=lr['status'], lit_reason=lr.get('reason'), lit_refs=lr.get('agent_ref_count'),
               lit_fab=ls.get('fabrication_rate'), lit_recall=ls.get('coverage_recall'),
               lit_precision=ls.get('coverage_precision'),
               lit_rec3=ls.get('recency_ratio_3y'), lit_rec5=ls.get('recency_ratio_5y'))
    fab = lr.get('fabrication') or {}
    row.update(lit_verified=fab.get('verified_count'), lit_fake=fab.get('fake_count'),
               lit_lookup_failed=fab.get('lookup_failed_count'))
    # experiment analysis
    ea = r['experiment_analysis']; es = s['experiment_analysis']
    row.update(ea_success=es['experiment_success'], ea_idea_code=es['idea_code_score'],
               ea_idea_code_status=ea['idea_code_consistency'].get('status'),
               ea_setup=es['setup_coverage'],
               ea_setup_ds=(ea['setup_coverage'].get('datasets') or {}).get('coverage'),
               ea_setup_bl=(ea['setup_coverage'].get('baselines') or {}).get('coverage'),
               ea_setup_mt=(ea['setup_coverage'].get('metrics') or {}).get('coverage'),
               ea_flags=';'.join(k for k, v in (ea['setup_coverage'].get('flags') or {}).items() if v),
               ea_ablation=es['ablation_coverage_score'], ea_ablation_ok=es['overall_ablation_ok'],
               ea_signif_ok=es['overall_significance_ok'],
               ea_abl_status=ea['ablation_significance'].get('status'),
               ea_abl_study_type=ea['ablation_significance'].get('study_type'),
               ea_rp=es['results_paper_score'], ea_rp_status=ea['results_paper_consistency'].get('status'),
               ea_hiding=es['hiding_unfavorable_suspected'],
               ea_metrics_path=ea.get('metrics_path'),
               ea_warnings=';'.join(ea['experiment_success'].get('warnings') or []),
               ea_suspicious=len(ea['experiment_success'].get('suspicious_values') or []))
    fs = d.get('fair_scores', {})
    row.update(fair_mean=fs.get('fair_mean_0_1'), fair_n_axes=len(fs.get('applicable_axes') or []),
               fair_axes=';'.join(fs.get('applicable_axes') or []))
    # manifest
    m = os.path.join(rd, 'artifacts/manifest.json')
    row['manifest'] = os.path.exists(m)
    if row['manifest']:
        j = json.load(open(m))
        row['returncode'] = j.get('returncode')
        row['bench_complete'] = j.get('benchmark_complete')
        row['duration_h'] = ((j.get('timing') or {}).get('duration_sec') or 0) / 3600 or None
        u = j.get('usage') or {}
        row['tokens'] = u.get('total_tokens'); row['completion_tokens'] = u.get('completion_tokens')
        row['llm_calls'] = u.get('calls')
        cst = j.get('cost')
        row['cost_usd'] = cst.get('usd') if isinstance(cst, dict) else cst
        row['issues'] = ';'.join((j.get('benchmark_issues') or []) + (j.get('validation_issues') or []))
        row['forced_finalize'] = j.get('forced_finalize')
        st = j.get('status')
        row['manifest_status'] = json.dumps(st)[:200] if st is not None else None
    row['run_dir'] = rd
    # other runs of same framework for this task (not evaluated)
    ws = os.path.dirname(rd)
    row['n_runs_same_fw'] = len([x for x in os.listdir(ws) if x.startswith(d['framework'] + '_')]) if os.path.isdir(ws) else None
    rows.append(row)

keys = []
for r in rows:
    for k in r:
        if k not in keys: keys.append(k)
with open('/tmp/evalstat/all_runs.csv', 'w', newline='') as fh:
    w = csv.DictWriter(fh, keys); w.writeheader(); w.writerows(rows)
json.dump(rows, open('/tmp/evalstat/all_runs.json', 'w'), indent=1, default=str)
print(len(rows), len(keys))
