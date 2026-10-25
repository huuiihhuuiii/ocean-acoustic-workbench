"""Bounded, inspectable query expansion. This is not an embedding model."""
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

RULES = Path(__file__).resolve().parents[2] / 'ocean-acoustic-public/data/knowledge-retrieval-rules.json'
COX_MUNK = r'\bcox\s*[-–—]?\s*munk\b'


def focus_query(question):
    """Cox–Munk surface roughness is not the Munk sound-speed profile."""
    return re.sub(COX_MUNK, '', unicodedata.normalize('NFKC',str(question)).lower(), flags=re.I)


def cox_munk_only(question):
    text=unicodedata.normalize('NFKC',str(question)).lower()
    return bool(re.search(COX_MUNK,text,re.I)) and not re.search(r'\bmunk\b',focus_query(text))


@lru_cache(maxsize=1)
def rules():
    return json.loads(RULES.read_text(encoding='utf-8'))['rules']


def plan_query(question):
    text = unicodedata.normalize('NFKC', str(question)).lower().strip()
    matched = []
    for rule in rules():
        if all(re.search(pattern, text, re.I) for pattern in rule.get('all', [])) and (not rule.get('any') or any(re.search(pattern, text, re.I) for pattern in rule['any'])) and not any(re.search(pattern,text,re.I) for pattern in rule.get('unless',[])):
            matched.append(rule)
    # No unrestricted automatic decomposition: only maintained rules add terms.
    # At most three additional rank lists keep latency bounded at course scale.
    variants = list(dict.fromkeys([text] + [q for rule in matched for q in rule['queries']]))[:4]
    return {'query': text, 'queries': variants, 'rule_ids': [rule['id'] for rule in matched], 'target_node_ids': list(dict.fromkeys(n for rule in matched for n in rule['node_ids'])), 'method': 'maintained_contextual_query_rules', 'model_called': False}


def reciprocal_rank_fusion(rank_lists, limit=8, preferred_nodes=()):
    """Fuse independent rankings, retaining an explicit concept priority."""
    scores, rows = {}, {}
    preferred = set(preferred_nodes)
    for rank in rank_lists:
        for position, row in enumerate(rank, 1):
            rows.setdefault(row['id'], row)
            scores[row['id']] = scores.get(row['id'], 0) + 1 / (60 + position)
    ids = sorted(rows, key=lambda key: (rows[key].get('node_id') not in preferred, -scores[key], key))
    return [(rows[key], round(scores[key], 8)) for key in ids[:limit]]
