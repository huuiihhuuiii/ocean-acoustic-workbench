"""Import course metadata and only the code/inputs needed for first verified runs."""
from pathlib import Path
import zipfile, json, shutil, sys
ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'.local'
def bootstrap(package):
    LOCAL.mkdir(exist_ok=True)
    with zipfile.ZipFile(package) as z:
        kb=LOCAL/'kb';kb.mkdir(exist_ok=True)
        for name in ['source_registry.json','claim_cards.jsonl','graph_seed.json','kb_questions_seed.jsonl']:
            (kb/name).write_bytes(z.read('05_知识库起步/'+name))
        reg=json.loads((kb/'source_registry.json').read_text(encoding='utf-8'))
        pdfs=LOCAL/'sources';pdfs.mkdir(exist_ok=True)
        for source in reg['sources']:
            if source['type']=='.pdf':
                target=pdfs/(source['id']+'.pdf')
                if not target.exists():
                    with z.open(source['package_path']) as inp,target.open('wb') as out:shutil.copyfileobj(inp,out)
        at_archive=LOCAL/'at-input.zip'
        if not at_archive.exists():
            with z.open('03_工具与教程/at.zip') as inp,at_archive.open('wb') as out:shutil.copyfileobj(inp,out)
    tool=LOCAL/'toolbox';tool.mkdir(exist_ok=True)
    with zipfile.ZipFile(at_archive) as a:
        for info in a.infolist():
            path=Path(info.filename)
            wanted=path.suffix=='.m' or info.filename.startswith('at/bin/') or info.filename in ['at/tests/Munk/MunkK.env','at/tests/Munk/MunkK.flp']
            if wanted and not info.is_dir():
                dest=(tool/path).resolve()
                if not dest.is_relative_to(tool.resolve()):raise ValueError('Unsafe archive path')
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(a.read(info))
    project=LOCAL/'project';project.mkdir(exist_ok=True)
    for name in ['MunkK.env','MunkK.flp']:
        shutil.copy2(tool/'at/tests/Munk'/name,project/name)
    script=ROOT/'backend/matlab/run_ocean_case.m'
    if script.exists():shutil.copy2(script,project/script.name)
    config={'matlab_path':shutil.which('matlab') or '', 'toolbox_path':str(tool/'at'), 'project_path':str(project),'package_path':str(Path(package).resolve()),'provider':'Qwen','base_url':'https://dashscope.aliyuncs.com/compatible-mode/v1','model':'qwen3.7-plus','timeout_seconds':240}
    if not (LOCAL/'config.json').exists():(LOCAL/'config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Imported',len(reg['sources']),'sources; toolbox:',tool/'at')
if __name__=='__main__':bootstrap(sys.argv[1])
