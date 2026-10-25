"""Offline checks of provider isolation and incompatible-model request handling."""
import sys,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import models,httpx
from fastapi import HTTPException

class Connections(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.local=patch.object(models,'LOCAL',Path(self.temp.name));self.local.start()
  self.cfg={'provider':'DeepSeek','base_url':'https://api.deepseek.com','model':'deepseek-flash','api_key':'deepseek-test-only'}
 def tearDown(self):self.local.stop();self.temp.cleanup()
 def config(self):return dict(self.cfg)
 def test_provider_key_does_not_cross_suppliers(self):
  models.store_profile({'provider':'Kimi','base_url':'https://api.moonshot.cn/v1','model':'kimi-k3','api_key':'kimi-test-only'})
  connection=models.select_connection({'provider':'Kimi','model':'kimi-k3'},self.config)
  self.assertEqual(connection['api_key'],'kimi-test-only')
  with self.assertRaises(HTTPException) as error:models.select_connection({'provider':'GLM','model':'glm-5.3'},self.config)
  self.assertEqual(error.exception.status_code,422)
  public=json.dumps(models.public_profiles(self.config));self.assertNotIn('test-only',public)
 def test_supplier_model_options(self):
  glm=models.chat_payload({'provider':'GLM','model':'glm-5.3'},[])
  self.assertEqual(glm['thinking']['type'],'enabled');self.assertEqual(glm['reasoning_effort'],'low')
  kimi=models.chat_payload({'provider':'Kimi','model':'kimi-k3'},[])
  self.assertNotIn('temperature',kimi);self.assertEqual(kimi['reasoning_effort'],'low')
 async def test_success_uses_exact_api_id_and_does_not_certify_agent(self):
  seen=[]
  def handler(request):
   seen.append(json.loads(request.content));self.assertEqual(str(request.url),'https://api.deepseek.com/chat/completions')
   return httpx.Response(200,json={'model':'deepseek-flash','choices':[{'message':{'content':'OK'}}],'usage':{'total_tokens':9}})
  original=httpx.AsyncClient
  with patch.object(models.httpx,'AsyncClient',side_effect=lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
   result=await models.test_connection({},self.config)
  self.assertTrue(result['ok']);self.assertEqual(seen[0]['model'],'deepseek-flash');self.assertIn('不表示',result['note'])
 async def test_permission_failure_redacts_remote_body(self):
  original=httpx.AsyncClient
  with patch.object(models.httpx,'AsyncClient',side_effect=lambda **kw:original(transport=httpx.MockTransport(lambda r:httpx.Response(403,text='echo secret deepseek-test-only')),**kw)):
   with self.assertRaises(HTTPException) as error:await models.test_connection({},self.config)
  self.assertEqual(error.exception.status_code,502);self.assertNotIn('test-only',error.exception.detail)
 async def test_account_list_requires_actual_call_for_certification(self):
  original=httpx.AsyncClient
  with patch.object(models.httpx,'AsyncClient',side_effect=lambda **kw:original(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'data':[{'id':'deepseek-flash'}]})),**kw)):
   result=await models.list_account_models({},self.config)
  self.assertTrue(result['selected_listed']);self.assertIn('实际调用',result['note'])
if __name__=='__main__':unittest.main()
