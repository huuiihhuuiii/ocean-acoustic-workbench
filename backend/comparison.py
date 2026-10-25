"""Matched-grid differences; local numerical stability is not physical accuracy."""
import numpy as np

def difference(a,b):
    if a['ranges_m']!=b['ranges_m'] or a['depths_m']!=b['depths_m'] or a['actual_receiver_depth_m']!=b['actual_receiver_depth_m']:
        return {'available':False,'reason':'距离/深度网格或实际接收深度不同，不能逐点比较'}
    out={'available':True}
    for key,prefix in [('curve_tl_db','receiver'),('tl_db','field')]:
        x=np.asarray(a[key],dtype=float);y=np.asarray(b[key],dtype=float)
        if x.shape!=y.shape:return {'available':False,'reason':'声场维度不同'}
        vx=np.isfinite(x);vy=np.isfinite(y);both=vx&vy;union=vx|vy
        values=np.abs(x[both]-y[both])
        out[prefix]={'common_points':int(both.sum()),'total_points':int(x.size),'valid_coverage_agreement':float(both.sum()/union.sum()) if union.any() else 0.0,'only_a_valid':int((vx&~vy).sum()),'only_b_valid':int((vy&~vx).sum()),'median_abs_db':float(np.median(values)) if len(values) else None,'p95_abs_db':float(np.percentile(values,95)) if len(values) else None,'max_abs_db':float(np.max(values)) if len(values) else None}
    return out

def analyze(plans,results):
    scenario=plans[0].get('scenario')
    if scenario not in ['model_compare','convergence']:return None
    roles={p.get('comparison_role'):(p,results.get(p.get('_job_id'))) for p in plans}
    names=[('kraken','bellhop','KRAKEN 与 BELLHOP')] if scenario=='model_compare' else [('baseline','beams','仅增加波束'),('baseline','step','仅减半步长'),('beams','both','增加波束后减半步长'),('step','both','减半步长后增加波束')]
    pairs=[]
    for first,second,label in names:
        entry={'label':label,'a_role':first,'b_role':second,'available':False,'reason':'等待两组结果；已删除的任务需恢复后比较'}
        if first in roles and second in roles:
            p,a=roles[first];q,b=roles[second]
            if p.get('environment_fingerprint')!=q.get('environment_fingerprint'):
                entry['reason']='环境快照不一致'
            elif a and b:
                entry.update(difference(a,b))
                if entry['available']:entry.pop('reason',None)
        pairs.append(entry)
    tolerance=plans[0].get('convergence_tolerance_db',1.0)
    stable=None
    if scenario=='convergence' and all(p['available'] for p in pairs):
        stable=all(p[metric]['max_abs_db'] is not None and p[metric]['max_abs_db']<=tolerance and p[metric]['valid_coverage_agreement']>=.99 for p in pairs for metric in ['receiver','field'])
    return {'scenario':scenario,'pairs':pairs,'tolerance_db':tolerance,'locally_stable':stable,'scope':'同一环境、C线性声速插值、相同频率/声源/接收网格与叠加方式。差值只统计共同有效点；共同覆盖率为共同有效点除以至少一组有效的点数。BELLHOP还受有限发射角覆盖与高频近似影响。局部稳定性不证明全面收敛、物理准确性或两种模型等价。'}
