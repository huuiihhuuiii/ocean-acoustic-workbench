"""Offline BM25 retrieval plus bounded, typed course-graph context.

The BM25 scorer is reused from Apache-2.0 rank_bm25 (backend/vendor).
Graph context follows the source-grounded local-retrieval design discussed by
LightRAG and Microsoft GraphRAG; their frameworks are not installed or called.
No embeddings, model training or paid API calls are needed by this module.
"""
from copy import deepcopy
from contextlib import closing
from functools import lru_cache
import hashlib
import json
import re
import sqlite3
import unicodedata
from pathlib import Path

from vendor.rank_bm25 import BM25Okapi
from query_planning import plan_query, reciprocal_rank_fusion, focus_query, cox_munk_only, COX_MUNK


ALIASES = {
    "sound pressure": ("声压", "acoustic_pressure"),
    "声压": ("声压", "acoustic_pressure"),
    "acoustic intensity": ("声强", "acoustic_intensity"),
    "声强": ("声强", "acoustic_intensity"),
    "acoustic impedance": ("声阻抗", "acoustic_impedance"),
    "声阻抗": ("声阻抗", "acoustic_impedance"),
    "decibel": ("分贝", "decibel"),
    "分贝": ("分贝", "decibel"),
    "spherical spreading": ("球面扩展", "spherical_spreading"),
    "cylindrical spreading": ("柱面扩展", "cylindrical_spreading"),
    "deep sound channel": ("深海声道", "deep_sound_channel"),
    "surface duct": ("表面声道", "surface_duct"),
    "gaussian beam": ("高斯波束", "gaussian_beams"),
    "coupled modes": ("耦合模态", "coupled_modes"),
    "mode excitation": ("模态激励", "mode_excitation"),
    "ray tracing": ("射线方法", "ray_method"),
    "convergence zone": ("汇聚区", "convergence_zone"),
    "tl": ("传播损失", "transmission_loss"),
    "transmission loss": ("传播损失", "transmission_loss"),
    "传输损失": ("传播损失", "transmission_loss"),
    "ssp": ("声速剖面", "sound_speed_profile"),
    "sound speed profile": ("声速剖面", "sound_speed_profile"),
    "源深": ("声源深度", "source_depth"),
    "source depth": ("声源深度", "source_depth"),
    "receiver depth": ("接收深度", "receiver_depth"),
    "kraken": ("KRAKEN", "matlab_kraken_wrapper"),
    "bellhop": ("BELLHOP", "bellhop"),
    "ram": ("RAM", "ram"),
    "pe": ("抛物方程", "parabolic_equation"),
    "parabolic equation": ("抛物方程", "parabolic_equation"),
    "ctd": ("CTD", "ctd"),
    "munk": ("Munk 理想剖面", "munk_profile"),
    "normal modes": ("简正波", "normal_mode_field"),
    "normal mode": ("简正波", "normal_mode_field"),
    "简正波": ("简正波", "normal_mode_field"),
    "模态激励": ("模态激励", "mode_excitation"),
    "模态激发": ("模态激励", "mode_excitation"),
    "刚性海底": ("刚性海底边界", "rigid_bottom"),
    "焦散": ("焦散与阴影区", "caustic_shadow"),
    "近零声压": ("近零声压与无效值", "near_zero_pressure"),
    "耦合模态": ("耦合模态与绝热近似", "coupled_modes"),
    "绝热近似": ("耦合模态与绝热近似", "coupled_modes"),
    "海底介质": ("海底介质与损耗", "seabed"),
    "海底损耗": ("海底介质与损耗", "seabed"),
    "coherent": ("相干", "coherent_modal_sum"),
    "snell": ("Snell", "snell"),
    "helmholtz": ("Helmholtz", "helmholtz"),
    "env": ("ENV 环境文件", "env_file"),
    "flp": ("FLP 场计算文件", "flp_file"),
    "shd": ("SHD 复声压输出", "binary_shd_pressure"),
    "asiaex": ("ASIAEX", "ASIAEX_CTD"),
    "sw06": ("SW06", "SW06_CTD"),
}
STOP_TOKENS = {"请问", "如何", "怎么", "什么", "为何", "为什么", "一下", "解释", "说明", "有关", "相关", "知识", "课程", "我们", "这个", "以及", "哪些", "是否", "可以", "问题", "进行", "the", "and", "with", "what", "how", "please", "explain", "is", "of", "to", "a", "an"}
STOP_TOKENS.update({'海洋','海水','水下','水中','ocean','marine','water','underwater'})


