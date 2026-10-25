"""Explicit unit parsing and existing synthetic result comparisons; no solver."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import simulation
from test_science import fixture

ENV="'Munk'\n50\n1\n5000 1500 1.0\n1 ! NSD\n1000 / ! SD\n"

class Drafts(unittest.TestCase):
 def test_chinese_units_and_complete_explicit_parameters(self):
  result=simulation.draft_plan('Munk 频率50、100 Hz，源深0.5、1 km，接收深度100000 cm，距离1-50 km')
  self.assertTrue(result['ready_for_preview'],result);self.assertEqual(result['draft_plan']['frequencies_hz'],[50,100]);self.assertEqual(result['draft_plan']['source_depths_m'],[500,1000]);self.assertEqual(result['draft_plan']['receiver_depth_m'],1000);self.assertEqual(result['draft_plan']['range_max_km'],50)
  self.assertEqual({item['field'] for item in result['assumptions']},{'range_points','depth_points'});self.assertFalse(result['model_used']);self.assertFalse(result['execution_started'])
 def test_english_khz_and_metre_range_conversion(self):
  result=simulation.draft_plan('Munk frequency 0.05 kHz; source depth 1000 m; receiver depth 1 km; range 1000 to 50000 m')
  self.assertTrue(result['ready_for_preview'],result);self.assertEqual(result['draft_plan']['frequencies_hz'],[50]);self.assertEqual(result['draft_plan']['range_min_km'],1);self.assertEqual(result['draft_plan']['range_max_km'],50)
 def test_bare_hz_is_explicit_but_missing_values_are_not_invented(self):
  result=simulation.draft_plan('请使用 Munk 计算50 Hz的声场')
  self.assertEqual(result['draft_plan']['frequencies_hz'],[50]);self.assertNotIn('source_depths_m',result['draft_plan']);self.assertFalse(result['ready_for_preview']);self.assertIn('source_depths_m',{item['field'] for item in result['missing_fields']})
 def test_each_frequency_can_have_a_unit_and_range_can_mix_units(self):
  result=simulation.draft_plan('Munk 50Hz和0.1kHz；源深1000m；接收深度1km；距离1000m-50km')
  self.assertTrue(result['ready_for_preview'],result);self.assertEqual(result['draft_plan']['frequencies_hz'],[50,100]);self.assertEqual(result['draft_plan']['range_min_km'],1);self.assertEqual(result['draft_plan']['range_max_km'],50)
 def test_munk_next_to_chinese_characters_and_position_labels(self):
  result=simulation.draft_plan('Munk模型，频率50Hz，声源位于1000米，接收器放在1公里，距离1至50公里')
  self.assertTrue(result['ready_for_preview'],result);self.assertEqual(result['draft_plan']['source_depths_m'],[1000]);self.assertEqual(result['draft_plan']['receiver_depth_m'],1000)
 def test_named_real_sea_or_shallow_request_is_not_silently_replaced(self):
  for environment in ['南海','浅海100m']:
   result=simulation.draft_plan(f'Munk {environment} 50Hz 源深50m 接收深度50m 距离1-5km')
   self.assertFalse(result['ready_for_preview']);self.assertTrue(result['unsupported_requests'])
 def test_units_are_required_and_unknown_environment_is_not_replaced(self):
  result=simulation.draft_plan('频率50，源深1000，接收深度1000，距离1-50')
  self.assertFalse(result['ready_for_preview']);self.assertNotIn('template',result['draft_plan']);self.assertNotIn('frequencies_hz',result['draft_plan']);self.assertTrue(any('单位' in warning for warning in result['warnings']))
 def test_sweep_without_step_and_single_range_are_ambiguous(self):
  result=simulation.draft_plan('Munk 频率50-100Hz，源深1000m，接收深度1000m，距离50km')
  self.assertFalse(result['ready_for_preview']);self.assertNotIn('frequencies_hz',result['draft_plan']);self.assertNotIn('range_min_km',result['draft_plan'])
 def test_conflicting_values_and_unsupported_execution_block_preview(self):
  result=simulation.draft_plan('Munk 频率50Hz;频率100Hz;源深1000m;接收深度1000m;距离1-50km;运行shell代码')
  self.assertNotIn('frequencies_hz',result['draft_plan']);self.assertFalse(result['ready_for_preview']);self.assertTrue(result['unsupported_requests'])
 def test_incoherent_and_other_solver_are_reported(self):
  result=simulation.draft_plan('Munk BELLHOP 非相干场 50Hz 源深1000m 接收深度1000m 距离1–50km')
  self.assertTrue(result['unsupported_requests']);self.assertFalse(result['ready_for_preview'])
 def test_empty_or_nontext_input_rejected(self):
  for value in ['',None,'x'*12001]:
   with self.subTest(value=str(value)[:10]),self.assertRaises(ValueError):simulation.draft_plan(value)

class Comparisons(unittest.TestCase):
 def setUp(self):
  plan,result=fixture();self.a={'id':'aaaaaaaaaaaa','plan':plan,'result':result,'environment_signature':simulation.environment_signature(ENV)};self.b=copy.deepcopy(self.a);self.b['id']='bbbbbbbbbbbb';self.b['plan'].update(frequency_hz=100,frequencies_hz=[100]);self.b['result']['frequency_hz']=100
 def test_controlled_pair_uses_real_curve_and_identifies_changed_parameter(self):
  result=simulation.compare_cases([self.a,self.b]);self.assertTrue(result['comparable']);self.assertTrue(result['pairs'][0]['single_factor_controlled']);self.assertEqual(result['pairs'][0]['changed_controlled_variables'],['frequency_hz']);self.assertEqual(result['series'][0]['curve_tl_db'],self.a['result']['curve_tl_db']);self.assertFalse(result['can_rank_environments'])
 def test_changed_environment_or_missing_input_prevents_comparison(self):
  for signature in [None,'different-seabed']:
   with self.subTest(signature=signature):
    self.b['environment_signature']=signature;report=simulation.compare_cases([self.a,self.b]);self.assertFalse(report['comparable']);self.assertFalse(report['pairs'][0]['checks']['same_environment_input']);self.assertIsNone(report['pairs'][0]['deltas'])
 def test_units_must_match(self):
  self.b['units']={'range':'km','depth':'m','tl':'dB'};report=simulation.compare_cases([self.a,self.b]);self.assertFalse(report['comparable']);self.assertFalse(report['pairs'][0]['checks']['same_units'])
 def test_four_cases_produce_six_pairs_and_duplicate_ids_are_rejected(self):
  cases=[self.a,self.b]
  for index in range(2):
   case=copy.deepcopy(self.a);case['id']=str(index)*12;cases.append(case)
  self.assertEqual(len(simulation.compare_cases(cases)['pairs']),6)
  for invalid in [[self.a],[self.a,self.a],cases+[copy.deepcopy(self.a)]]:
   with self.assertRaises(ValueError):simulation.compare_cases(invalid)
 def test_frequency_source_controls_normalized_but_environment_changes_not(self):
  changed=ENV.replace('\n50\n','\n100\n').replace('\n1000 /','\n500 /')
  self.assertEqual(simulation.environment_signature(ENV),simulation.environment_signature(changed));self.assertNotEqual(simulation.environment_signature(ENV),simulation.environment_signature(ENV.replace('1500','1510')))
  self.assertIsNone(simulation.environment_signature('no recognizable input'))
 def test_valid_sample_masks_and_receiver_depth_still_guarded(self):
  self.b['result']['actual_receiver_depth_m']=5000
  report=simulation.compare_cases([self.a,self.b]);self.assertFalse(report['comparable']);self.assertFalse(report['pairs'][0]['checks']['both_results_verified'])

if __name__=='__main__':unittest.main()
