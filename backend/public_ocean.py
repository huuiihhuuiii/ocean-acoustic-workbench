"""Allow-listed public ocean documents, reproducible snapshots and offline RAG.

NOAA body text follows NOAA's published public-domain policy. Other registered
sites contribute a project-written short guide and a link, not copied full text.
Search/status are offline; refresh runs separately and never opens arbitrary URLs.
The private course SQLite index is never read or overwritten by the collector.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import threading
import time
from urllib.parse import urljoin, urlsplit

from vendor.rank_bm25 import BM25Okapi
from retrieval import contains_term, normalize, tokenize

NODE_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = NODE_ROOT.parent / "ocean-acoustic-public" / "data"
REGISTRY = DATA_ROOT / "open-ocean-sources.json"
CHUNKS = DATA_ROOT / "open-ocean-chunks.json"
CACHE_ROOT = NODE_ROOT / ".local" / "kb" / "open-ocean"
ALLOWED_HOSTS = frozenset({
    "oceanservice.noaa.gov", "www.ncei.noaa.gov", "www.ndbc.noaa.gov",
    "ioos.noaa.gov", "www.pmel.noaa.gov", "oceanexplorer.noaa.gov",
    "tidesandcurrents.noaa.gov", "www.fisheries.noaa.gov", "www.teos-10.org",
    "argo.ucsd.edu", "www.oceannetworks.ca", "www.ioc.unesco.org",
    "www.go-ship.org", "dosits.org", "www.whoi.edu", "www.jamstec.go.jp",
})
_refresh_lock = threading.Lock()
_state_lock = threading.Lock()
_refresh_state = {"running": False, "last_started_at": None, "last_finished_at": None, "last_report": None}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


class Element:
    def __init__(self, tag="root", attrs=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.children = []


class HTMLTree(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Element(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Element(tag, attrs))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def walk(node):
    if isinstance(node, Element):
        yield node
        for child in node.children:
            yield from walk(child)


SKIP_TAGS = {"nav", "header", "footer", "aside", "form", "script", "style", "noscript", "svg", "figure", "figcaption", "video", "audio", "iframe", "button"}
BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "div", "section", "article", "br", "hr"}


def clean_text(node):
    if isinstance(node, str):
        return node
    if node.tag in SKIP_TAGS or node.attrs.get("aria-hidden") == "true":
        return ""
    classes = set(node.attrs.get("class", "").split())
    if classes & {"breadcrumbs", "sidebarLinks", "social", "sr-only", "navbar", "related-posts", "wp-block-embed", "card", "signatureblock"}:
        return ""
    value = "".join(clean_text(child) for child in node.children)
    return "\n" + value + "\n" if node.tag in BLOCK_TAGS else value


def normalized_lines(text):
    return "\n\n".join(line for line in (re.sub(r"\s+", " ", line).strip() for line in text.splitlines()) if line)


def extract_noaa_fact(raw_html):
    """Require the known NOAA NOS content container; fail closed on redesigns.

    Extract the question, one-line answer and main article column only. All
    pictures/video/captions, social/navigation/sidebar/contact material is omitted.
    Reject NOAA's soft-404 pages even when the HTTP status is 200.
    """
    tree = HTMLTree(); tree.feed(raw_html)
    title_node = next((node for node in walk(tree.root) if node.tag == "title"), None)
    document_title = normalized_lines(clean_text(title_node)) if title_node else ""
    if re.search(r"page not found|error\s*404|access denied", document_title, re.I):
        raise ValueError("source_not_found")
    root = next((node for node in walk(tree.root) if "inner_content" in node.attrs.get("class", "").split()), None)
    # NOAA NOS currently serves two layouts. The newer Bootstrap article has
    # direct h1/h2 children in a container and a col-md-9 content column.
    if root is None:
        root = next((node for node in walk(tree.root) if "container" in node.attrs.get("class", "").split() and any(isinstance(child, Element) and child.tag == "h1" for child in node.children)), None)
    if root is None:
        raise ValueError("unsupported_page_layout")
    headings = [node for node in root.children if isinstance(node, Element) and node.tag in {"h1", "h2"}]
    column = next((node for node in walk(root) if set(node.attrs.get("class", "").split()) & {"span8", "col-md-9"}), None)
    if column is None:
        # The coral/climate infographic page closes inner_content before its
        # body row. Accept that known layout only when exactly one article-sized
        # div exists in the document; do not fall back to scraping the whole body.
        columns = [node for node in walk(tree.root) if node.tag == "div" and set(node.attrs.get("class", "").split()) & {"span8", "col-md-9"}]
        if len(columns) == 1:
            column = columns[0]
    if column is None:
        raise ValueError("unsupported_page_layout")
    text = normalized_lines("\n".join(clean_text(node) for node in [*headings, column]))
    # Embed-player fallbacks and download prompts are not scientific evidence.
    text = "\n\n".join(part for part in text.split("\n\n") if not re.search(r"browser.*support HTML5|direct link to the video|^VIDEO:|^Download this|^Watch our|^Click on graphic", part, re.I))
    if len(text) < 100:
        raise ValueError("too_little_article_text")
    updated = re.search(r"Last updated:(?:\s|<[^>]+>)*(\d{2}/\d{2}/\d{2}(?:\d{2})?)", raw_html, re.I)
    source_updated_at = None
    if updated:
        source_updated_at = datetime.strptime(updated.group(1), "%m/%d/%y" if len(updated.group(1)) == 8 else "%m/%d/%Y").date().isoformat()
    return {"title": normalized_lines(clean_text(headings[0])) if headings else document_title, "text": text, "source_updated_at": source_updated_at}


def validate_url(url, source):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("unsafe_source_url")
    if parsed.hostname not in ALLOWED_HOSTS or parsed.hostname not in source.get("allowed_hosts", [urlsplit(source["url"]).hostname]):
        raise ValueError("redirect_host_not_allowed")
    # A registry entry must approve each redirect destination explicitly. An
    # official host alone does not authorize scraping an arbitrary path/query.
    if url not in source.get("allowed_urls", [source["url"]]):
        raise ValueError("redirect_url_not_registered")
    if parsed.fragment:
        raise ValueError("source_fragment_not_allowed")
    return url


def fetch_source(source, *, client_factory=None, max_bytes=2_000_000, timeout_seconds=20):
    """No keys, cookies, environment proxy or automatic redirects are sent."""
    if client_factory is None:
        import httpx
        client_factory = httpx.Client
    url = validate_url(source["url"], source)
    started = time.monotonic()
    # One isolated client per source; registry data cannot provide request headers.
    with client_factory(timeout=timeout_seconds, follow_redirects=False, trust_env=False, headers={"User-Agent": "OceanAcousticCoursework/0.6 (public text educational indexing)", "Accept": "text/html"}) as client:
        expired = threading.Event()
        def expire():
            expired.set()
            try:
                close = getattr(client, "close", None)
                if close:
                    close()
            except Exception:
                pass
        # HTTPX read timeout is per read. A separate deadline closes a slow
        # stream even if the server keeps trickling smaller blocks indefinitely.
        watchdog = threading.Timer(timeout_seconds, expire)
        watchdog.daemon = True; watchdog.start()
        try:
            for _ in range(4):
                remaining = timeout_seconds - (time.monotonic() - started)
                if remaining <= 0 or expired.is_set():
                    raise TimeoutError("source_timeout")
                # A server-set cookie from a previous redirect is never forwarded.
                if hasattr(client, "cookies"):
                    client.cookies.clear()
                with client.stream("GET", url, timeout=remaining) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        url = validate_url(urljoin(url, response.headers.get("location", "")), source)
                        continue
                    if response.status_code != 200:
                        raise ValueError("source_http_" + str(response.status_code))
                    if "html" not in response.headers.get("content-type", "").lower():
                        raise ValueError("unsupported_content_type")
                    declared = response.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > max_bytes:
                        raise ValueError("source_too_large")
                    body = bytearray()
                    for block in response.iter_bytes():
                        if expired.is_set() or time.monotonic() - started > timeout_seconds:
                            raise TimeoutError("source_timeout")
                        body.extend(block)
                        if len(body) > max_bytes:
                            raise ValueError("source_too_large")
                    encoding = getattr(response, "encoding", None) or "utf-8"
                    return {"raw": bytes(body), "html": bytes(body).decode(encoding, errors="replace"), "resolved_url": url, "http_last_modified": response.headers.get("last-modified"), "etag": response.headers.get("etag")}
            raise ValueError("too_many_redirects")
        except Exception:
            if expired.is_set():
                raise TimeoutError("source_timeout") from None
            raise
        finally:
            watchdog.cancel()


def split_text(text, maximum=1300, overlap=180):
    parts = []; start = 0
    while start < len(text):
        end = min(start + maximum, len(text))
        if end < len(text):
            boundary = text.rfind("\n\n", start + maximum // 2, end)
            if boundary > start:
                end = boundary
        piece = text[start:end]
        left = len(piece) - len(piece.lstrip())
        right = len(piece) - len(piece.rstrip())
        parts.append((start + left, end - right, piece.strip()))
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
    return parts


def make_chunks(source, text):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    kind = "public_web_excerpt" if source["content_policy"] == "public_domain_text" else "public_reference_guide"
    result = []
    for ordinal, (start, end, excerpt) in enumerate(split_text(text), 1):
        result.append({"id": f"{source['id']}-{digest[:12]}-{ordinal:03}", "source_id": source["id"], "label": source["title_zh"], "text": excerpt, "evidence_type": kind, "verification_status": "official_source_snapshot" if kind == "public_web_excerpt" else "project_written_reference_guide", "pdf_page": None, "url": source["url"], "organization": source["organization"], "title": source.get("title", source["title_zh"]), "title_zh": source["title_zh"], "guide_zh": source.get("guide_zh", ""), "search_aliases": source.get("search_aliases", []), "topics": source.get("topics", []), "fetched_at": source.get("fetched_at"), "source_updated_at": source.get("source_updated_at"), "sha256": source.get("sha256"), "text_sha256": digest, "char_start": start, "char_end": end, "license": source["license"], "snapshot_status": source.get("snapshot_status", "ingested"), "snapshot_not_realtime": True, "temporal_note": source.get("temporal_note", "公开页面快照；其中历史示例、典型值、预测值不是当前实测数据。"), "conditions": "正文依据所列公开页面；中文标题、关键词和导读由课程项目整理，不是官方译文。"})
    return result


def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def is_stale(source, now=None, ttl_hours=None):
    now = now or datetime.now(timezone.utc)
    fetched = parse_date(source.get("fetched_at"))
    hours = ttl_hours if ttl_hours is not None else source.get("ttl_hours", 168)
    return fetched is None or now - fetched > timedelta(hours=hours)


@lru_cache(maxsize=6)
def _read_json(filename, mtime, size):
    return json.loads(Path(filename).read_text(encoding="utf-8"))


def read_json(path, fallback):
    path = Path(path)
    if not path.is_file():
        return deepcopy(fallback)
    stat = path.stat()
    return deepcopy(_read_json(str(path), stat.st_mtime_ns, stat.st_size))


def load_public_data(registry=REGISTRY, chunks=CHUNKS, cache_root=CACHE_ROOT):
    base = read_json(registry, {"schema_version": 1, "sources": []})
    values = read_json(chunks, [])
    # A single cache bundle is atomically swapped; source metadata and chunks
    # therefore cannot come from different refresh generations.
    cache = read_json(Path(cache_root) / "snapshot.json", {})
    if cache.get("registry") and cache.get("chunks") is not None:
        approved = {source["id"]: source for source in base.get("sources", [])}
        cached = {source["id"]: source for source in cache["registry"].get("sources", [])}
        effective = []
        cached_ids = set()
        for source_id, source in approved.items():
            candidate = cached.get(source_id)
            if candidate and candidate.get("url") == source.get("url") and candidate.get("content_policy") == source.get("content_policy"):
                merged = {**source, **candidate}
                # Refresh metadata may supersede old metadata, but local cache
                # contents cannot widen the committed allow-list or permissions.
                for field in ["url", "allowed_urls", "allowed_hosts", "content_policy", "license", "ttl_hours", "search_aliases", "guide_zh", "guide_kind", "topics"]:
                    if field in source:
                        merged[field] = deepcopy(source[field])
                effective.append(merged); cached_ids.add(source_id)
            else:
                effective.append(source)
        base = {**base, "sources": effective, "refreshed_at": cache.get("refreshed_at")}
        values = [row for row in values if row["source_id"] not in cached_ids] + [row for row in cache["chunks"] if row["source_id"] in cached_ids]
    return base, values


def refresh_sources(*, registry=REGISTRY, chunks=CHUNKS, cache_root=CACHE_ROOT, ttl_hours=None, force=False, source_ids=None, publish=False, fetcher=fetch_source):
    """Refresh approved document entries, preserving every last-good snapshot."""
    if not _refresh_lock.acquire(blocking=False):
        return {"running": True, "reason": "refresh_already_running"}
    try:
        with _state_lock:
            _refresh_state.update(running=True, last_started_at=utc_now())
        current, old_chunks = load_public_data(registry, chunks, cache_root)
        rows = deepcopy(current.get("sources", [])); by_source = {}
        for chunk in old_chunks:
            by_source.setdefault(chunk["source_id"], []).append(chunk)
        ids = set(source_ids or []); report = {"started_at": utc_now(), "refreshed": [], "failed": [], "skipped": []}
        targets = [row for row in rows if row.get("content_policy") == "public_domain_text" and (not ids or row["id"] in ids) and (force or is_stale(row, ttl_hours=ttl_hours))]
        def collect(row):
            fetched = utc_now()
            try:
                response = fetcher(row)
                document = extract_noaa_fact(response["html"])
                update = {**row, "title": document["title"], "fetched_at": fetched, "checked_at": fetched, "source_updated_at": document["source_updated_at"], "source_updated_at_kind": "page_last_updated" if document["source_updated_at"] else "not_provided", "resolved_url": response["resolved_url"], "http_last_modified": response.get("http_last_modified"), "etag": response.get("etag"), "sha256": hashlib.sha256(response["raw"]).hexdigest(), "text_sha256": hashlib.sha256(document["text"].encode()).hexdigest(), "snapshot_status": "ingested", "original_source_verified": True, "last_fetch_error": None}
                return row["id"], update, make_chunks(update, document["text"]), None
            except Exception as error:
                # Never copy raw network exceptions/URLs/headers into public status.
                allowed = {"source_not_found", "unsupported_page_layout", "too_little_article_text", "unsafe_source_url", "redirect_host_not_allowed", "redirect_url_not_registered", "source_fragment_not_allowed", "unsupported_content_type", "source_too_large", "too_many_redirects", "source_timeout"}
                message = str(error)
                category = message if message in allowed or re.fullmatch(r"source_http_\d{3}", message) else "source_fetch_failed"
                return row["id"], {**row, "checked_at": fetched, "snapshot_status": "last_good_snapshot" if by_source.get(row["id"]) else "fetch_failed", "last_fetch_error": category}, None, category
        # A bounded maintenance pool avoids one slow site delaying all sources.
        with ThreadPoolExecutor(max_workers=3) as pool:
            updates = list(pool.map(collect, targets))
        update_map = {}
        for source_id, row, content, failure in updates:
            update_map[source_id] = row
            if content is not None:
                by_source[source_id] = content; report["refreshed"].append(source_id)
            else:
                report["failed"].append({"source_id": source_id, "error": failure, "last_good_preserved": bool(by_source.get(source_id))})
        rows = [update_map.get(row["id"], row) for row in rows]
        report["skipped"] = [row["id"] for row in rows if row["id"] not in update_map]
        new_chunks = [chunk for row in rows for chunk in by_source.get(row["id"], [])]
        refreshed_at = utc_now(); current.update(sources=rows, refreshed_at=refreshed_at)
        report.update(finished_at=refreshed_at, documents_with_text=sum(bool(by_source.get(row["id"])) and row.get("content_policy") == "public_domain_text" for row in rows), chunks=len(new_chunks))
        # The private course db and files are outside this independent cache root.
        atomic_json(Path(cache_root) / "snapshot.json", {"registry": current, "chunks": new_chunks, "refreshed_at": refreshed_at, "report": report})
        if publish:
            atomic_json(registry, current); atomic_json(chunks, new_chunks)
        with _state_lock:
            _refresh_state.update(running=False, last_finished_at=refreshed_at, last_report=report)
        return report
    finally:
        with _state_lock:
            _refresh_state["running"] = False
        _refresh_lock.release()


def refresh_if_stale(ttl_hours=168, background=True, **kwargs):
    """Nonblocking startup/on-demand hook. Search and status never call this."""
    registry, _ = load_public_data(kwargs.get("registry", REGISTRY), kwargs.get("chunks", CHUNKS), kwargs.get("cache_root", CACHE_ROOT))
    due = [row["id"] for row in registry.get("sources", []) if row.get("content_policy") == "public_domain_text" and is_stale(row, ttl_hours=ttl_hours)]
    with _state_lock:
        running = _refresh_state["running"]
    if running or not due:
        return {"scheduled": False, "running": running, "stale_sources": len(due)}
    if not background:
        return refresh_sources(ttl_hours=ttl_hours, source_ids=due, **kwargs)
    # The refresh function owns the lock. Competing hooks may create a short-lived
    # daemon, but only one performs I/O; all others immediately return.
    threading.Thread(target=refresh_sources, kwargs={"ttl_hours": ttl_hours, "source_ids": due, **kwargs}, name="public-ocean-refresh", daemon=True).start()
    return {"scheduled": True, "running": True, "stale_sources": len(due)}


def public_ocean_status(registry=None, chunks=None, now=None):
    if registry is None or chunks is None:
        registry, chunks = load_public_data()
    sources = registry.get("sources", []) if isinstance(registry, dict) else registry
    now = now or datetime.now(timezone.utc); ids = {chunk["source_id"] for chunk in chunks}
    web_sources = [{key: row.get(key) for key in ["id", "organization", "title", "title_zh", "guide_zh", "url", "content_policy", "topics", "source_updated_at", "source_updated_at_kind", "fetched_at", "checked_at", "sha256", "hash_kind", "guide_sha256", "text_sha256", "license", "snapshot_status", "original_source_verified", "last_fetch_error", "temporal_note", "ttl_hours"]} | {"stale": is_stale(row, now), "chunks": sum(chunk["source_id"] == row["id"] for chunk in chunks)} for row in sources]
    times = [row["fetched_at"] for row in sources if row.get("fetched_at")]
    with _state_lock:
        refresh = deepcopy(_refresh_state)
    return {"mode": "public_ocean_document_rag", "registered_sources": len(sources), "indexed_sources": len(ids), "successful_web_documents": sum(row["id"] in ids and row.get("content_policy") == "public_domain_text" for row in sources), "reference_guides": sum(row["id"] in ids and row.get("content_policy") == "original_project_summary" for row in sources), "data_service_entries": sum(row.get("content_policy") == "metadata_only" for row in sources), "chunks": len(chunks), "latest_fetched_at": max(times, default=None), "oldest_fetched_at": min(times, default=None), "stale_sources": sum(row["stale"] for row in web_sources if row["content_policy"] == "public_domain_text"), "methods": ["BM25", "editorial_bilingual_topic_aliases"], "web_sources": web_sources, "refresh": refresh, "realtime_observations_connected": False, "live_web_search": False, "training_performed": False, "note": "官方知识网页正文快照 + 项目自写参考导读；公开网页数量与课程 PDF 页数分别统计。刷新页面不代表获取最新观测值；当前没有接入实时海况数据接口。"}


@lru_cache(maxsize=2)
def _public_index(payload):
    chunks = json.loads(payload)
    texts = [normalize(" ".join([row["text"], row.get("title", ""), row.get("title_zh", ""), row.get("guide_zh", ""), *row.get("search_aliases", [])])) for row in chunks]
    tokens = [tokenize(text) for text in texts]
    return chunks, texts, BM25Okapi(tokens) if tokens else None


def retrieve_public_ocean(query, limit=6, registry=None, chunks=None):
    if registry is None or chunks is None:
        registry, chunks = load_public_data()
    if not chunks or int(limit) <= 0:
        return []
    rows, texts, model = _public_index(json.dumps(chunks, ensure_ascii=False, sort_keys=True))
    query = normalize(query); terms = tokenize(query)
    if not terms:
        return []
    scores = model.get_scores(terms)
    ranked = []
    for index, (row, text) in enumerate(zip(rows, texts)):
        matches = [term for term in terms if contains_term(text, term)]
        aliases = [term for term in row.get("search_aliases", []) if contains_term(query, term)]
        # Unknown questions stay empty instead of returning weak generic metadata.
        if not matches or not (aliases or any(len(term) >= 4 and term.isascii() for term in matches) or len(set(matches)) >= 2):
            continue
        score = max(float(scores[index]), 0.0) + 2 * len(aliases)
        ranked.append((score, index))
    ranked.sort(key=lambda item: (-item[0], rows[item[1]]["id"]))
    chosen = []; per_source = {}
    for score, index in ranked:
        row = rows[index]; source_id = row["source_id"]
        if per_source.get(source_id, 0) >= 2:
            continue
        evidence = deepcopy(row)
        label = "项目自写导读" if row["evidence_type"] == "public_reference_guide" else "公开网页快照"
        evidence.update(retrieval={"method": "bm25+editorial-bilingual-aliases", "role": "public_document", "score": round(score, 7), "snapshot_not_realtime": True}, all_references=[{"source_id": source_id, "url": row["url"], "locator": f"{label}，正文字符 {row['char_start']}–{row['char_end']}"}], citation={"source_id": source_id, "url": row["url"], "title": row.get("title"), "organization": row.get("organization"), "fetched_at": row.get("fetched_at"), "source_updated_at": row.get("source_updated_at"), "sha256": row.get("sha256"), "text_sha256": row.get("text_sha256"), "license": row.get("license"), "snapshot_not_realtime": True})
        chosen.append(evidence); per_source[source_id] = per_source.get(source_id, 0) + 1
        if len(chosen) >= min(int(limit), 20):
            break
    return chosen


def main():
    parser = argparse.ArgumentParser(description="Refresh allow-listed public ocean knowledge; never overwrites the private course index.")
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--chunks", type=Path, default=CHUNKS)
    parser.add_argument("--cache-root", type=Path, default=CACHE_ROOT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--publish", action="store_true", help="Export refreshed public-domain text snapshots to the public JSON bundle.")
    parser.add_argument("--ttl-hours", type=float, default=168)
    parser.add_argument("--source", action="append", dest="source_ids")
    args = parser.parse_args()
    print(json.dumps(refresh_sources(**vars(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