def normalize(text):
    return unicodedata.normalize("NFKC", str(text)).lower().strip()


def contains_term(text, term):
    term = normalize(term)
    if term.isascii():
        return bool(re.search(r"(?<![a-z0-9_])" + re.escape(term) + r"(?![a-z0-9_])", text))
    return term in text


def tokenize(text):
    """Use the same Latin tokens / Chinese n-grams for indexing and queries."""
    text = normalize(text)
    result = re.findall(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)?", text)
    for block in re.findall(r"[\u4e00-\u9fff]+", text):
        for width in (2, 3, 4):
            result.extend(block[i:i + width] for i in range(len(block) - width + 1))
    return [term for term in result if term not in STOP_TOKENS]


def load_chunks(path):
    """Read a local index only. Never expose a source file's absolute path."""
    path = Path(path)
    if not path.is_file():
        return []
    return list(_load_chunks_cached(str(path.resolve()), path.stat().st_mtime_ns, path.stat().st_size))


def load_index_report(path):
    path=Path(path)
    if not path.is_file():return {}
    return deepcopy(_load_report_cached(str(path.resolve()),path.stat().st_mtime_ns,path.stat().st_size))


@lru_cache(maxsize=3)
def _load_report_cached(filename,modified,size):
    path=Path(filename);report={}
    if path.suffix in {'.sqlite','.sqlite3','.db'}:
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as database:
            if database.execute("SELECT 1 FROM sqlite_master WHERE name='metadata' AND type='table'").fetchone():
                row=database.execute("SELECT value FROM metadata WHERE key='report'").fetchone()
                if row:report=json.loads(row[0])
    if not report:
        sidecar=path.with_suffix('.report.json')
        if sidecar.is_file():report=json.loads(sidecar.read_text(encoding='utf-8'))
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):digest.update(block)
    report['index_revision']=digest.hexdigest()
    return report


@lru_cache(maxsize=3)
def _load_chunks_cached(filename, modified, size):
    path = Path(filename)
    if path.suffix in {".sqlite", ".sqlite3", ".db"}:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as database:
            rows = [row[0] for row in database.execute("SELECT payload FROM chunks ORDER BY id")]
    else:
        rows = path.read_text(encoding="utf-8").splitlines()
    chunks, ids = [], set()
    for line_number, line in enumerate(rows, 1):
        if not line.strip():
            continue
        chunk = json.loads(line)
        if not chunk.get("id") or chunk["id"] in ids:
            raise ValueError(f"知识片段编号缺失或重复：第 {line_number} 行")
        if not chunk.get("source_id") or not isinstance(chunk.get("text"), str):
            raise ValueError(f"知识片段来源或原文缺失：第 {line_number} 行")
        ids.add(chunk["id"])
        value={key: value for key, value in chunk.items() if key not in {"path", "source_path", "file_path"}}
        if value.get('evidence_type')=='source_excerpt' and value.get('ingestion_version',1)<2:
            value['text_integrity_warning']='旧版文本索引可能丢失上/下标，须核对原页并从授权原文重建；当前未自动恢复公式。'
        chunks.append(value)
    return tuple(chunks)


