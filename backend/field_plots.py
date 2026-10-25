"""Display-only interpolation; original sample values and masks are retained."""
import numpy as np

def render(folder,data):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    x=np.asarray(data['ranges_m'],dtype=float)/1000;z=np.asarray(data['depths_m'],dtype=float);tl=np.asarray(data['tl_db'],dtype=float)
    if tl.shape!=(len(z),len(x)) or not np.isfinite(tl).any():raise ValueError('结果维度或有效值校验失败')
    cmap=plt.get_cmap('viridis_r').copy();cmap.set_bad('white')
    for smooth,name in [(False,'tl_map_grid'),(True,'tl_map')]:
        fig,ax=plt.subplots(figsize=(12,6),facecolor='white');fig.subplots_adjust(left=.09,right=.94,bottom=.16,top=.88)
        regular=np.allclose(np.diff(x),np.diff(x)[0],rtol=1e-4) and np.allclose(np.diff(z),np.diff(z)[0],rtol=1e-4)
        if smooth and regular:
            dx=(x[-1]-x[0])/(len(x)-1);dz=(z[-1]-z[0])/(len(z)-1)
            im=ax.imshow(np.ma.masked_invalid(tl),extent=(x[0]-dx/2,x[-1]+dx/2,z[-1]+dz/2,z[0]-dz/2),origin='upper',aspect='auto',interpolation='bilinear',interpolation_stage='data',cmap=cmap,vmin=40,vmax=110)
        else:
            im=ax.pcolormesh(x,z,np.ma.masked_invalid(tl),shading='auto',cmap=cmap,vmin=40,vmax=110)
        ax.set(xlabel='Range (km)',ylabel='Depth (m)',title=f"{data.get('solver','kraken').upper()} · {data['frequency_hz']:g} Hz · source {data['source_depth_m']:g} m",xlim=(x[0],x[-1]),ylim=(z[-1],z[0]))
        fig.colorbar(im,ax=ax,label='TL (dB)')
        fig.text(.09,.035,f"Computed grid: {len(z)} depths x {len(x)} ranges | "+('Display interpolation only; white = masked data' if smooth else 'Original computed samples; white = masked data'),fontsize=10,color='#637f89')
        fig.savefig(folder/(name+'.png'),dpi=220)
        if smooth:fig.savefig(folder/'tl_map.svg',dpi=220)
        plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,4),facecolor='white');ax.plot(x,data['curve_tl_db'],color='#07828c',lw=1.2);ax.set(xlabel='Range (km)',ylabel='TL (dB)',title=f"Receiver depth {data['actual_receiver_depth_m']:g} m");ax.grid(alpha=.16);fig.tight_layout();fig.savefig(folder/'tl_curve.png',dpi=220);plt.close(fig)
