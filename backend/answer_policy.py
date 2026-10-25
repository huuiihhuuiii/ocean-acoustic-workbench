"""Explicit retrieval coverage and pretrained-knowledge routing; no training."""
import json
from datetime import datetime, timezone
from pathlib import Path
import uuid
from evidence_policy import assess_evidence

def policy(evidence, scope='course', mode='chat', question=''):
    if scope not in ('course', 'general'):
        raise ValueError('请选择课程依据或模型一般知识')
    covered = bool(evidence)
    template = mode == 'agent'
    status = 'course_evidence' if covered else 'course_template' if template else 'no_course_evidence'
    if covered:
        notice = '本次使用检索到的课程或公开资料；引用不表示已覆盖全部海洋知识。' if scope == 'course' else '资料依据与模型一般知识须分别说明；一般知识未经本项目原文核验。'
    else:
        notice = '本次分析授权项目；未检索到对应课程正文。' if template else '未检索到课程依据。可切换到模型一般知识或补充资料。' if scope == 'course' else '未检索到课程依据；本次使用模型一般知识，未经本项目原文核验。'
    rule = '当前选择【仅依据资料】，结论只基于检索到的课程或公开片段和实际读取的授权项目，依据不足时明确缺口。' if scope == 'course' else '当前选择【资料 + 模型知识】，允许使用模型已有的一般知识回答资料未覆盖的问题；与资料依据分别标注。没有本次提供的资料不得生成引用。公开网页是带抓取时间的快照，区分原页更新时间、抓取时间和观测时间，不得声称本轮实时搜索或编造最新海洋观测数值。'
    assessment=assess_evidence(question,evidence)
    if assessment['status']=='missing_observation_data':
        status='missing_observation_data'
        notice='无法依据现有资料给出该时空位置的实测数值。请提供带观测时间、站位/坐标、深度、变量、单位和质量标记的数据；当前教材和公开网页仅能解释原理。'
    return {'knowledge_scope': scope, 'coverage_status': status, 'coverage_notice': notice, 'can_generate': assessment['can_answer_requested_numeric'] and (scope == 'general' or covered or template), 'rule': rule+' 检索到的引用是候选资料，不表示命题已经得到支持；时间地点相关数值必须来自匹配的实测数据。', 'evidence_assessment':assessment}

def note_gap(path, question):
    path = Path(path)
    rows = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    text = question.strip()[:600]
    now = datetime.now(timezone.utc).isoformat()
    existing = next((r for r in rows if r['question'] == text), None)
    if existing:
        existing.update(count=existing['count'] + 1, last_seen=now)
    else:
        rows.insert(0, {'id': str(uuid.uuid4()), 'question': text, 'count': 1, 'created_at': now, 'last_seen': now, 'status': 'pending'})
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(rows[:40], ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
