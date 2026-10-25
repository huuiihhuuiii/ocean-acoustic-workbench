"""Unicode/provenance, paraphrases and evidence sufficiency; no paid requests."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import answer_policy
import evidence_policy
import evaluate_knowledge
import ingestion
import knowledge
import query_planning
import retrieval


class KnowledgeQualityTests(unittest.TestCase):
    def test_display_unicode_and_offsets_preserve_formula_characters(self):
        original='  p² = ρcI; c₀ + αz; 单位 m²/s²；Ｑ保持原字形。\n' * 15
        display=ingestion.clean_text(original)
        self.assertIn('p²',display);self.assertIn('c₀',display);self.assertIn('Ｑ',display)
        self.assertIn('p2',ingestion.search_normalize(display));self.assertIn('c0',ingestion.search_normalize(display))
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'authored-formula.md';source.write_text(original,encoding='utf-8')
            chunks,warnings=ingestion.ingest_source({'id':'FORMULA','path':str(source)},directory,size=250,overlap=40)
            self.assertFalse(warnings)
            for row in chunks:
                self.assertEqual(row['text'],display[row['char_start']:row['char_end']])
                self.assertEqual(row['search_text'],ingestion.search_normalize(row['text']))
                self.assertEqual(row['offset_basis'],'display_page_text_v2')
                self.assertEqual(row['ingestion_version'],2)
                self.assertFalse(row['math_layout_verified'])
            self.assertIn('p²',chunks[0]['text'])

    def test_legacy_index_readable_but_needs_source_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'old.jsonl'
            path.write_text(json.dumps({'id':'OLD','source_id':'S17','pdf_page':31,'text':'p2 = rho c I','evidence_type':'source_excerpt'})+'\n',encoding='utf-8')
            values=retrieval.load_chunks(path)
            self.assertEqual(values[0]['text'],'p2 = rho c I')  # No invented repair.
            self.assertIn('重建',values[0]['text_integrity_warning'])
            with patch.object(knowledge,'CHUNKS',path):status=knowledge.retrieval_status()
            self.assertTrue(status['text_integrity']['requires_rebuild'])
            self.assertEqual(status['text_integrity']['legacy_chunks'],1)

    def test_maintained_colloquial_queries_retrieve_multiple_concepts(self):
        cases=[('把声源放到声道轴附近为什么可能更有效',{'source_depth','mode_excitation','deep_sound_channel'}),('为什么接收位置平移一点会突然几乎听不到',{'modal_sum','coherent_modal_sum','near_zero_pressure'}),('盐多一点声音会不会跑得快一些',{'temperature_salinity'})]
        with patch.object(knowledge,'CHUNKS',Path('__missing_test_index__')):
            for question,expected in cases:
                evidence=knowledge.retrieve(question)
                self.assertTrue(expected.issubset({row.get('node_id') for row in evidence}),question)
                self.assertTrue(any('RRF' in row['retrieval'].get('methods',[]) for row in evidence))
                self.assertTrue(all(row['support_status']=='candidate_only' and not row['claim_support_verified'] for row in evidence))
        self.assertEqual(knowledge.retrieve('海洋里的世界杯足球冠军是哪个队'),[])

    def test_query_rules_are_contextual_and_bounded(self):
        self.assertFalse(query_planning.plan_query('今天我的盐多放了一点')['rule_ids'])
        self.assertFalse(query_planning.plan_query('TEOS-10 与温盐压输入有什么关系')['rule_ids'])
        plan=query_planning.plan_query('把声源放到声道轴附近为什么可能更有效')
        self.assertIn('source_near_axis',plan['rule_ids']);self.assertLessEqual(len(plan['queries']),4)
        self.assertFalse(plan['model_called'])

    def test_many_cited_page_chunks_do_not_crowd_out_precise_reviewed_card(self):
        rows=[{'id':f'D-CROWD-{i}','source_id':'S17','pdf_page':359,'node_id':'transmission_loss','node_ids':['transmission_loss'],'evidence_type':'source_excerpt','text':'SHD complex pressure amplitude transmission loss TL reference pressure. '*20} for i in range(30)]
        found=retrieval.retrieve(knowledge.graph_data(),knowledge.knowledge_cards(),'SHD 文件的复数声压如何转成 TL',chunks=rows)
        self.assertTrue({'binary_shd_pressure','transmission_loss'}.issubset({row.get('node_id') for row in found if row.get('evidence_type')!='source_excerpt'}))
        self.assertTrue(any(row.get('evidence_type')=='source_excerpt' for row in found))

    def test_nonempty_snapshot_cannot_supply_current_site_value(self):
        question='今天东海一千米深海水声速是多少'
        background=[{'id':'BG','source_id':'NOAA','text':'Typical ocean sound speed is about 1500 m/s.','evidence_type':'public_web_excerpt','fetched_at':'2026-10-15T00:00:00Z'}]
        assessment=evidence_policy.assess_evidence(question,background)
        self.assertEqual(assessment['status'],'missing_observation_data')
        self.assertEqual(assessment['observation_requirements']['depth_m'],1000)
        self.assertFalse(assessment['claim_support_verified'])
        for scope in ('course','general'):
            result=answer_policy.policy(background,scope,'chat',question)
            self.assertFalse(result['can_generate']);self.assertEqual(result['coverage_status'],'missing_observation_data')
        self.assertTrue(answer_policy.policy(background,'general','chat','温度如何影响声速')['can_generate'])
        for terse in ('今天东海海水声速','东海1000米声速','today temperature in East China Sea'):
            self.assertEqual(evidence_policy.assess_evidence(terse,background)['status'],'missing_observation_data')
        self.assertFalse(evidence_policy.observation_requirements('最新海平面研究有哪些机制')['requires_observation'])
        self.assertFalse(evidence_policy.observation_requirements('What is ocean current speed?')['requires_observation'])

    def test_future_observation_contract_checks_time_depth_qc_and_all_regions(self):
        now=datetime(2026,10,15,8,tzinfo=timezone.utc)
        row={'id':'OBS','source_id':'AUTHORED','url':'https://example.org/authored-fixture','evidence_type':'structured_observation','verification_status':'trusted_observation_adapter','observation':{'variable':'sound_speed','value':1500,'units':'m/s','quality_control':'accepted','location':'东海','depth_m':1000,'observed_at':'2026-10-15T07:00:00Z'}}
        question='今天东海1000米深海水声速是多少'
        self.assertEqual(evidence_policy.assess_evidence(question,[row],now)['status'],'structured_observation_available')
        for changes in ({'observed_at':'2026-10-12T07:00:00Z'},{'depth_m':50},{'quality_control':'not_checked'},{'location':'南海'},{'value':float('nan')}):
            wrong={**row,'observation':{**row['observation'],**changes}}
            self.assertEqual(evidence_policy.assess_evidence(question,[wrong],now)['status'],'missing_observation_data')
        comparison='今天东海和南海1000米深海水声速哪个更快'
        self.assertEqual(evidence_policy.assess_evidence(comparison,[row],now)['status'],'missing_observation_data')
        self.assertFalse(evidence_policy.assess_evidence(question,[{**row,'verification_status':'source_text_unreviewed'}],now)['can_answer_requested_numeric'])

    def test_citation_ids_and_page_membership_are_not_semantic_support(self):
        rows=[{'id':'C-ONE','source_id':'S17','pdf_page':359,'all_references':[{'source_id':'S17','pdf_page':359}]}]
        check=evidence_policy.validate_citation_ids('A[C-ONE] B[C-FAKE] C[S17,359] D[S17,999]',rows)
        self.assertEqual(check['unknown_ids'],['C-FAKE'])
        self.assertEqual(check['unknown_source_locators'],[{'source_id':'S17','pdf_page':999}])
        self.assertFalse(check['claim_support_verified'])

    def test_benchmark_contains_sixty_authored_criteria_and_traceable_locators(self):
        spec=json.loads(evaluate_knowledge.BENCHMARK.read_text(encoding='utf-8'))
        self.assertEqual(len(spec['cases']),60);self.assertEqual(len({case['id'] for case in spec['cases']}),60)
        for case in spec['cases']:
            self.assertTrue(case['answer_points']);self.assertTrue(case['applicable_conditions']);self.assertTrue(case['must_not_claim'])
            if case['retrieval_expected']:self.assertTrue(case['source_references'])
        report=evaluate_knowledge.evaluate()
        self.assertEqual(report['model_calls'],0);self.assertEqual(report['network_calls'],0)
        self.assertGreaterEqual(report['metrics']['hit_at_k'],0.95)
        self.assertEqual(report['metrics']['numeric_gate_correct'],8)
        self.assertEqual(report['metrics']['unknown_empty_correct'],2)

    def test_precise_focus_filters_annotated_noise_not_just_first_hit(self):
        def raw(identifier,source,page,text):
            return {'id':identifier,'source_id':source,'pdf_page':page,'node_ids':[],'evidence_type':'source_excerpt','text':text}
        chunks=[raw('GOOD375','S17',375,'Munk sound speed profile describes an idealized deep sound channel. '*10),raw('GOOD376','S17',376,'Munk sound speed profile requires explicit environmental conditions. '*10),raw('COX','S18',400,'Cox-Munk surface roughness model Munk profile. '*10),raw('HISTORY','S17',15,'Walter Munk author history Munk profile. '*10),raw('INDEX','S17',807,'Index Munk profile page list. '*10),raw('SAME_WORD','OTHER',375,'Munk sound speed profile idealized deep sound channel. '*10)]
        evidence=retrieval.retrieve(knowledge.graph_data(),knowledge.knowledge_cards(),'Munk 理想剖面的适用条件是什么',chunks=chunks)
        self.assertEqual(evidence[0]['node_id'],'munk_profile')
        self.assertEqual({row['id'] for row in evidence if row['evidence_type']=='source_excerpt'},{'GOOD375','GOOD376'})
        self.assertTrue(all(row['id'] not in {'COX','HISTORY','INDEX','SAME_WORD'} for row in evidence))
        self.assertLessEqual(sum(row['retrieval']['role']=='graph_context' for row in evidence),2)
        self.assertLess(len(evidence),8)

    def test_cox_munk_surface_model_is_not_sound_speed_profile(self):
        for question in ('Cox–Munk 海面粗糙度模型是什么','Cox-Munk surface roughness','Cox Munk 海面模型'):
            rows=retrieval.retrieve(knowledge.graph_data(),knowledge.knowledge_cards(),question)
            self.assertFalse(any(row.get('node_id') in {'munk_profile','munk_case'} for row in rows),question)
        cox={'id':'COX-RAW','source_id':'S18','pdf_page':400,'evidence_type':'source_excerpt','node_ids':[],'text':'Cox-Munk surface roughness describes sea surface slope statistics. '*12}
        filler=[{'id':f'FILLER-{i}','source_id':'S17','pdf_page':i+1,'evidence_type':'source_excerpt','node_ids':[],'text':'Munk profile describes an idealized sound speed environment. '*10} for i in range(30)]
        rows=retrieval.retrieve(knowledge.graph_data(),knowledge.knowledge_cards(),'Cox–Munk 海面粗糙度模型是什么',chunks=filler+[cox])
        self.assertEqual([row['id'] for row in rows],['COX-RAW'])
        noise={'id':'PUBLIC-NOISE','source_id':'O-NOISE','evidence_type':'public_web_excerpt','text':'Generic ocean model and sea surface knowledge.'}
        self.assertEqual([row['id'] for row in retrieval.focused_evidence('Cox–Munk 海面模型',rows+[noise])],['COX-RAW'])

    def test_public_second_topic_must_be_explicit_when_course_focus_exists(self):
        with patch.object(knowledge,'CHUNKS',Path('__missing_test_index__')):
            single=knowledge.retrieve('Munk 理想剖面的适用条件是什么')
            mixed=knowledge.retrieve('Munk 与 WOA 的声速剖面有什么区别')
            full=knowledge.retrieve('Munk 与 World Ocean Atlas 的剖面有什么区别')
        self.assertFalse(any(row['source_id'].startswith('O-') for row in single))
        self.assertTrue(any(row['source_id']=='O-WOA' for row in mixed))
        self.assertTrue(any(row['source_id']=='O-WOA' for row in full))
        self.assertFalse(any(row['source_id'] in {'O-WOD','O-ARGO-QC'} for row in mixed))

    def test_no_key_formatter_never_dumps_pdf_extraction(self):
        rows=knowledge.retrieve('Munk 理想剖面')
        marker='UNREVIEWED_PDF_GARBAGE_'*200
        raw={'id':'RAW','source_id':'S17','pdf_page':375,'evidence_type':'source_excerpt','text':marker}
        answer=knowledge.format_no_model_answer(rows+[raw])
        self.assertNotIn(marker[:40],answer);self.assertIn('适用条件',answer);self.assertIn('资料抽屉',answer);self.assertLess(len(answer),1800)
        raw_only=knowledge.format_no_model_answer([raw]);self.assertNotIn(marker[:40],raw_only);self.assertIn('PDF 第 375 页',raw_only)


if __name__=='__main__':unittest.main()
