"""Read this AT build's RAM sequential-unformatted TL grid, checking each record.

The grid contains TL, not complex pressure: phase cannot be reconstructed.
For this executable, sample i=ndz has physical depth (ndz-1)*dz.
The local AT MATLAB reader labels these one dz deeper; a zr=1 m probe
independently confirms the offset for this build. Other RAM builds need a probe.
"""
import argparse,json,struct
from pathlib import Path
import numpy as np

def read_grid(path):
    with Path(path).open('rb') as f:
        marker=f.read(4)
        if len(marker)!=4:raise ValueError('Missing RAM header')
        endian=next((e for e in ('<','>') if struct.unpack(e+'i',marker)[0]==60),None)
        if endian is None:raise ValueError('Unsupported RAM header: expected 4-byte markers and 60-byte payload')
        header=f.read(60);tail=f.read(4)
        if len(header)!=60 or len(tail)!=4 or struct.unpack(endian+'i',tail)[0]!=60:raise ValueError('Truncated RAM header or mismatched marker')
        names=['frequency_hz','source_depth_m','receiver_depth_m','range_max_m','dr_m','ndr','zmax_m','dz_m','ndz','zmplt_m','c0_m_s','pade_terms','stability_terms','stability_range_m','depth_count']
        meta=dict(zip(names,struct.unpack(endian+'5fi2fi2f2ifi',header)))
        nz=meta['depth_count'];step=meta['dr_m']*meta['ndr'];dz=meta['dz_m']*meta['ndz']
        if not np.isfinite(list(meta.values())).all() or not 0<nz<=100000 or min(step,dz)<=0 or meta['range_max_m']<=0:raise ValueError('Invalid RAM grid dimensions')
        columns=[]
        while True:
            begin=f.read(4)
            if not begin:break
            if len(begin)!=4 or struct.unpack(endian+'i',begin)[0]!=nz*4:raise ValueError('RAM range record marker mismatch')
            payload=f.read(nz*4);end=f.read(4)
            if len(payload)!=nz*4 or len(end)!=4 or struct.unpack(endian+'i',end)[0]!=nz*4:raise ValueError('Truncated RAM range record')
            columns.append(np.frombuffer(payload,dtype=endian+'f4').astype(float))
            if len(columns)*nz>50000000:raise ValueError('RAM grid too large for this reader')
        expected=int(np.floor(meta['range_max_m']/step+1e-5))
        if not columns or len(columns)!=expected:raise ValueError(f'RAM range count mismatch: {len(columns)} != {expected}')
    return {'metadata':meta,'ranges_m':np.arange(1,len(columns)+1)*step,'depths_m':np.arange(1,nz+1)*dz-meta['dz_m'],'at_matlab_nominal_depths_m':np.arange(1,nz+1)*dz,'tl_db':np.stack(columns,axis=1)}

def export(path,output):
    data=read_grid(path);out=Path(output);out.mkdir(parents=True,exist_ok=True)
    tl=data['tl_db'];finite=np.isfinite(tl)
    if not finite.any():raise ValueError('RAM output has no finite TL')
    summary={**data['metadata'],'shape':list(tl.shape),'finite_ratio':float(finite.mean()),'first_depth_m':float(data['depths_m'][0]),'first_range_m':float(data['ranges_m'][0]),'tl_min_db':float(np.min(tl[finite])),'tl_max_db':float(np.max(tl[finite])),'depth_convention':'Physical depth (sample_index*ndz-1)*dz; differs by -dz from local MATLAB reader; verified for current executable by receiver-depth probe.','note':'TL output only; no phase, not a complex-pressure SHD reconstruction.'}
    line=Path(path).with_name('tl.line')
    if line.exists():
        curve=np.loadtxt(line,ndmin=2);z=data['metadata']['receiver_depth_m'];k=int(np.argmin(abs(data['depths_m']-z)))
        if len(curve)==len(data['ranges_m']) and np.allclose(curve[:,0],data['ranges_m'],atol=.01) and abs(data['depths_m'][k]-z)<1e-4:
            valid=np.isfinite(curve[:,1])&np.isfinite(tl[k]);summary['line_grid_max_abs_db']=float(np.max(abs(curve[valid,1]-tl[k,valid]))) if valid.any() else None
            summary['line_grid_compared_points']=int(valid.sum())
    np.savez_compressed(out/'ram_grid.npz',ranges_m=data['ranges_m'],depths_m=data['depths_m'],tl_db=tl)
    (out/'ram_summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False),encoding='utf-8')
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(9,5));vmin,vmax=np.percentile(tl[finite],[2,98]);img=ax.pcolormesh(data['ranges_m']/1000,data['depths_m'],tl,shading='auto',cmap='viridis_r',vmin=vmin,vmax=vmax);ax.invert_yaxis();ax.set(xlabel='Range (km)',ylabel='Depth (m)',title='RAM transmission loss (display limits: P2-P98)');fig.colorbar(img,ax=ax,label='TL (dB)');fig.tight_layout();fig.savefig(out/'ram_tl.png',dpi=150);plt.close(fig)
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('grid');parser.add_argument('--out-dir',required=True);args=parser.parse_args();print(json.dumps(export(args.grid,args.out_dir),ensure_ascii=False))
