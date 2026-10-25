import json
from pathlib import Path
providers=[
 {'id':'DeepSeek','name':'DeepSeek 官方','organization':'杭州深度求索','base_url':'https://api.deepseek.com','website':'https://platform.deepseek.com','documentation':'https://api-docs.deepseek.com/api/list-models/','note':'官方显示名称与 API 标识不同：V4.1-Flash 使用 deepseek-flash。'},
 {'id':'Qwen','name':'阿里云百炼 · 北京','organization':'阿里云','base_url':'https://dashscope.aliyuncs.com/compatible-mode/v1','website':'https://bailian.console.aliyun.com','documentation':'https://help.aliyun.com/zh/model-studio/models','note':'可使用北京业务空间专属域名；API Key 须与地域一致。三方模型需在控制台开通对应服务。'},
 {'id':'Kimi','name':'月之暗面 Kimi 官方','organization':'Moonshot AI','base_url':'https://api.moonshot.cn/v1','website':'https://platform.kimi.com','documentation':'https://platform.kimi.com/docs/models','note':'当前列出 K3 / K2.7 Code / K2.6；已下线的 K2、K2.5 不再作为预设。'},
 {'id':'GLM','name':'智谱 BigModel 官方','organization':'智谱 AI','base_url':'https://open.bigmodel.cn/api/paas/v4','website':'https://bigmodel.cn','documentation':'https://docs.bigmodel.cn/cn/guide/start/model-overview','note':'使用按量模型 API 端点；Coding Plan 的专用端点与权限不能混用。'}]
models=[]
def add(provider,id,name,developer,kind,description,docs=None,options=None):
    p=next(x for x in providers if x['id']==provider)
    models.append({'key':provider+':'+id,'provider':provider,'id':id,'name':name,'developer':developer,'kind':kind,'description':description,'documentation':docs or p['documentation'],'verified_date':'2026-10-08','verification':'官方文档已核对；账户权限待验证','request_options':options or {}})
add('DeepSeek','deepseek-flash','DeepSeek-V4.1-Flash','DeepSeek','通用 / 视觉','日常知识问答、图像理解与工具调用。')
add('DeepSeek','deepseek-v4-pro','DeepSeek-V4-Pro','DeepSeek','通用 / 推理','复杂问题与长上下文分析。')
for id,name,kind in [('qwen3.8-max','Qwen3.8-Max','通用 / 视觉'),('qwen3.7-plus','Qwen3.7-Plus','通用 / 视觉'),('qwen3.8-flash','Qwen3.8-Flash','通用')]:add('Qwen',id,name,'阿里巴巴通义千问',kind,'百炼官方千问模型；使用北京地域模型 API。')
add('Qwen','deepseek-v4.1-flash','DeepSeek-V4.1-Flash','DeepSeek','第三方模型','通过百炼调用；与 DeepSeek 官方的 deepseek-flash 标识不同。')
add('Qwen','deepseek-v4-pro-0813','DeepSeek-V4-Pro-0813','DeepSeek','第三方模型','百炼列出的 DeepSeek 版本标识。')
add('Qwen','kimi-k3','Kimi K3','Moonshot AI','第三方模型','百炼列出的 Kimi 模型；账户需开通对应服务。')
add('Qwen','glm-5.2','GLM-5.2','智谱 AI','第三方模型','百炼列出的 GLM 模型；账户需开通对应服务。')
add('Kimi','kimi-k3','Kimi K3','Moonshot AI','通用 / 推理','支持知识工作、视觉理解与编程；须满足账户访问条件。',options={'reasoning_effort':'low'})
add('Kimi','kimi-k2.7-code','Kimi K2.7 Code','Moonshot AI','编程','面向编程与工具调用。')
add('Kimi','kimi-k2.7-code-highspeed','Kimi K2.7 Code Highspeed','Moonshot AI','编程 / 高速','K2.7 Code 的高速版。')
add('Kimi','kimi-k2.6','Kimi K2.6','Moonshot AI','通用 / 视觉','通用对话、视觉理解和 Agent 任务。')
glm_options={'thinking':{'type':'enabled'},'reasoning_effort':'low','temperature':1}
add('GLM','glm-5.3','GLM-5.3','智谱 AI','文本 / 推理','复杂编程与分析；始终启用思考。','https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3',glm_options)
add('GLM','glm-5.3-flash','GLM-5.3-Flash','智谱 AI','通用 / 视觉','原生多模态模型；始终启用思考。','https://docs.bigmodel.cn/cn/guide/models/vlm/glm-5.3-flash',glm_options)
add('GLM','glm-5.3-flashx','GLM-5.3-FlashX','智谱 AI','通用 / 高速','Flash 系列高速版；模型 API 与套餐权限以账户为准。','https://docs.bigmodel.cn/cn/guide/models/vlm/glm-5.3-flash',glm_options)
out=Path(__file__).parent/'data/model_catalog.json'
out.write_text(json.dumps({'verified_date':'2026-10-08','providers':providers,'models':models},ensure_ascii=False,indent=2),encoding='utf-8')
print('Catalog:',len(providers),'API providers,',len(models),'explicit provider/model combinations')
