from pathlib import Path
import zipfile,json,shutil
app=Path(__file__).resolve().parents[1]
target=Path.home()/'Documents/MATLAB/AcousticsToolbox'
target.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(app/'.local/at-input.zip') as z:
    for item in z.infolist():
        dest=(target/item.filename).resolve()
        if not dest.is_relative_to(target.resolve()):raise ValueError('Unsafe path')
        if item.is_dir():dest.mkdir(parents=True,exist_ok=True);continue
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and dest.stat().st_size==item.file_size:continue
        with z.open(item) as inp,dest.open('wb') as out:shutil.copyfileobj(inp,out)
cfgfile=app/'.local/config.json';cfg=json.loads(cfgfile.read_text(encoding='utf-8'));cfg['toolbox_path']=str(target/'at');cfgfile.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
matdir=target.parent
startup=matdir/'startup.m'
block="\n% BEGIN OCEAN AT TOOLBOX\nocean_at_root = '"+str(target/'at').replace('\\','/')+"';\naddpath(ocean_at_root, fullfile(ocean_at_root,'bin'), fullfile(ocean_at_root,'ReadWrite'), fullfile(ocean_at_root,'Plot'), fullfile(ocean_at_root,'Misc'), '-begin');\nclear ocean_at_root\n% END OCEAN AT TOOLBOX\n"
old=startup.read_text(encoding='utf-8') if startup.exists() else ''
if 'BEGIN OCEAN AT TOOLBOX' not in old:
    if startup.exists():shutil.copy2(startup,matdir/'startup.before_ocean_at.m.bak')
    startup.write_text(old+block,encoding='utf-8')
else:
    import re
    updated=re.sub(r'\n?% BEGIN OCEAN AT TOOLBOX.*?% END OCEAN AT TOOLBOX\n?',block,old,flags=re.S)
    startup.write_text(updated,encoding='utf-8')
print('Installed full AT toolbox:',target/'at')
print('Startup:',startup)
