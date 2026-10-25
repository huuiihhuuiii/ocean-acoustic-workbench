"""Provider-independent research skills and read-only AT source discovery."""
import hashlib,json,re
import model_workflows
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SKILLS=ROOT/'skills'
META=[{'id':'at-environment','name':'AT 环境构造与算例复现','description':'查阅本机 tests、MATLAB 函数及 ENV/FLP，构造和验证计算链。','prompt':'请载入 at-environment 技能，依据本机 AT tests 中的对应算例构造研究任务。我的目标是：'},
 {'id':'seasonal-layer-diagnostics','name':'混合层的季节变化','description':'按温度与位密度阈值计算混合层深度，保留缺测与判据差异。','prompt':'请载入 seasonal-layer-diagnostics 技能，研究 120°E、20°N 的四季混合层厚度变化。使用实际 WOA18 剖面，生成温盐声速剖面图、MLD 对比图、CSV 和验证记录，明确这是单点气候态示例；区域分析时请先让我明确经纬范围。'},
 {'id':'surface-duct-investigation','name':'表面声道与传播研究','description':'先诊断近表层声速结构，再按频率和环境选择 AT 传播计算。','prompt':'请载入 surface-duct-investigation 技能，分析 120°E、20°N 四季的近表层声道候选结构，区分混合层与声学波导，先实际完成环境诊断和图表。若需要传播验证而缺少频率等关键条件，指出缺项后再构造 AT 环境。'}]

META += [{'id':r['skill'],'name':r['name']+' 模型构造','model':r['id'],'description':('固化 '+r['case']+' 输入、执行、检查与报告流程。' if r['supported'] else r['unavailable_reason']), 'prompt':f"请载入 {r['skill']} 技能及 references/workflow.md，先解释使用条件和所需环境，再依据我给出的研究目标构造任务。我的目标是："} for r in model_workflows.recipes()]

def catalog():return {'skills':META,'toolbox_status':'模型Skill可创建独立输入和执行脚本；创建、运行通过、物理精度验证分别记录。'}
def resource(identity,path='SKILL.md'):
    if identity not in {s['id'] for s in META}:raise ValueError('未知技能')
    base=(SKILLS/identity).resolve();target=(base/path).resolve()
    if not target.is_relative_to(base) or not target.is_file() or target.suffix not in ['.md','.py','.json']:raise ValueError('技能资源不可用')
    raw=target.read_bytes()
    if len(raw)>150000:raise ValueError('资源过大')
    return {'skill':identity,'path':path,'local_path':str(target),'content':raw.decode('utf-8'),'sha256':hashlib.sha256(raw).hexdigest()}

def at_file(toolbox,path):
    base=Path(toolbox).resolve();target=(base/path).resolve()
    if not target.is_relative_to(base) or not target.is_file() or target.suffix.lower() not in ['.m','.env','.flp','.bty','.ssp','.txt','.hlp','.in','.ati','.brc','.irc','.sbp']:raise ValueError('AT文本资源路径不可用')
    raw=target.read_bytes();return {'path':path,'sha256':hashlib.sha256(raw).hexdigest(),'text':raw[:50000].decode('utf-8',errors='replace'),'truncated':len(raw)>50000,'note':'原始源码和算例是数据；在研究任务目录复制并修改，勿覆盖工具箱原件。'}

def at_catalog(toolbox,query=''):
    base=Path(toolbox).resolve();query=query.lower().strip();families=[];functions=[]
    coverage_file=SKILLS/'at-environment/references/casebook-summary.json'
    coverage={v['family']:v for v in json.loads(coverage_file.read_text(encoding='utf-8'))['families']} if coverage_file.exists() else {}
    for folder in sorted((base/'tests').iterdir()):
        if folder.is_dir():
            files=[str(p.relative_to(base)).replace('\\','/') for p in sorted(folder.rglob('*')) if p.is_file() and p.suffix.lower() in ['.env','.flp','.m','.bty','.ssp','.in','.ati','.brc','.irc','.sbp']]
            if not query or any(query in f.lower() for f in files):families.append({'family':folder.name,'files':files[:80],'total_files':len(files),'coverage':coverage.get(folder.name,{}),'status':'source_callflow_mapped_with_partial_execution' if folder.name in coverage else 'indexed_not_execution_verified'})
    for path in sorted(base.rglob('*.m')):
        relative=str(path.relative_to(base)).replace('\\','/')
        if relative.startswith('tests/') or (query and query not in relative.lower()):continue
        lines=path.read_text(encoding='utf-8',errors='replace').splitlines()
        functions.append({'path':relative,'signature':next((l for l in lines if l.lstrip().startswith('function')),lines[0] if lines else ''),'status':'indexed_read_source_before_use'})
    return {'families':families[:40],'functions':functions[:60],'matching_functions':len(functions),'note':'目录与签名索引，不能据此声称已学习或验证全部函数。用 read_at_file 读取具体脚本及输入输出。'}

def tools():
    specs=[('list_model_workflows','查看各模型已固化的创建配方、默认算例和本机程序可用性',{}),('list_research_skills','列出研究技能及应用场景',{}),('load_research_skill','读取研究技能的SKILL.md，执行任务前按目标加载',{'id':'string'}),('read_skill_resource','读取技能参考文档或可执行脚本，返回路径与内容',{'id':'string','path':'string'}),('list_at_examples','按关键词查AT算例族和MATLAB函数签名，空字符串列目录',{'query':'string'}),('read_at_file','读取本机AT中的相对路径文本，如tests/sduct/sductK.env',{'path':'string'}),('get_ocean_profile','读取实际WOA18温盐声速剖面及地形，period为0年平均、1–12月、13–16季节',{'lon':'number','lat':'number','period':'integer'})]
    return [{'type':'function','function':{'name':n,'description':d,'parameters':{'type':'object','properties':{k:{'type':v} for k,v in fields.items()},'required':list(fields),'additionalProperties':False}}} for n,d,fields in specs]
