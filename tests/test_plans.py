"""Schema-level checks never enqueue MATLAB or call paid APIs."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import Plan,preview
from pydantic import ValidationError
from fastapi import HTTPException
class PlanTests(unittest.TestCase):
 def test_numeric_integer_input_and_case_count(self):
  result=preview(Plan(frequencies_hz=[50,100],source_depths_m=[500,1000]));self.assertEqual(result['case_count'],4)
 def test_unknown_field_rejected(self):
  with self.assertRaises(ValidationError):Plan(command='system("unsafe")')
 def test_boolean_or_unit_string_rejected(self):
  for value in [True,'50 Hz','50']:
   with self.subTest(value=value):
    with self.assertRaises(ValidationError):Plan(frequencies_hz=[value])
 def test_nonfinite_and_out_of_template_range(self):
  for value in [float('nan'),float('inf'),0,201]:
   with self.subTest(value=value):
    with self.assertRaises(ValidationError):Plan(frequencies_hz=[value])
 def test_duplicate_controls_deduplicated(self):
  self.assertEqual(preview(Plan(frequencies_hz=[50,50],source_depths_m=[500,500]))['case_count'],1)
 def test_range_and_template_rejected(self):
  for plan in [Plan(range_min_km=20,range_max_km=10),Plan(template='arbitrary_env')]:
   with self.assertRaises(HTTPException):preview(plan)
if __name__=='__main__':unittest.main()
