"""Candidate provenance and observation sufficiency, without model/API calls.

Relevance, citation existence and support for a generated claim are different
properties. This module never marks semantic/physical claim support verified.
Only a future trusted data adapter may supply structured observations; ordinary
text, NOAA explanatory pages and their fetch dates do not meet that contract.
"""
from datetime import datetime, timezone
import math
import re

VARIABLES = {
    'sound_speed': r'声速|声音.*速度|sound speed',
    'temperature': r'海温|海水温度|水温|\btemperature\b',
    'salinity': r'盐度|salinity',
    'sea_level': r'海平面|潮位|sea level',
    'wave_height': r'浪高|波高|wave height',
    'current_speed': r'流速|海流速度|current speed',
    'oxygen': r'溶解氧|含氧量|dissolved oxygen',
}
REGIONS = ('东海', '南海', '黄海', '渤海', '北海', '日本海', '太平洋', '大西洋', '印度洋', '北冰洋', '南大洋', 'east china sea', 'south china sea')
CURRENT = r'今天|今日|现在|当前|此刻|实时|最新|此时|today|right now|\bcurrent(?:ly)?\b(?!\s+(?:speed|direction|meter|data))|latest|real.time'
NUMERIC = r'多少|多高|多大|几度|几米|数值|测量值|实测值|观测值|是多少|哪个.*快|哪个.*高|how (?:much|high|fast)|what is.*(?:value|temperature|speed|level)'
CONCEPTUAL = r'为什么|为何|如何|原理|机制|什么因素|有什么关系|是什么意思|是什么|怎么形成|方法|假设|理想|算例|研究|论文|why|mechanism|method|affect|definition'


def observation_requirements(question):
    text = str(question).lower()
    variables = [name for name, pattern in VARIABLES.items() if re.search(pattern, text, re.I)]
    locations = [place for place in REGIONS if place in text]
    current = bool(re.search(CURRENT, text, re.I))
    year = re.search(r'(?<!\d)(?:19|20)\d{2}(?!\d)', text)
    depth = re.search(r'(\d+(?:\.\d+)?)\s*(千米|公里|km|米|m)(?:深|水深|处|深度)?', text)
    depth_m = float(depth[1]) * (1000 if depth[2] in ('千米', '公里', 'km') else 1) if depth else None
    if depth_m is None:
        for phrase, value in [('一千米',1000),('一公里',1000),('一百米',100),('五百米',500),('两千米',2000),('二千米',2000)]:
            if phrase in text:depth_m=value;break
    implicit = bool(variables and (current or (locations and depth_m is not None)) and not re.search(CONCEPTUAL,text,re.I))
    numeric = bool(re.search(NUMERIC,text,re.I))
    needs = bool(variables and (numeric or implicit) and (current or locations or year))
    return {'requires_observation': needs, 'variables': variables, 'locations': locations, 'depth_m': depth_m, 'current_requested': current, 'year': int(year[0]) if year else None, 'numeric_requested': numeric, 'implicit_numeric_requested':implicit}


def _observation_matches(row, request, now):
    # Retrieval snippets cannot self-promote to measurements. This origin must
    # be set by a trusted, non-LLM ingestion adapter after QC and unit parsing.
    if row.get('evidence_type') != 'structured_observation' or row.get('verification_status') != 'trusted_observation_adapter':return False
    value = row.get('observation') or {}
    if value.get('variable') not in request['variables'] or not value.get('units') or not isinstance(value.get('value'), (int,float)) or isinstance(value.get('value'), bool) or not math.isfinite(value['value']):return False
    if value.get('quality_control') != 'accepted' or not row.get('source_id') or not row.get('url'):return False
    if not request['locations'] or not any(place in str(value.get('location','')).lower() for place in request['locations']):return False
    if value['variable'] in {'sound_speed','temperature','salinity','oxygen'} and (request['depth_m'] is None or value.get('depth_m') != request['depth_m']):return False
    try:date=datetime.fromisoformat(value['observed_at'].replace('Z','+00:00')).astimezone(timezone.utc)
    except (KeyError,ValueError,TypeError):return False
    if request['current_requested']:
        age=(now-date).total_seconds()
        if age < -300 or age > 86400:return False
    elif request['year']:
        if date.year != request['year']:return False
    else:return False  # An exact observation time is still missing.
    return True


def assess_evidence(question, evidence, now=None):
    request = observation_requirements(question)
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:instant=instant.replace(tzinfo=timezone.utc)
    matching = [row for row in evidence if request['requires_observation'] and _observation_matches(row, request, instant)]
    observations = [row['id'] for row in matching]
    pairs={(variable,location) for variable in request['variables'] for location in request['locations']}
    covered={(row['observation']['variable'],location) for row in matching for location in request['locations'] if location in str(row['observation'].get('location','')).lower()}
    blocked = request['requires_observation'] and (not observations or not pairs or not pairs.issubset(covered))
    status = 'missing_observation_data' if blocked else 'structured_observation_available' if observations else 'candidate_evidence_only' if evidence else 'no_evidence'
    return {'status':status, 'candidate_count':len(evidence), 'candidate_ids':[row['id'] for row in evidence], 'claim_support_verified':False, 'semantic_support_checked':False, 'citation_role':'retrieval_candidates', 'observation_requirements':request, 'observation_ids':observations, 'missing_observation_pairs':[{'variable':variable,'location':location} for variable,location in sorted(pairs-covered)], 'can_answer_requested_numeric':not blocked, 'note':'当前资料仅为相关候选；尚未逐项核验生成答案与引用的蕴含关系。' if not blocked else '未检索到同时符合时间、海域、深度、变量、单位和质量控制要求的实测记录；教材典型值、历史案例、气候态与网页抓取时间均不能替代。'}


def annotate_candidates(evidence, question):
    assessment=assess_evidence(question,evidence)
    for row in evidence:
        row['support_status']='candidate_only'
        row['claim_support_verified']=False
        row['evidence_assessment']={'status':assessment['status'],'requires_observation':assessment['observation_requirements']['requires_observation'],'claim_support_verified':False}
    return evidence


def validate_citation_ids(answer, evidence):
    """Check bracketed known IDs only; not entailment or answer correctness."""
    known={row['id'] for row in evidence}
    # Plain prose [1] and arbitrary labels must not silently count as sources.
    used=list(dict.fromkeys(re.findall(r'\[([A-Za-z][A-Za-z0-9_.:-]{1,100})\]',str(answer))))
    locators=list(dict.fromkeys((source,int(page)) for source,page in re.findall(r'\[([A-Za-z][A-Za-z0-9_-]{0,64})\s*,\s*(\d{1,5})\]',str(answer))))
    available={(ref.get('source_id'),ref.get('pdf_page')) for row in evidence for ref in (row.get('all_references') or [row])}
    return {'used_ids':used,'unknown_ids':[item for item in used if item not in known],'known_ids':[item for item in used if item in known],'used_source_locators':[{'source_id':s,'pdf_page':p} for s,p in locators],'unknown_source_locators':[{'source_id':s,'pdf_page':p} for s,p in locators if (s,p) not in available],'claim_support_verified':False,'check':'citation_id_and_locator_membership_only'}