def _raw_card_text(card, node):
    if card.get("evidence_type") == "source_excerpt":
        return card.get("text", "")
    return " ".join([card.get("label", ""), card.get("label", ""), card.get("text", ""), card.get("formula", ""), card.get("conditions", ""), node.get("misconception", ""), *node.get("tags", [])])


def _expanded_text(text):
    normalized = normalize(text)
    # Bilingual course vocabulary is expanded on both sides, so Chinese
    # questions can find English original pages without a paid embedding API.
    expansions = [phrase for term, (phrase, _) in ALIASES.items() if contains_term(normalized, term)]
    return normalized + " " + " ".join(normalize(phrase) for phrase in expansions)


@lru_cache(maxsize=2)
def _lexical_corpus(raw_texts):
    """Cache tokenization and BM25 together; rebuild only when text changes.

    Loaded source strings are themselves cached by file revision. Repeated
    queries hash those strings instead of expanding/retokenizing thousands of
    snippets. Only selected results are deep-copied by the request path.
    """
    expanded = tuple(_expanded_text(text) for text in raw_texts)
    corpus = tuple(tuple(tokenize(text)) for text in expanded)
    return expanded, tuple(frozenset(terms) for terms in corpus), BM25Okapi(corpus) if any(corpus) else None


def _retrieve_single(graph, cards, query, limit=8, chunks=()):
    query = normalize(query)
    explicit_query=focus_query(query)
    limit = max(0, min(int(limit), 20))
    if not query or not limit:
        return []
    by_id = {node["id"]: node for node in graph["nodes"]}
    focus = {node["id"] for node in graph["nodes"] if node.get("kind") == "knowledge" and contains_term(explicit_query, node["label"])}
    expansions = [phrase for term, (phrase, _) in ALIASES.items() if contains_term(explicit_query, term)]
    focus.update(node_id for term, (_, node_id) in ALIASES.items() if contains_term(explicit_query, term) and node_id in by_id)
    # Chinese labels often carry an English abbreviation; match their Chinese
    # portion too, without matching a single Chinese character.
    for node in graph["nodes"]:
        if node.get("kind") != "knowledge":
            continue
        for label_part in re.findall(r"[\u4e00-\u9fff]{2,}", node["label"]):
            if label_part in explicit_query:
                focus.add(node["id"])
    if 'munk_profile' in focus:
        focus.discard('sound_speed_profile')
    if any(term in query for term in ("munk 算例", "munk算例", "munk 示例", "munk示例")):
        focus.discard("munk_profile")
        focus.add("munk_case")
    context = set(focus)
    for edge in graph["edges"]:
        if edge["group"] == "related" and (edge["source"] in focus or edge["target"] in focus):
            context.update((edge["source"], edge["target"]))

    # A named surface model must not be answered by the similarly named sound
    # speed card. Only original snippets actually naming Cox–Munk can remain.
    cox_only=cox_munk_only(query)
    if cox_only:
        focus=set();context=set()
        # Keep whole-corpus IDF statistics; scoring only one/two retained pages
        # can make every shared word's BM25 IDF non-positive.
        documents=list(chunks)
    else:documents = list(cards) + list(chunks)
    focus_pages={(ref['source_id'],ref['pdf_page']) for node_id in focus for ref in by_id[node_id].get('references',[]) if ref.get('pdf_page') is not None}
    if not documents:
        return []
    expanded_texts, term_sets, scorer = _lexical_corpus(tuple(_raw_card_text(card, by_id.get(card.get("node_id"), {})) for card in documents))
    if scorer is None:
        return []
    query_terms = list(dict.fromkeys(tokenize(query + " " + " ".join(expansions))))
    if not query_terms:
        return []
    query_term_set = set(query_terms)
    scores = scorer.get_scores(query_terms)
    lexical_order = sorted((i for i, terms in enumerate(term_sets) if query_term_set.intersection(terms) and scores[i] > 0), key=lambda i: (-float(scores[i]), documents[i]["id"]))
    lexical_ranks = {index: rank for rank, index in enumerate(lexical_order, 1)}
    ranked = []
    for index, card in enumerate(documents):
        if cox_only and not re.search(COX_MUNK,normalize(card.get('text','')),re.I):continue
        node_ids = set(card.get("node_ids", [])) | {card.get("node_id")}
        focused = bool(focus.intersection(node_ids))
        adjacent = bool(context.intersection(node_ids)) and not focused
        is_excerpt = card.get("evidence_type") == "source_excerpt"
        # Keep precise concept questions within one hop. An explicitly linked
        # raw source must also match the question; a link is not relevance.
        lexical_rank = lexical_ranks.get(index)
        if is_excerpt and not lexical_rank:
            continue
        if is_excerpt and focus and (card.get('source_id'),card.get('pdf_page')) not in focus_pages:
            # Exact reviewed concepts use their reviewed source pages. A bare
            # surname/"profile" token elsewhere in a book is not this concept.
            continue
        if focus and not context.intersection(node_ids):
            # Unmapped document text can still answer a focused question when
            # the actual concept appears in the text, not just its source link.
            focus_terms = [term for term, (_, node_id) in ALIASES.items() if node_id in focus]
            focus_terms += [part for node_id in focus for part in re.findall(r"[\u4e00-\u9fff]{2,}|[a-z][a-z0-9_]{2,}", normalize(by_id[node_id]["label"]))]
            if not is_excerpt or not lexical_rank or not any(contains_term(expanded_texts[index], term) for term in focus_terms):
                continue
        if not lexical_rank and not focused and (not adjacent or is_excerpt):
            continue
        # An actually matched original excerpt should reach the answer context
        # ahead of a loosely related graph card. Exact reviewed concepts remain
        # first, preserving their assumptions and equation checks.
        source_prior=0.06 if is_excerpt and lexical_rank and not adjacent else 0
        # Multiple unreviewed excerpts from the same cited page can otherwise
        # crowd out the exact reviewed concept/assumptions card as books grow.
        # 0.12 exceeds the raw-text prior plus its maximum lexical contribution
        # (0.06 + 3/61); the priority therefore holds as the corpus grows.
        reviewed_focus_prior=0.12 if focused and not is_excerpt else 0
        fusion = (3 / (60 + lexical_rank) if lexical_rank else 0) + (0.25 if focused else 0.04 if adjacent else 0) + source_prior + reviewed_focus_prior
        ranked.append((fusion, focused, index, adjacent))
    ranked.sort(key=lambda item: (-item[0], not item[1], documents[item[2]]["id"]))
    result=[]
    for fusion, focused, index, adjacent in ranked[:limit]:
        card=deepcopy(documents[index])
        node_ids=set(card.get('node_ids',[]))|{card.get('node_id')}
        lexical_rank=lexical_ranks.get(index)
        card["retrieval"] = {"method": "bm25+curated-graph", "bm25_score": round(float(scores[index]), 6), "fusion_score": round(fusion, 6), "role": "question_focus" if focused else "graph_context" if adjacent else "text_match", "is_direct_evidence": bool(focused or (lexical_rank and not adjacent)), "support_status": "candidate_only", "claim_support_verified": False, "direct_match_note": "直接命中只表示检索相关，不表示已证明回答中的命题。"}
        card["evidence_type"] = card.get("evidence_type", "reviewed_course_card")
        card["citation"] = {"source_id": card.get("source_id"), "pdf_page": card.get("pdf_page"), "printed_page": card.get("printed_page"), "locator": card.get("locator", ""), "citation_id": card["id"]}
        node = by_id.get(card.get("node_id"), {})
        if node.get("misconception"):
            card["misconception"] = node["misconception"]
        card["related_triples"] = []
        for edge in graph["edges"]:
            if edge["group"] == "hierarchy" or not node_ids.intersection((edge["source"], edge["target"])):
                continue
            card["related_triples"].append({"source": by_id[edge["source"]]["label"], "relation": edge["label"], "target": by_id[edge["target"]]["label"], "relation_kind": edge["group"], "note": edge.get("note", ""), "provenance": "人工整理的课程关联或建议学习顺序；不能替代物理定律及原文证据。"})
        card["related_triples"] = card["related_triples"][:10]
        result.append(card)
    return result


