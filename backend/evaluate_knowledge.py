"""No-key, no-network retrieval regression. Not generated-answer accuracy.

python backend/evaluate_knowledge.py [--include-private] [--baseline]
The default reads public cards/snapshots only, never private textbook excerpts.
"""
import argparse
from contextlib import nullcontext
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import knowledge
from evidence_policy import assess_evidence
import query_planning

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / 'docs/benchmarks/knowledge-60.json'


def evaluate(benchmark=BENCHMARK, limit=8, include_private=False, baseline=False):
    specification=json.loads(Path(benchmark).read_text(encoding='utf-8'))
    cases=specification['cases']
    results=[]
    index_context=nullcontext() if include_private else patch.object(knowledge,'CHUNKS',Path('__offline_public_benchmark_no_private_index__'))
    rewrite_context=patch.object(query_planning,'rules',return_value=[]) if baseline else nullcontext()
    with index_context, rewrite_context:
        for case in cases:
            evidence=knowledge.retrieve(case['question'],limit)
            assessment=assess_evidence(case['question'],evidence)
            expected_nodes=set(case['expected_node_ids']);expected_sources=set(case['expected_any_source_ids'])
            actual_nodes={row.get('node_id') for row in evidence};actual_sources={row['source_id'] for row in evidence}
            hit=bool(expected_nodes & actual_nodes or expected_sources & actual_sources)
            positions=[i for i,row in enumerate(evidence,1) if row.get('node_id') in expected_nodes or row['source_id'] in expected_sources]
            locator=lambda ref:(ref.get('source_id'),ref.get('pdf_page'),'' if ref.get('pdf_page') else ref.get('url') or ref.get('locator',''))
            expected_locators={locator(ref) for ref in case['source_references']}
            actual_locators={locator(ref) for row in evidence for ref in (row.get('all_references') or [row])}
            results.append({'id':case['id'],'category':case['category'],'expected_node_ids':sorted(expected_nodes),'returned_node_ids':[row.get('node_id') for row in evidence],'returned_source_ids':list(dict.fromkeys(row['source_id'] for row in evidence)),'returned_ids':[row['id'] for row in evidence],'hit_at_k':hit if case['retrieval_expected'] else None,'source_locator_hit_at_k':bool(expected_locators & actual_locators) if case['retrieval_expected'] else None,'node_recall_at_k':len(expected_nodes & actual_nodes)/len(expected_nodes) if expected_nodes else None,'reciprocal_rank':1/min(positions) if positions else 0,'empty':not evidence,'gate_status':assessment['status'],'gate_correct':assessment['status']==case['expected_gate_status']})
    positives=[row for row in results if row['hit_at_k'] is not None]
    recalls=[row['node_recall_at_k'] for row in results if row['node_recall_at_k'] is not None]
    gates=[row for row in results if row['category']=='numeric_gate'];unknown=[row for row in results if row['category']=='unknown']
    mean=lambda values:round(sum(values)/len(values),6) if values else None
    return {'benchmark':'knowledge-60','benchmark_sha256':hashlib.sha256(Path(benchmark).read_bytes()).hexdigest(),'benchmark_cases':len(cases),'run_at':datetime.now(timezone.utc).isoformat(),'k':limit,'private_index_included':include_private,'maintained_rewrites_enabled':not baseline,'model_calls':0,'network_calls':0,'metrics':{'positive_questions':len(positives),'hit_at_k':mean([row['hit_at_k'] for row in positives]),'source_locator_hit_at_k':mean([row['source_locator_hit_at_k'] for row in positives]),'node_recall_at_k':mean(recalls),'mrr_at_k':mean([row['reciprocal_rank'] for row in positives]),'numeric_gate_correct':sum(row['gate_correct'] for row in gates),'numeric_gate_cases':len(gates),'unknown_empty_correct':sum(row['empty'] for row in unknown),'unknown_cases':len(unknown),'all_gate_correct':sum(row['gate_correct'] for row in results)},'interpretation':'开发者固定题集上的候选召回与缺证据门控回归；不是独立盲测，不代表模型回答正确率、物理准确率或引用支持率。','results':results}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark',default=str(BENCHMARK));parser.add_argument('--limit',type=int,default=8)
    parser.add_argument('--include-private',action='store_true');parser.add_argument('--baseline',action='store_true',help='Disable maintained contextual rewrites, keeping the same corpus and evidence gate.')
    parser.add_argument('--output',default=str(Path(__file__).resolve().parents[1]/'.local/kb/evaluation-60.json'))
    args=parser.parse_args()
    if not 1<=args.limit<=20:parser.error('--limit must be 1..20')
    report=evaluate(args.benchmark,args.limit,args.include_private,args.baseline)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},ensure_ascii=False,indent=2))
