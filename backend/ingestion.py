"""Explicit, local-only document ingestion with page and revision provenance.

Usage: python backend/ingestion.py --manifest manifest.json
The manifest and generated chunks belong in .local and must not be committed.
PDF parsing reuses the already-installed pypdfium2/PDFium dependency. Scanned
pages are reported for OCR/manual review; this script does not invent text or
automatically extract unverified physical relations into the course graph.
"""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".local/kb/chunks.sqlite3"
INGESTION_VERSION = 2
TEXT_POLICY = 'unicode_display_preserved_search_nfkc_v2'


def clean_text(text):
    # Compatibility normalization destroys superscripts/subscripts (p² -> p2,
    # c₀ -> c0). Preserve text-layer Unicode for quotations and formula display.
    # PDF layout itself is not verified by this whitespace-only cleanup.
    text = str(text).replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()).strip()


def search_normalize(text):
    """Lossy compatibility normalization is exclusively a retrieval field."""
    return unicodedata.normalize('NFKC', str(text)).lower().strip()


def chunk_text(text, size=1100, overlap=160):
    """Prefer paragraph/sentence boundaries; overlap never crosses PDF pages."""
    if size < 200 or overlap < 0 or overlap >= size // 2:
        raise ValueError("分块尺寸至少 200 字符，重叠须小于尺寸的一半。")
    text = clean_text(text)
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = max(text.rfind(mark, start + size // 2, end) for mark in ("\n", "。", ". ", "; ", "；"))
            if boundary >= start + size // 2:
                end = boundary + 1
        piece = text[start:end].strip()
        if piece:
            left = start + len(text[start:end]) - len(text[start:end].lstrip())
            yield {"text": piece, "char_start": left, "char_end": left + len(piece)}
        if end == len(text):
            break
        start = max(end - overlap, start + 1)


def pages_from_source(path, selected_pages=None, metadata=None):
    path = Path(path)
    suffix = path.suffix.lower()
    metadata = metadata if metadata is not None else {}
    metadata.update({"type": suffix, "total_pages": None, "selected_pages": None})
    if suffix == ".pdf":
        import pypdfium2 as pdfium
        document = pdfium.PdfDocument(str(path))
        try:
            pages = list(dict.fromkeys(selected_pages)) if selected_pages is not None else list(range(1, len(document) + 1))
            for number in pages:
                if type(number) is not int or number < 1 or number > len(document):
                    raise ValueError("指定的 PDF 页码超出文档范围。")
            metadata.update({"total_pages": len(document), "selected_pages": len(pages)})
            for number in pages:
                page, text_page = None, None
                text = None
                try:
                    page = document[number - 1]
                    text_page = page.get_textpage()
                    text = text_page.get_text_range()
                except Exception:
                    # A page-level parse failure is recorded without returning
                    # parser messages that might contain private file paths.
                    metadata.setdefault("read_error_pages", []).append(number)
                finally:
                    if text_page is not None:text_page.close()
                    if page is not None:page.close()
                yield number, text
        finally:
            document.close()
    elif suffix == ".docx":
        if selected_pages:
            raise ValueError("DOCX 没有稳定页码，请使用段落定位或先导出 PDF。")
        with zipfile.ZipFile(path) as archive:
            document = ET.fromstring(archive.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        # Read only w:t elements, excluding XML metadata and instructions.
        text = "\n".join("".join(element.text or "" for element in paragraph.findall(".//w:t", ns)) for paragraph in document.findall(".//w:p", ns))
        yield None, text
    elif suffix in {".txt", ".md"}:
        if selected_pages:
            raise ValueError("文本文件没有 PDF 页码。")
        yield None, path.read_text(encoding="utf-8-sig")
    else:
        raise ValueError("当前支持 PDF、DOCX、UTF-8 TXT 和 Markdown。")


def file_revision(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def ingest_source(source, base_directory, size=1100, overlap=160, report=None):
    source_id = source.get("id", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", source_id):
        raise ValueError("来源编号只能包含字母、数字、下划线和短横线。")
    path = Path(source["path"])
    if not path.is_absolute():
        path = Path(base_directory) / path
    revision = file_revision(path)
    result, warnings, processed_pages, indexed_pages = [], [], set(), set()
    metadata, processed_units, indexed_units = {}, 0, 0
    for page_number, text in pages_from_source(path, source.get("pages"), metadata):
        processed_units+=1
        if page_number is not None:processed_pages.add(page_number)
        if text is None:
            warnings.append({"source_id": source_id, "pdf_page": page_number, "status": "needs_ocr_or_review", "category": "parse_error", "reason": "该页文本层读取失败；需重新解析或人工检查，尚未做 OCR。"})
            continue
        text = clean_text(text)
        count = len(re.sub(r"\s", "", text))
        if count < 35:
            warnings.append({"source_id": source_id, "pdf_page": page_number, "status": "needs_ocr_or_review", "category": "blank_or_short", "text_characters": count, "reason": "提取文字为空或过短；可能是封面/空白页，也可能为扫描内容，需查看原页，不能据此断言已识别。"})
            continue
        if text.count("�") > max(1, len(text) // 200):
            warnings.append({"source_id": source_id, "pdf_page": page_number, "status": "needs_ocr_or_review", "category": "unreadable_text", "text_characters": count, "reason": "文本含过多异常字符，未生成回答片段；公式或编码需人工检查，尚未做 OCR。"})
            continue
        indexed_units+=1
        if page_number is not None:indexed_pages.add(page_number)
        for number, piece in enumerate(chunk_text(text, size, overlap), 1):
            digest = hashlib.sha256((revision + str(page_number) + str(piece["char_start"]) + piece["text"]).encode()).hexdigest()[:14]
            locator = f"PDF 第 {page_number} 页" if page_number else f"段落片段 {number}，字符 {piece['char_start']}–{piece['char_end']}"
            node_ids = list(dict.fromkeys(source.get("page_nodes", {}).get(str(page_number), source.get("node_ids", []))))
            result.append({"id": f"D-{source_id}-{digest}", "label": source.get("title") or path.name, "text": piece["text"], "search_text": search_normalize(piece['text']), "ingestion_version": INGESTION_VERSION, "text_policy": TEXT_POLICY, "math_layout_verified": False, "source_id": source_id, "pdf_page": page_number, "printed_page": page_number - int(source["printed_page_offset"]) if page_number and "printed_page_offset" in source else None, "locator": locator, "node_id": node_ids[0] if node_ids else None, "node_ids": node_ids, "formula": "", "conditions": source.get("conditions") or "以下为原文片段；适用条件、单位及公式需结合原页和人工核查，不能据此补造结论。", "evidence_type": "source_excerpt", "verification_status": "source_text_unreviewed", "source_revision": revision, "char_start": piece["char_start"], "char_end": piece["char_end"], "offset_basis": "display_page_text_v2", "all_references": [{"source_id": source_id, "pdf_page": page_number, "locator": locator}]})
    if report is not None:
        total, selected = metadata.get('total_pages'), metadata.get('selected_pages')
        report.update({'source_id':source_id,'title':source.get('title') or path.name,'type':path.suffix.lower(),'source_revision':revision,'total_pages':total,'selected_pages':selected,'processed_pages':len(processed_pages),'indexed_pages':len(indexed_pages),'chunks':len(result),'processed_units':processed_units,'indexed_units':indexed_units,'failed_or_needs_ocr_pages':len(warnings),'blank_or_short_pages':sum(w.get('category')=='blank_or_short' for w in warnings),'unreadable_pages':sum(w.get('category') in {'unreadable_text','parse_error'} for w in warnings),'coverage_ratio':round(len(indexed_pages)/total,6) if total else None,'selected_success_ratio':round(len(indexed_pages)/selected,6) if selected else None,'full_document_selected':source.get('pages') is None})
    return result, warnings


def build_index(manifest, output=DEFAULT_OUTPUT, size=1100, overlap=160):
    manifest = Path(manifest)
    specification = json.loads(manifest.read_text(encoding="utf-8-sig"))
    chunks, warnings, seen, source_reports = [], [], set(), []
    for source in specification["sources"]:
        if source.get("id") in seen:
            raise ValueError("同一入库清单包含重复来源编号。")
        seen.add(source.get("id"))
        source_report={}
        values, issues = ingest_source(source, manifest.parent, size, overlap, source_report)
        chunks.extend(values)
        warnings.extend(issues)
        source_reports.append(source_report)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # An interrupted refresh must not corrupt the previously usable index.
    counts={field:sum(source.get(field) or 0 for source in source_reports) for field in ['total_pages','selected_pages','processed_pages','indexed_pages','failed_or_needs_ocr_pages','blank_or_short_pages','unreadable_pages','processed_units','indexed_units']}
    counts['coverage_ratio']=round(counts['indexed_pages']/counts['total_pages'],6) if counts['total_pages'] else None
    counts['selected_success_ratio']=round(counts['indexed_pages']/counts['selected_pages'],6) if counts['selected_pages'] else None
    report = {"ingestion_version": INGESTION_VERSION, "text_policy": TEXT_POLICY, "math_layout_verified": False, "sources": len(seen), "chunks": len(chunks), "warnings": warnings, "needs_ocr_pages": len(warnings), "source_coverage":source_reports,'coverage':counts, "source_revisions": sorted({chunk["source_revision"] for chunk in chunks}), "retrieval": "BM25 + 人工核实的课程图谱；未训练、未调用付费模型。"}
    with tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        if output.suffix in {".sqlite", ".sqlite3", ".db"}:
            with closing(sqlite3.connect(temporary)) as database:
                database.executescript("CREATE TABLE chunks(id TEXT PRIMARY KEY,source_id TEXT,pdf_page INTEGER,payload TEXT); CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);")
                database.executemany("INSERT INTO chunks VALUES(?,?,?,?)", [(chunk["id"], chunk["source_id"], chunk["pdf_page"], json.dumps(chunk, ensure_ascii=False)) for chunk in chunks])
                database.execute("INSERT INTO metadata VALUES('report',?)", (json.dumps(report, ensure_ascii=False),))
                database.commit()
        else:
            temporary.write_text("".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks), encoding="utf-8")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    report["index_revision"] = file_revision(output)
    output.with_suffix(".report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def course_manifest(graph, source_directory):
    """Build a private manifest for cited course pages, not whole textbooks."""
    sources = {}
    for node in graph["nodes"]:
        for reference in node.get("references", []):
            source_id, page = reference["source_id"], reference.get("pdf_page")
            source_path = Path(source_directory) / (source_id + ".pdf")
            if not page or not source_path.is_file():
                continue
            source = sources.setdefault(source_id, {"id": source_id, "path": str(source_path.resolve()), "title": source_id + " 课程原页", "pages": [], "page_nodes": {}})
            if page not in source["pages"]:
                source["pages"].append(page)
            source["page_nodes"].setdefault(str(page), []).append(node["id"])
    for source in sources.values():
        source["pages"].sort()
    return {"sources": list(sources.values())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="把授权的课程文件转成带页码和版本的本地检索片段。")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--size", type=int, default=1100)
    parser.add_argument("--overlap", type=int, default=160)
    args = parser.parse_args()
    print(json.dumps(build_index(args.manifest, args.output, args.size, args.overlap), ensure_ascii=False, indent=2))