GENERIC_PUBLIC_ANCHORS={'海洋','海水','水下','剖面','声速剖面','声速','温度','盐度','压力','深度','profile','profiles','sound','speed','海底','模型','传播','观测','ocean','marine','sea','water','underwater'}
PUBLIC_SOURCE_NAMES={'O-WOA':['World Ocean Atlas'],'O-WOD':['World Ocean Database']}


def focused_evidence(query,evidence,limit=8):
    """Select answer context; never pad an exact topic with generic matches."""
    cap=max(0,min(int(limit),20))
    if cox_munk_only(query):
        return [row for row in evidence if row.get('evidence_type') in {'source_excerpt','public_web_excerpt'} and re.search(COX_MUNK,normalize(row.get('text','')),re.I)][:cap]
    manual=lambda row:row.get('evidence_type') in {'reviewed_course_card','knowledge_card'}
    focused=[row for row in evidence if manual(row) and (row.get('retrieval',{}).get('role')=='question_focus' or row.get('retrieval',{}).get('focus') is True)]
    if not focused:return evidence[:cap]
    labels=normalize(' '.join(str(row.get(key) or '') for row in focused for key in ['label','text','formula']));question=normalize(query)
    pages={(ref['source_id'],ref['pdf_page']) for row in focused for ref in row.get('all_references',[]) if ref.get('pdf_page') is not None}
    public=[row for row in evidence if row.get('evidence_type') in {'public_web_excerpt','public_reference_guide'} and any(normalize(term) not in GENERIC_PUBLIC_ANCHORS and contains_term(question,term) and not contains_term(labels,term) for term in list(row.get('search_aliases',[]))+PUBLIC_SOURCE_NAMES.get(row.get('source_id'),[]))]
    raw=[row for row in evidence if row.get('evidence_type')=='source_excerpt' and (row.get('source_id'),row.get('pdf_page')) in pages]
    # Prefer one excerpt per cited page before taking another of that page.
    seen_pages=set();first=[];rest=[]
    for row in raw:
        page=(row['source_id'],row['pdf_page'])
        (rest if page in seen_pages else first).append(row);seen_pages.add(page)
    related=[row for row in evidence if manual(row) and row not in focused and row.get('retrieval',{}).get('role')=='graph_context']
    selected=focused+public[:2]+(first+rest)[:2]+related[:2]
    seen=set()
    return [row for row in selected if not(row['id'] in seen or seen.add(row['id']))][:cap]


def retrieve(graph, cards, query, limit=8, chunks=()):
    """Preserve precise queries; fuse bounded maintained paraphrase branches."""
    cap = max(0, min(int(limit), 20))
    plan = plan_query(query)
    if not plan['rule_ids']:
        return focused_evidence(query,_retrieve_single(graph, cards, query, max(cap,12), chunks),cap)
    rankings = [_retrieve_single(graph, cards, variant, max(cap, 12), chunks) for variant in plan['queries']]
    result = []
    for row, score in reciprocal_rank_fusion(rankings, cap, plan['target_node_ids']):
        row = deepcopy(row)
        row['retrieval'].update({'methods': ['BM25', 'typed_graph_context', 'maintained_query_rules', 'RRF'], 'rrf_score': score, 'query_rule_ids': plan['rule_ids'], 'query_variants': len(plan['queries'])})
        if row.get('node_id') in plan['target_node_ids']:
            row['retrieval'].update(role='question_focus', focus_origin='maintained_query_rule')
        result.append(row)
    return focused_evidence(query,result,cap)
