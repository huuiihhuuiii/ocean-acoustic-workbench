"""Read actual AT output and render diagnostic results without UI dependencies."""
import json,re
import numpy as np

def field_metadata(folder,data):
    if data.get('solver')=='scooter':
        text=(folder/'case.prt').read_text(encoding='ascii',errors='replace')
        mesh=re.search(r'Number mesh points auto calc\.\s*=\s*(\d+)',text)
        nk=re.search(r'Nk\s*=\s*(\d+)',text)
        data['mesh_points_actual']=int(mesh.group(1)) if mesh else data.get('mesh_points_requested')
        if nk:data['wavenumber_samples']=int(nk.group(1))
        return
    if data.get('solver','kraken')!='kraken' or not (folder/'case.flp').is_file():return
    lines=(folder/'case.flp').read_text(encoding='ascii').splitlines()
    match=re.search(r"'([^']+)'",lines[1]) if len(lines)>1 else None
    if not match:return
    option=match.group(1)
    addition='incoherent' if len(option)>3 and option[3]=='I' else 'coherent'
    data.update(field_options=option,mode_addition=addition,reference=f'AT FIELD normalized amplitude; TL = -20 log10 |p|; {addition} modal addition ({option})')

def read_rays(path):
    lines=path.read_text(encoding='ascii').splitlines()
    frequency=float(lines[1]);sources=[int(x) for x in lines[2].split()];beams=[int(x) for x in lines[3].split()]
    if sources!=[1,1,1] or beams[1]!=1 or lines[6].strip().strip("'")!='rz':raise ValueError('不支持的声线文件维度')
    tokens=iter(' '.join(lines[7:]).split());rays=[]
    for _ in range(beams[0]):
        angle=float(next(tokens));steps=int(next(tokens));top=int(next(tokens));bottom=int(next(tokens))
        if not 2<=steps<=1000000:raise ValueError('声线步数无效')
        points=np.array([[float(next(tokens)),float(next(tokens))] for _ in range(steps)])
        if not np.isfinite(points).all():raise ValueError('声线含非有限坐标')
        rays.append({'angle_deg':angle,'surface_bounces':top,'bottom_bounces':bottom,'ranges_m':points[:,0].tolist(),'depths_m':points[:,1].tolist()})
    if next(tokens,None) is not None:raise ValueError('声线文件存在未解析数据')
    return frequency,rays

def extra_plots(folder,data):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    if data.get('solver')=='bellhop' and 'tl_db' not in data:
        f,rays=read_rays(folder/'rays.ray')
        if abs(f-data['frequency_hz'])>1e-4:raise ValueError('声线频率不一致')
        fig,ax=plt.subplots(figsize=(10,5),facecolor='#f6fafb')
        for r in rays:
            color='#cf8b3b' if r['bottom_bounces'] else '#07828c' if r['surface_bounces'] else '#5074ba'
            ax.plot(np.array(r['ranges_m'])/1000,r['depths_m'],color=color,alpha=.6,lw=.7)
        ax.set(xlabel='Range (km)',ylabel='Depth (m)',title=f"BELLHOP · {len(rays)} rays · source {data['source_depth_m']:g} m",ylim=(data['water_depth_m'],0));ax.grid(alpha=.15)
        fig.tight_layout();fig.savefig(folder/'rays.png',dpi=150);plt.close(fig)
        data.update(ray_count=len(rays),surface_reflected_rays=sum(r['surface_bounces']>0 for r in rays),bottom_reflected_rays=sum(r['bottom_bounces']>0 for r in rays))
        (folder/'rays.json').write_text(json.dumps({'frequency_hz':f,'rays':rays}),encoding='utf-8')
        return
    if not (folder/'modes.json').exists():return
    m=json.loads((folder/'modes.json').read_text());z=np.array(m['depths_m']);phi=np.array(m['shape_real'])
    # MATLAB jsonencode collapses singleton dimensions and scalar vectors.
    if m['displayed_count']==1 and phi.shape==(len(z),):phi=phi[:,None]
    if phi.shape!=(len(z),m['displayed_count']) or not np.isfinite(phi).all():raise ValueError('模态形状维度无效')
    fig,axes=plt.subplots(1,m['displayed_count'],figsize=(10,5),sharey=True,facecolor='#f6fafb')
    for i,ax in enumerate(np.atleast_1d(axes)):
        scale=np.max(np.abs(phi[:,i]));ax.plot(phi[:,i]/scale if scale else phi[:,i],z,color='#07828c');ax.axvline(0,color='#b7c9ce',lw=.5);ax.set(title=f'Mode {i+1}',xlim=(-1.1,1.1));ax.grid(alpha=.12)
    np.atleast_1d(axes)[0].set(ylabel='Depth (m)',ylim=(data['water_depth_m'],0));fig.suptitle('First modes · real part, individually normalized for display');fig.tight_layout();fig.savefig(folder/'modes.png',dpi=150);plt.close(fig)
    wave=np.atleast_1d(m['wavenumber_real_rad_m'])
    if wave.ndim!=1 or len(wave)!=m['count'] or not np.isfinite(wave).all():raise ValueError('模态波数维度无效')
    fig,ax=plt.subplots(figsize=(10,3.5),facecolor='#f6fafb');ax.plot(np.arange(1,len(wave)+1),wave,color='#07828c',marker='.' if len(wave)==1 else None);ax.set(xlabel='Mode index',ylabel='Re(k) (rad/m)',title='Horizontal modal wavenumbers');ax.grid(alpha=.15);fig.tight_layout();fig.savefig(folder/'wavenumbers.png',dpi=150);plt.close(fig)
