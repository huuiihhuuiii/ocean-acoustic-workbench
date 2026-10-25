"""Evidence-backed model recipes shared by Agent tools and the model library."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'skills/at-environment/references/creation-workflows.json'


def recipes():
    return json.loads(REFERENCE.read_text(encoding='utf-8'))['models']


def catalog(toolbox, matlab=None):
    tool = Path(toolbox)
    return {'models': [{**r, 'available': r['supported'] and (r['id']=='ram' or matlab is None or Path(matlab).is_file()) and all((tool / 'bin' / exe).is_file() for exe in r['executables']),
                        'runtime': 'Python' if r['id']=='ram' else 'MATLAB',
                        'matlab_available': Path(matlab).is_file() if matlab is not None else None,
                        'missing_executables': [exe for exe in r['executables'] if not (tool / 'bin' / exe).is_file()]}
                       for r in recipes()]}


def payload(toolbox, model, case):
    """Read only original inputs; reject unavailable recipes before task creation."""
    tool = Path(toolbox).resolve()
    recipe = next((r for r in recipes() if r['id'] == model.lower()), None)
    if recipe is None:
        raise ValueError('未知模型，请先 list_model_workflows')
    if not recipe['supported']:
        raise ValueError(recipe['unavailable_reason'])
    if case and case != recipe['case']:
        raise ValueError('未固化的算例；现有创建入口为 ' + recipe['case'] + '，其他算例请按技能独立构造')
    missing = [exe for exe in recipe['executables'] if not (tool / 'bin' / exe).is_file()]
    if missing:
        raise ValueError('缺少程序：' + ', '.join(missing))
    files, sources = {}, []
    for source, target in recipe['inputs']:
        path = (tool / source).resolve()
        if not path.is_relative_to(tool) or not path.is_file():
            raise ValueError('算例输入不存在：' + source)
        raw = path.read_bytes()
        files[target] = raw
        sources.append({'source': source, 'file': target, 'sha256': hashlib.sha256(raw).hexdigest()})
    helper = ROOT / 'skills/at-environment/scripts'
    if model.lower() == 'ram':
        files['read_ram_grid.py'] = (helper / 'read_ram_grid.py').read_bytes()
        files['run_model.py'] = (helper / 'run_ram_workflow.py').read_bytes()
        runner = 'run_model.py'
    else:
        quote = lambda value: value.replace("'", "''")
        setup = f"addpath(genpath('{quote(tool.as_posix())}')); set(0,'DefaultFigureVisible','off');\n"
        for suffix in ['.shd', '.shd.mat', '.grn', '.mod', '.prt']:
            output = recipe['base'] + suffix
            setup += f"if isfile('{output}'), delete('{output}'); end\n"
        calls = []
        for exe in recipe['executables']:
            calls.append(f"[code,txt]=system(['\"' which('{exe}') '\" {recipe['base']}']); disp(txt); assert(code==0,'{exe} failed');\n")
        if recipe['postprocess']:
            calls.append(recipe['postprocess'] + '\n')
        setup += ''.join(calls) + f"workflow_output='{recipe['output']}'; workflow_model='{recipe['name']}'; workflow_axis='{recipe['axis']}';\n"
        setup += (helper / 'summarize_model.m').read_text(encoding='utf-8')
        files['run_model.m'] = setup.encode('utf-8')
        runner = 'run_model.m'
    manifest = {'model': recipe['id'], 'skill': recipe['skill'], 'case': recipe['case'], 'runner': runner,
                'sources': sources, 'scope': '原例创建与执行结构检查；自定义环境需明确改动并单独验证。',
                'limitations': recipe['limitations']}
    if model.lower() == 'ram':
        manifest['ram_executable'] = str(tool / 'bin/ram.exe')
    return files, manifest


def input_hashes(folder):
    """Freeze the actual staged model inputs, including user-added dependencies."""
    extensions = {'.env', '.flp', '.bty', '.ati', '.ssp', '.in', '.brc', '.irc', '.sbp'}
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(folder).iterdir())
            if p.is_file() and (p.suffix.lower() in extensions or p.name in {'run_model.py','run_model.m','read_ram_grid.py'})}
