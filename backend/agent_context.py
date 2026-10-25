"""Read-only task evidence for the conversational agent."""
from pathlib import Path

def guidance():
    return Path(__file__).with_name('agent_guide.md').read_text(encoding='utf-8')+'\n开放研究先用 list_research_skills 发现技能，再 load_research_skill 读取合适的SKILL.md，按需 read_skill_resource；通过 list_at_examples/read_at_file 查阅原始AT输入与函数。季节混合层、表面声道先实际读取 get_ocean_profile，数据诊断与声场仿真分开；不能把目录索引当成执行验证。\n构造指定模型时载入对应 at-kraken、at-krakenc、at-scooter、at-bellhop、at-ram、at-simplepe、at-sparc、at-bellhop3d 或 at-krakel 技能及 references/workflow.md。用 list_model_workflows 检查可用配方，prepare_model_research_task 固化独立输入和运行脚本，run_research_script 实际执行，检查产物后 finish_research_task。创建工具不启动计算。自定义环境先明确目标与关键参数，再修改任务副本；基线参数只能用于原例复现。KRAKEL 弹性场后处理尚未验证时如实说明，不能改用其他模型冒充。'

def tools():
    specs=[('list_project_files','列出授权项目文件',{}),('read_project_file','读取授权项目文本文件',{'path':'string'}),('list_jobs','查询最新100条可见任务的状态、创建时间和输入',{}),('get_job','查询指定任务的真实状态、冻结环境、结果摘要及日志',{'id':'string'}),('get_batch','查询批次结果和稳定性分析',{'id':'string'}),('search_knowledge','查询知识卡和来源',{'query':'string'}),('list_materials','列出教材与全文页索引状态',{}),('search_materials','按专业关键词检索资料原文页，返回定位摘录',{'query':'string'}),('read_material_page','读取教材指定PDF页的提取原文及原页链接',{'source_id':'string','page':'integer'})]
    result=[{'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object','properties':{k:{'type':v} for k,v in fields.items()},'required':list(fields),'additionalProperties':False}}} for name,description,fields in specs]
    next(t for t in result if t['function']['name']=='search_materials')['function']['parameters']['properties']['source_id']={'type':'string','description':'可选，仅搜索指定来源，例如S17；不传则搜索全部索引'}
    return result

def compact(value,detail=False):
    result={k:value.get(k) for k in ('id','state','created','updated','error')}
    plan=value.get('plan',{})
    result['plan']={k:v for k,v in plan.items() if k!='environment_snapshot'}
    env=plan.get('environment_snapshot')
    if env:
        result['environment_snapshot']=env if detail else {'ssp_rows':len(env.get('ssp',[]))}
    if detail:
        for k in ('summary','artifacts'): 
            if k in value:result[k]=value[k]
        result['log']=value.get('log','')[-6000:]
    return result
