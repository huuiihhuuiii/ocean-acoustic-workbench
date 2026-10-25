"""Explicit code scopes and job-scoped artifacts; never expose local settings."""
import hashlib
from urllib.parse import quote
from pathlib import Path
from fastapi import HTTPException
TEXT={'.m','.env','.flp','.py','.jsx','.js','.css','.md','.json','.txt','.csv','.log','.prt','.ray','.in','.bty','.ati','.ssp','.brc','.irc','.sbp','.line'}
IMAGE={'.png','.svg'}
RAW={'.shd','.mod','.grn','.mat','.grid','.npz'}
CODE_DIRS={'backend','src','tests'}

def code_allowed(root,path):
    rel=path.relative_to(root)
    return rel.as_posix()=='README.md' or (len(rel.parts)>1 and rel.parts[0] in CODE_DIRS and not any(p.startswith('.') or p=='__pycache__' for p in rel.parts))

def list_files(root,project,local,jobs):
    rows=[]
    def add(path,key,group,label=None,url=None):
        if not path.is_file() or path.suffix.lower() not in TEXT|IMAGE|RAW:return
        rows.append({'path':key,'size':path.stat().st_size,'group':group,'label':label or key,'kind':'image' if path.suffix.lower() in IMAGE else 'raw' if path.suffix.lower() in RAW else 'text','url':url})
    for directory in sorted(CODE_DIRS):
        for path in sorted((root/directory).rglob('*')):
            if path.is_file() and code_allowed(root,path):add(path,'@workbench/'+path.relative_to(root).as_posix(),'workbench',path.relative_to(root).as_posix())
    add(root/'README.md','@workbench/README.md','workbench','README.md')
    for path in sorted(project.rglob('*')):
        if path.is_file():add(path,path.relative_to(project).as_posix(),'project')
    for job in jobs:
        for path in sorted((local/'runs'/job['id']).glob('*')):
            add(path,'@runs/'+job['id']+'/'+path.name,'runs',f"{job['id']} / {path.name}",'/api/jobs/'+job['id']+'/artifact/'+path.name)
    return {'root':str(project),'roots':{'workbench':str(root),'project':str(project),'runs':str(local/'runs')},'groups':[{'id':'workbench','name':'工作台代码与场景'},{'id':'runs','name':'任务输入与输出'},{'id':'project','name':'初始示例项目'}],'files':rows}

def resolve_file(root,project,local,key,lookup):
    url=None
    if key.startswith('@workbench/'):
        path=(root/key[len('@workbench/'):]).resolve()
        if not path.is_relative_to(root) or not code_allowed(root,path):raise HTTPException(403,'仅允许工作台代码目录')
    elif key.startswith('@runs/'):
        parts=key.split('/')
        if len(parts)!=3:raise HTTPException(403,'非法任务文件路径')
        lookup(parts[1]);base=(local/'runs'/parts[1]).resolve();path=(base/parts[2]).resolve()
        if not path.is_relative_to(base):raise HTTPException(403,'非法任务文件路径')
        url='/api/jobs/'+parts[1]+'/artifact/'+parts[2]
    else:
        path=(project/key).resolve()
        if not path.is_relative_to(project):raise HTTPException(403,'仅允许授权项目内文件')
    if not path.is_file() or path.suffix.lower() not in TEXT|IMAGE|RAW:raise HTTPException(403,'不支持的项目文件')
    return path,url

def read_file(root,project,local,key,lookup):
    path,url=resolve_file(root,project,local,key,lookup)
    kind='image' if path.suffix.lower() in IMAGE else 'raw' if path.suffix.lower() in RAW else 'text'
    if not url:url='/api/project/content?path='+quote(key,safe='')
    raw=b''
    if kind=='text':
        with path.open('rb') as stream:raw=stream.read(200001)
    return {'path':key,'kind':kind,'url':url,'size':path.stat().st_size,'content':raw[:200000].decode('utf-8',errors='replace'),'truncated':len(raw)>200000,'sha256':hashlib.sha256(raw[:200000]).hexdigest() if kind=='text' else ''}
