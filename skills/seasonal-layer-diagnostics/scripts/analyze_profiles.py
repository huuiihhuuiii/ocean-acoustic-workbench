"""Reproducible climatological layer diagnostics, independent of an LLM/provider."""
import argparse,csv,json,sys
from pathlib import Path
import numpy as np
import gsw

def crossing(depth,departure,threshold):
    hits=np.flatnonzero(departure>=threshold)
    if not len(hits):return {'depth_m':None,'status':'not_crossed','observed_to_m':float(depth[-1])}
    i=int(hits[0])
    value=depth[i] if i==0 else depth[i-1]+(depth[i]-depth[i-1])*(threshold-departure[i-1])/(departure[i]-departure[i-1])
    return {'depth_m':float(value),'status':'crossed'}

def diagnose(profile,reference=10.,density_threshold=.03,temperature_threshold=.2):
    if reference<0 or density_threshold<=0 or temperature_threshold<=0:raise ValueError('Invalid diagnostic thresholds')
    rows=profile['rows'];z=np.array([r['depth_m'] for r in rows],dtype=float)
    if len(z)<2 or not np.isfinite(z).all() or np.any(np.diff(z)<=0):raise ValueError('Depth must be finite and strictly increasing')
    missing=[d for d in profile.get('missing_depths_m',[]) if z[0]<=d<=z[-1]]
    if missing:
        cutoff=min(missing);rows=[r for r in rows if r['depth_m']<cutoff];z=np.array([r['depth_m'] for r in rows],dtype=float)
    result={'requested':profile.get('requested'),'selected':profile.get('selected'),'period_id':profile.get('period_id'),'period':profile.get('period'),'reference_depth_m':reference,'density_threshold_kg_m3':density_threshold,'temperature_threshold_c':temperature_threshold,'internal_missing_cutoff_m':min(missing) if missing else None}
    if len(z)<2 or z[0]>reference or z[-1]<=reference:
        return {**result,'density_mld':{'depth_m':None,'status':'insufficient_reference'},'temperature_mld':{'depth_m':None,'status':'insufficient_reference'},'surface_duct':{'depth_m':None,'status':'insufficient_profile'}}
    temperature=np.array([r['temperature_c'] for r in rows]);sal=np.array([r['practical_salinity'] for r in rows]);sound=np.array([r['sound_speed_m_s'] for r in rows]);pos=profile['selected']
    if not np.isfinite([temperature,sal,sound]).all():raise ValueError('Profile contains nonfinite values')
    pressure=gsw.p_from_z(-z,pos['lat']);sa=gsw.SA_from_SP(sal,pressure,pos['lon'],pos['lat']);ct=gsw.CT_from_t(sa,temperature,pressure);sigma=gsw.sigma0(sa,ct);pt=gsw.pt0_from_t(sa,temperature,pressure)
    ref_sigma=float(np.interp(reference,z,sigma));ref_pt=float(np.interp(reference,z,pt));zz=np.r_[reference,z[z>reference]];dd=np.r_[0,sigma[z>reference]-ref_sigma];dt=np.r_[0,np.abs(pt[z>reference]-ref_pt)]
    result.update(density_mld=crossing(zz,dd,density_threshold),temperature_mld=crossing(zz,dt,temperature_threshold))
    slope=np.diff(sound)/np.diff(z)
    if z[0]!=0:duct={'depth_m':None,'status':'missing_surface'}
    elif slope[0]<=1e-6:duct={'depth_m':None,'status':'no_surface_connected_positive_gradient'}
    else:
        stop=np.flatnonzero(slope<=1e-6)
        duct={'depth_m':float(z[int(stop[0])]),'status':'candidate_local_maximum','sound_speed_increase_m_s':float(sound[int(stop[0])]-sound[0])} if len(stop) else {'depth_m':None,'status':'positive_gradient_unclosed','observed_to_m':float(z[-1])}
    result['surface_duct']=duct;result['note']='Climatological threshold diagnostics; candidate sound-speed duct is not proof of acoustic trapping.'
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profiles');parser.add_argument('--lon',type=float);parser.add_argument('--lat',type=float);parser.add_argument('--periods',default='13,14,15,16');parser.add_argument('--out-dir',required=True);args=parser.parse_args()
    if args.profiles:profiles=json.loads(Path(args.profiles).read_text(encoding='utf-8-sig'))
    else:
        if args.lon is None or args.lat is None:parser.error('Use --profiles or both --lon and --lat')
        sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'backend'));import ocean_data
        profiles=[ocean_data.profile(args.lon,args.lat,int(p)) for p in args.periods.split(',')]
    if not profiles:raise ValueError('No profiles')
    results=[diagnose(p) for p in profiles];out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
    (out/'profiles.json').write_text(json.dumps(profiles,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (out/'layer_metrics.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    with (out/'layer_metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['lon','lat','period','density_mld_m','density_status','temperature_mld_m','temperature_status','duct_candidate_m','duct_status'])
        for r in results:w.writerow([r['selected']['lon'],r['selected']['lat'],r['period_id'],r['density_mld']['depth_m'],r['density_mld']['status'],r['temperature_mld']['depth_m'],r['temperature_mld']['status'],r['surface_duct']['depth_m'],r['surface_duct']['status']])
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    labels=[str(r['period_id']) for r in results];fig,ax=plt.subplots(figsize=(8,4))
    for key,label in [('density_mld','Density MLD'),('temperature_mld','Temperature MLD'),('surface_duct','Duct candidate')]:
        ax.plot(range(len(results)),[r[key]['depth_m'] if r[key]['depth_m'] is not None else np.nan for r in results],marker='o',label=label)
    ax.set(xticks=range(len(labels)),xticklabels=labels,xlabel='WOA period (13-16: seasons)',ylabel='Depth (m)',title='Climatological layer diagnostics');ax.invert_yaxis();ax.legend();fig.tight_layout();fig.savefig(out/'seasonal_layers.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(12,5),sharey=True)
    for p in profiles:
        for ax,key in zip(axes,['temperature_c','practical_salinity','sound_speed_m_s']):ax.plot([r[key] for r in p['rows']],[r['depth_m'] for r in p['rows']],label=str(p['period_id']))
    for ax,title in zip(axes,['Temperature (C)','Practical salinity','Sound speed (m/s)']):ax.set(xlabel=title,ylim=(min(300,max(p['rows'][-1]['depth_m'] for p in profiles)),0));ax.grid(alpha=.2)
    axes[0].set_ylabel('Depth (m)');axes[-1].legend(title='WOA period');fig.tight_layout();fig.savefig(out/'seasonal_profiles.png',dpi=150);plt.close(fig)
    print(json.dumps({'out_dir':str(out),'profiles':len(results),'metrics':results},ensure_ascii=False))

if __name__=='__main__':main()
