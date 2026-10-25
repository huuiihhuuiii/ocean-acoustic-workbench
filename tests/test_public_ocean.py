"""Public ocean provenance, bilingual search and bounded-refresh checks.

All network behavior is simulated. Committed NOAA snapshots are tested offline;
the tests neither fetch the web nor use a model key or private course material.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import knowledge
import public_ocean as ocean


BODY = "Ocean acidification reduces carbonate availability and affects calcifying organisms. " * 5
LEGACY = '<html><head><title>Ocean acidification</title></head><nav>Navigation noise</nav><div class="inner_content"><h1>Ocean acidification</h1><h2>Carbon dioxide changes seawater chemistry.</h2><div class="row"><div class="span8"><p>' + BODY + '</p><figure><img src="thirdparty.png"><figcaption>Third-party image caption</figcaption></figure><script>Instruction noise</script></div><div class="span3"><p>Sidebar noise</p></div></div></div><p><strong>Last updated:</strong> 09/23/26</p><footer>Footer noise</footer></html>'
MODERN = '<html><head><title>Ocean acidification</title></head><div class="container"><h1>Ocean acidification</h1><h2>Carbon dioxide changes seawater chemistry.</h2><div class="row"><div class="col-md-9"><p>' + BODY + '</p><div class="card"><p>Image caption in card</p></div></div><div class="col-md-3">Sidebar noise</div></div></div><h5><strong>Last updated:</strong></h5><h6>09/23/26</h6></html>'


def source():
    return {"id": "TEST-ACID", "url": "https://oceanservice.noaa.gov/facts/acidification.html", "title_zh": "海洋酸化", "organization": "NOAA", "search_aliases": ["海洋酸化", "酸化", "carbonate"], "guide_zh": "海洋吸收二氧化碳可影响碳酸盐体系。", "content_policy": "public_domain_text", "license": {"name": "Public domain", "url": "https://oceanservice.noaa.gov/about/faq.html"}, "ttl_hours": 168}


class Response:
    def __init__(self, status=200, headers=None, content=b"article"):
        self.status_code = status
        self.headers = headers or {"content-type": "text/html"}
        self.content = content
        self.encoding = "utf-8"
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def iter_bytes(self): yield self.content


class Client:
    def __init__(self, responses, **kwargs):
        self.responses = iter(responses)
        self.calls = []
        self.options = kwargs
        self.cookies = {"not_forwarded": "cookie"}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def stream(self, method, url, **kwargs):
        self.calls.append((method, url, dict(self.cookies), kwargs))
        return next(self.responses)


class PublicOceanTests(unittest.TestCase):
    def test_known_noaa_layouts_exclude_navigation_images_and_sidebar(self):
        for html in [LEGACY, MODERN]:
            document = ocean.extract_noaa_fact(html)
            self.assertIn("carbonate availability", document["text"])
            self.assertEqual(document["source_updated_at"], "2026-09-23")
            for noise in ["Navigation noise", "Sidebar noise", "Footer noise", "image caption", "Instruction noise"]:
                self.assertNotIn(noise.lower(), document["text"].lower())
        external = '<html><title>Coral reefs</title><div class="inner_content"><h1>Coral reefs</h1><h2>Climate impacts coral.</h2></div><div class="span8"><p>' + BODY + '</p></div></html>'
        self.assertIn("carbonate availability", ocean.extract_noaa_fact(external)["text"])
        with self.assertRaisesRegex(ValueError, "source_not_found"):
            ocean.extract_noaa_fact('<html><title>Page Not Found: Error 404</title></html>')

    def test_redirects_require_an_explicit_registered_https_destination(self):
        row = source(); clients = []
        def factory(**kwargs):
            client = Client([Response(302, {"location": "https://127.0.0.1/admin"})], **kwargs)
            clients.append(client); return client
        with self.assertRaisesRegex(ValueError, "redirect_host_not_allowed"):
            ocean.fetch_source(row, client_factory=factory)
        self.assertEqual(len(clients[0].calls), 1)
        self.assertFalse(clients[0].options["follow_redirects"])
        self.assertFalse(clients[0].options["trust_env"])
        self.assertEqual(clients[0].calls[0][2], {})
        self.assertNotIn("Authorization", clients[0].options["headers"])
        with self.assertRaisesRegex(ValueError, "redirect_url_not_registered"):
            ocean.validate_url("https://oceanservice.noaa.gov/arbitrary?token=abc", row)
        with self.assertRaisesRegex(ValueError, "unsafe_source_url"):
            ocean.validate_url("http://oceanservice.noaa.gov/facts/acidification.html", row)

    def test_stream_size_and_total_timeout_are_bounded(self):
        with self.assertRaisesRegex(ValueError, "source_too_large"):
            ocean.fetch_source(source(), max_bytes=4, client_factory=lambda **kw: Client([Response(content=b"12345")], **kw))
        with patch.object(ocean.time, "monotonic", side_effect=[0, 21]):
            with self.assertRaisesRegex(TimeoutError, "source_timeout"):
                ocean.fetch_source(source(), timeout_seconds=20, client_factory=lambda **kw: Client([], **kw))
        closed = threading.Event()
        class SlowResponse(Response):
            def iter_bytes(self):
                closed.wait(1)
                raise RuntimeError("stream closed")
                yield b""
        class SlowClient(Client):
            def close(self): closed.set()
        started = time.monotonic()
        with self.assertRaisesRegex(TimeoutError, "source_timeout"):
            ocean.fetch_source(source(), timeout_seconds=.03, client_factory=lambda **kw: SlowClient([SlowResponse()], **kw))
        self.assertTrue(closed.is_set())
        self.assertLess(time.monotonic() - started, .5)

    def test_failure_preserves_last_good_snapshot_without_raw_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp); registry = tmp / "sources.json"; chunks = tmp / "chunks.json"; cache = tmp / "cache"
            ocean.atomic_json(registry, {"sources": [source()]}); ocean.atomic_json(chunks, [])
            fetched = {"raw": LEGACY.encode(), "html": LEGACY, "resolved_url": source()["url"]}
            first = ocean.refresh_sources(registry=registry, chunks=chunks, cache_root=cache, force=True, fetcher=lambda row: fetched)
            self.assertEqual(first["documents_with_text"], 1)
            before_registry, before = ocean.load_public_data(registry, chunks, cache)
            def failure(row): raise RuntimeError("sensitive raw exception secret=not-for-public")
            report = ocean.refresh_sources(registry=registry, chunks=chunks, cache_root=cache, force=True, fetcher=failure)
            after_registry, after = ocean.load_public_data(registry, chunks, cache)
            self.assertEqual(before, after)
            self.assertEqual(before_registry["sources"][0]["fetched_at"], after_registry["sources"][0]["fetched_at"])
            self.assertTrue(report["failed"][0]["last_good_preserved"])
            self.assertNotIn("sensitive", json.dumps(report))
            self.assertEqual(after_registry["sources"][0]["snapshot_status"], "last_good_snapshot")
            self.assertFalse((tmp / "chunks.sqlite3").exists())

    def test_chunk_character_offsets_reproduce_the_clean_source_excerpt(self):
        text = "Heading\n\n" + BODY * 20
        chunks = ocean.make_chunks(source(), text)
        for chunk in chunks:
            self.assertEqual(text[chunk["char_start"]:chunk["char_end"]], chunk["text"])

    def test_expiry_uses_fetch_time_not_source_update_and_hook_skips_fresh(self):
        now = datetime(2026, 10, 13, tzinfo=timezone.utc)
        row = {**source(), "fetched_at": (now - timedelta(hours=24)).isoformat(), "source_updated_at": "1999-01-01"}
        self.assertFalse(ocean.is_stale(row, now))
        self.assertTrue(ocean.is_stale(row, now, ttl_hours=12))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            ocean.atomic_json(path / "sources.json", {"sources": [{**row, "fetched_at": ocean.utc_now()}]})
            ocean.atomic_json(path / "chunks.json", [])
            with patch.object(ocean, "fetch_source", side_effect=AssertionError("fresh sources cannot make requests")):
                result = ocean.refresh_if_stale(registry=path / "sources.json", chunks=path / "chunks.json", cache_root=path / "cache")
            self.assertFalse(result["scheduled"])

    def test_committed_bilingual_documents_have_real_provenance(self):
        registry = ocean.read_json(ocean.REGISTRY, {}); chunks = ocean.read_json(ocean.CHUNKS, [])
        status = ocean.public_ocean_status(registry, chunks)
        self.assertGreaterEqual(status["successful_web_documents"], 20)
        self.assertFalse(status["realtime_observations_connected"])
        expected = {"海洋酸化为什么影响碳酸盐": "O-NOAA-ACIDIFICATION", "珊瑚白化能恢复吗": "O-NOAA-CORAL-BLEACH", "全球海平面和相对海平面有什么区别": "O-NOAA-SEALEVEL-GLOBAL-LOCAL", "海流受什么驱动": "O-NOAA-CURRENT", "漂流浮标怎么监测海流": "O-NOAA-CURRENTMON", "海啸传播速度与水深有什么关系": "O-NOAA-TSUNAMI", "Argo 数据质控如何选择延时模式": "O-ARGO-QC"}
        for query, source_id in expected.items():
            results = ocean.retrieve_public_ocean(query, 8, registry, chunks)
            self.assertIn(source_id, {row["source_id"] for row in results}, query)
            for row in results:
                self.assertIsNone(row["pdf_page"])
                self.assertTrue(row["citation"]["url"].startswith("https://"))
                self.assertTrue(row["snapshot_not_realtime"])
        self.assertEqual(ocean.retrieve_public_ocean("世界杯足球冠军", 8, registry, chunks), [])
        for row in registry["sources"]:
            if row.get("snapshot_status") == "ingested":
                self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
                self.assertTrue(row["fetched_at"])
                self.assertTrue(row["license"]["url"])
                self.assertTrue(row["source_updated_at"])

    def test_shared_knowledge_citations_use_web_urls_and_preserve_course_counts(self):
        evidence = ocean.retrieve_public_ocean("海洋酸化", 2)
        citations = knowledge.citations_for(evidence)
        self.assertTrue(all(c["url"].startswith("https://oceanservice.noaa.gov/") for c in citations))
        self.assertTrue(all(c["pdf_page"] is None for c in citations))
        self.assertIn("不能提供或编造", knowledge.answer_context(evidence))
        with patch.object(knowledge, "CHUNKS", Path("__missing_course_index__")):
            status = knowledge.retrieval_status()
            self.assertEqual(status["indexed_pages"], 0)
            self.assertEqual(status["source_documents"], 0)
            self.assertGreaterEqual(status["public_ocean"]["successful_web_documents"], 20)
            self.assertTrue(any(row["source_id"] == "O-NOAA-ACIDIFICATION" for row in knowledge.retrieve("海洋酸化")))
        generic = {"id": "GENERIC", "source_id": "COURSE", "text": "Marine background", "retrieval": {"role": "text_match"}}
        with patch.object(knowledge.retrieval, "retrieve", return_value=[generic]):
            self.assertEqual(knowledge.retrieve("海洋酸化",1)[0]["source_id"], "O-NOAA-ACIDIFICATION")


if __name__ == "__main__": unittest.main()
