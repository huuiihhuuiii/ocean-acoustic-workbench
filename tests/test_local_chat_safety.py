"""Exercise the real chat endpoint body with isolated storage and fake HTTP.

Importing app.py starts a worker and updates its configured job database. This
test compiles only the Chat schema and chat function from that source file,
without importing the application's startup, touching production jobs, or
making any provider request. Dependencies and evidence are explicit fixtures.
"""
import ast
import copy
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing, contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import answer_policy, context_budget
import knowledge as course_knowledge

TEST_KEY = "TEST-ONLY-NOT-A-REAL-API-KEY"
EVIDENCE = [{"id": "TEST-CARD", "text": "测试课程依据", "source_id": "TEST",
             "formula": "", "conditions": "仅为离线测试夹具", "locator": "test-fixture"}]


class LocalChatSafety(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.database = self.root / "messages.sqlite3"
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY, session TEXT, role TEXT, text TEXT, created TEXT, metadata TEXT DEFAULT '{}')")
            connection.commit()
        self.connection_config = {"provider": "Qwen", "model": "qwen-test", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "api_key": ""}
        self.evidence = copy.deepcopy(EVIDENCE)
        tree = ast.parse((ROOT / "backend/app.py").read_text(encoding="utf-8-sig"))
        definitions = []
        for item in tree.body:
            if isinstance(item, (ast.ClassDef, ast.AsyncFunctionDef)) and item.name in ("Chat", "chat"):
                item = copy.deepcopy(item)
                item.decorator_list = []
                definitions.append(item)
        self.assertEqual(len(definitions), 2)
        self.namespace = {
            "__name__": "isolated_chat_endpoint", "BaseModel": BaseModel, "Field": Field, "field_validator": field_validator,
            "Literal": Literal, "HTTPException": HTTPException, "httpx": httpx,
            "json": json, "config": lambda: dict(self.connection_config),
            "connect": self.connect_database, "stamp": lambda: "test-time",
            "search": lambda message: copy.deepcopy(self.evidence), "history": lambda session: [],
            "kbfile": lambda name: self.root / name, "answer_policy": answer_policy, "context_budget": context_budget,
            "knowledge": SimpleNamespace(answer_context=lambda evidence: "test evidence only",
                                         format_no_model_answer=course_knowledge.format_no_model_answer,
                                         citations_for=lambda evidence: [{"id": e["id"]} for e in evidence],
                                         retrieval_status=lambda: {"scope": "test-fixtures"}),
            "models": SimpleNamespace(catalog=lambda: {"providers": [{"id": "Qwen", "base_url": self.connection_config["base_url"]}],
                                                       "models": [{"provider": "Qwen", "id": "qwen-test"}]},
                                      validate_endpoint=lambda provider, url: None,
                                      chat_payload=lambda cfg, messages, tools: {"model": cfg["model"], "messages": messages}),
        }
        exec(compile(ast.Module(body=definitions, type_ignores=[]), str(ROOT / "backend/app.py"), "exec"), self.namespace)

    def tearDown(self):
        self.directory.cleanup()

    @contextmanager
    def connect_database(self):
        connection = sqlite3.connect(self.database)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    async def ask(self, **values):
        return await self.namespace["chat"](self.namespace["Chat"](message="测试问题", **values))

    async def test_no_key_general_with_evidence_reports_course_provenance(self):
        with patch.object(httpx, "AsyncClient", side_effect=AssertionError("Provider transport must not run")):
            result = await self.ask(knowledge_mode="general")
        self.assertFalse(result["model_used"])
        self.assertEqual(result["requested_knowledge_mode"], "general")
        self.assertEqual(result["knowledge_scope"], "course")
        self.assertEqual(result["coverage_status"], "course_evidence")
        self.assertIn("未调用模型", result["coverage_notice"])
        self.assertTrue(result["evidence"])
        self.assertIsNone(result["model_provider"])
        with closing(sqlite3.connect(self.database)) as connection:
            saved = json.loads(connection.execute("SELECT metadata FROM messages WHERE role='assistant'").fetchone()[0])
        self.assertEqual(saved["requested_knowledge_mode"], "general")
        self.assertEqual(saved["knowledge_scope"], "course")

    async def test_no_key_general_without_evidence_never_claims_model_knowledge(self):
        self.evidence = []
        with patch.object(httpx, "AsyncClient", side_effect=AssertionError("Provider transport must not run")):
            result = await self.ask(knowledge_mode="general")
        self.assertEqual(result["knowledge_scope"], "course")
        self.assertEqual(result["requested_knowledge_mode"], "general")
        self.assertEqual(result["coverage_status"], "no_course_evidence")
        self.assertIn("没有使用模型一般知识", result["coverage_notice"])
        self.assertNotIn("本次使用模型一般知识", result["coverage_notice"])
        self.assertFalse(result["model_used"])
        self.assertEqual(result["evidence"], [])
        self.assertEqual(result["citations"], [])

    async def test_observation_question_is_blocked_before_paid_call_even_in_general_agent(self):
        self.connection_config['api_key']=TEST_KEY
        with patch.object(httpx,'AsyncClient',side_effect=AssertionError('No provider call without matching observations')):
            result=await self.namespace['chat'](self.namespace['Chat'](message='今天东海1000m深处声速是多少？',knowledge_mode='general',mode='agent'))
        self.assertFalse(result['model_used']);self.assertEqual(result['coverage_status'],'missing_observation_data')
        self.assertEqual(result['requested_knowledge_mode'],'general');self.assertEqual(result['knowledge_scope'],'course')
        self.assertFalse(result['evidence_assessment']['can_answer_requested_numeric']);self.assertFalse(result['evidence_assessment']['claim_support_verified'])

    async def test_trimmed_evidence_is_reassessed_before_provider_transport(self):
        from datetime import datetime,timezone
        self.connection_config['api_key']=TEST_KEY
        self.evidence=[{'id':'TEST-OBSERVATION','source_id':'TEST','text':'Synthetic observation fixture only','url':'https://example.org/test-only','evidence_type':'structured_observation','verification_status':'trusted_observation_adapter','observation':{'variable':'sound_speed','value':1500,'units':'m/s','location':'东海','depth_m':1000,'quality_control':'accepted','observed_at':datetime.now(timezone.utc).isoformat()}}]
        original=context_budget.build_context
        def trim_observation(**values):
            packed=original(**values)
            packed['evidence']=[{key:value for key,value in row.items() if key!='observation'} for row in packed['evidence']]
            return packed
        with patch.object(context_budget,'build_context',side_effect=trim_observation),patch.object(httpx,'AsyncClient',side_effect=AssertionError('Trimming must not bypass evidence assessment')):
            result=await self.namespace['chat'](self.namespace['Chat'](message='今天东海1000m深处声速是多少？',knowledge_mode='general'))
        self.assertFalse(result['model_used']);self.assertEqual(result['coverage_status'],'missing_observation_data')

    async def provider_failure(self, *, error=None, response=None):
        self.connection_config["api_key"] = TEST_KEY
        class FakeClient:
            def __init__(self, **options):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
            async def post(self, *args, **options):
                if error is not None:
                    raise error
                return response
        with patch.object(httpx, "AsyncClient", FakeClient):
            with self.assertRaises(HTTPException) as caught:
                await self.ask()
        self.assertEqual(caught.exception.status_code, 502)
        detail = caught.exception.detail
        self.assertNotIn(TEST_KEY, detail)
        self.assertNotIn("Authorization", detail)
        self.assertNotIn("internal-private", detail)
        return detail

    async def test_arbitrary_exception_text_is_not_returned(self):
        detail = await self.provider_failure(error=RuntimeError("Authorization: Bearer " + TEST_KEY + " internal-private"))
        self.assertIn("返回格式不兼容", detail)

    async def test_network_exception_does_not_echo_header_or_key(self):
        detail = await self.provider_failure(error=httpx.ConnectError("Authorization " + TEST_KEY + " internal-private"))
        self.assertIn("网络连接", detail)
        self.assertNotIn("密钥无效", detail)

    async def test_timeout_exception_has_fixed_safe_diagnosis(self):
        detail = await self.provider_failure(error=httpx.ReadTimeout("timeout " + TEST_KEY + " internal-private"))
        self.assertIn("超时", detail)

    async def test_http_auth_failure_preserves_status_without_remote_body(self):
        detail = await self.provider_failure(response=httpx.Response(401, text="Authorization " + TEST_KEY + " internal-private"))
        self.assertIn("HTTP 401", detail)
        self.assertIn("密钥无效", detail)

    async def test_malformed_success_payload_has_safe_format_error(self):
        detail = await self.provider_failure(response=httpx.Response(200, text="Authorization " + TEST_KEY + " internal-private"))
        self.assertIn("返回格式不兼容", detail)

    async def test_tool_exception_text_is_not_sent_back_to_model(self):
        self.connection_config["api_key"] = TEST_KEY
        def unsafe_reader(path):
            raise RuntimeError("Authorization " + TEST_KEY + " internal-private")
        self.namespace["read_file"] = unsafe_reader
        seen_tool_outputs = []
        class FakeClient:
            def __init__(self, **options):
                self.calls = 0
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
            async def post(self, *args, **options):
                self.calls += 1
                if self.calls == 1:
                    return httpx.Response(200, json={"model": "qwen-test", "choices": [{"message": {
                        "role": "assistant", "tool_calls": [{"id": "test-call", "type": "function", "function": {
                            "name": "read_project_file", "arguments": '{"path":"fixture.m"}'}}]}}]})
                seen_tool_outputs.append(options["json"]["messages"][-1]["content"])
                return httpx.Response(200, json={"model": "qwen-test", "choices": [{"message": {"content": "工具未完成。"}}]})
        with patch.object(httpx, "AsyncClient", FakeClient):
            result = await self.ask(mode="agent")
        self.assertEqual(result["reply"], "工具未完成。")
        self.assertEqual(len(seen_tool_outputs), 1)
        self.assertIn("工具参数不合法", seen_tool_outputs[0])
        self.assertNotIn(TEST_KEY, seen_tool_outputs[0])
        self.assertNotIn("Authorization", seen_tool_outputs[0])
        self.assertNotIn("internal-private", seen_tool_outputs[0])


if __name__ == "__main__":
    unittest.main()
