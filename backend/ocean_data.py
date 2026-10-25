"""Read local WOA18 and ETOPO1 without copying the multi-GB archive."""
from pathlib import Path
import threading,os,json
import numpy as np
from netCDF4 import Dataset
import gsw

LOCAL=Path(os.environ.get('OCEAN_RUNTIME_DIR',str(Path(__file__).absolute().parents[1]/'.local')))
CONFIG=LOCAL/'config.json'
SETTINGS=json.loads(CONFIG.read_text(encoding='utf-8')) if CONFIG.is_file() else {}
ROOT=Path(os.environ.get('OCEAN_DATA_DIR',SETTINGS.get('ocean_data_path',str(LOCAL/'ocean-data'))))
LOCK=threading.Lock() # netCDF/HDF5 operations must not overlap across request threads.
PERIODS=[{'id':0,'label':'年平均'}]+[{'id':m,'label':f'{m}月'} for m in range(1,13)]+[{'id':m,'label':label} for m,label in [(13,'1—3月'),(14,'4—6月'),(15,'7—9月'),(16,'10—12月')]]

def catalog():
    files=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'bytes':p.stat().st_size} for p in ROOT.rglob('*') if p.is_file() and p.suffix in ('.nc','.grd','.gz','.tif')]
    return {'available':len(files)==39,'files':files,'count':len(files),'bytes':sum(f['bytes'] for f in files),'periods':PERIODS,'name':'WOA18 温盐气候场与 ETOPO1 海底地形','path':str(ROOT.resolve()),'method':'TEOS-10：深度→海水压力，实用盐度→绝对盐度，原位温度→声速（完整 Gibbs 函数）'}

def terrain(lon,lat):
    with Dataset(str(ROOT/'terrain/ETOPO1_Bed_g_gmt4.grd')) as ds:
        x=np.asarray(ds['x'][:]);y=np.asarray(ds['y'][:]);ix=int(np.argmin(abs(x-lon)));iy=int(np.argmin(abs(y-lat)))
        return {'lon':float(x[ix]),'lat':float(y[iy]),'elevation_m':float(ds['z'][iy,ix])}

def terrain_map(west=95,east=145,south=-5,north=45):
    if not np.isfinite([west,east,south,north]).all() or not (-180<=west<east<=180 and -90<=south<north<=90):raise ValueError('地图经纬范围无效')
    if east-west<.1 or north-south<.1:raise ValueError('地图范围不能小于0.1度')
    with LOCK:
        with Dataset(str(ROOT/'terrain/ETOPO1_Bed_g_gmt4.grd')) as ds:
            x=np.asarray(ds['x'][:]);y=np.asarray(ds['y'][:])
            ix0=max(0,int(np.searchsorted(x,west)));ix1=min(len(x)-1,int(np.searchsorted(x,east)))
            iy0=max(0,int(np.searchsorted(y,south)));iy1=min(len(y)-1,int(np.searchsorted(y,north)))
            sx=max(1,int(np.ceil((ix1-ix0)/240)));sy=max(1,int(np.ceil((iy1-iy0)/160)))
            xs=slice(ix0,ix1+1,sx);ys=slice(iy0,iy1+1,sy)
            z=np.ma.filled(ds['z'][ys,xs],np.nan).astype(float)
            return {'lons':x[xs].tolist(),'lats':y[ys].tolist(),'elevation_m':[[float(v) if np.isfinite(v) else None for v in row] for row in z], 'source':'ETOPO1 基岩高程（m，相对海平面）','note':'地图为降采样预览；点选后按原始地形网格读取，温盐采用最近1°格点。'}

def profile(lon,lat,period):
    if not np.isfinite([lon,lat]).all() or not -180<=lon<=180 or not -90<=lat<=90 or period not in range(17):raise ValueError('经纬度或时段超出范围')
    lon=-180. if lon==180 else lon
    with LOCK:
        if not ROOT.is_dir():raise FileNotFoundError('未连接本地海洋环境数据目录')
        tp=list(ROOT.rglob(f'woa18_A5B7_t{period:02d}_01.nc'));sp=list(ROOT.rglob(f'woa18_A5B7_s{period:02d}_01.nc'))
        if len(tp)!=1 or len(sp)!=1:raise FileNotFoundError('温盐配对文件缺失或重复')
        bottom=terrain(lon,lat)
        if bottom['elevation_m']>=0:raise ValueError('该坐标的 ETOPO1 网格为陆地，请选择海洋位置')
        with Dataset(str(tp[0])) as t,Dataset(str(sp[0])) as s:
            lats=np.asarray(t['lat'][:]);lons=np.asarray(t['lon'][:]);ix=int(np.argmin(abs((lons-lon+180)%360-180)));iy=int(np.argmin(abs(lats-lat)))
            if not np.array_equal(t['depth'][:],s['depth'][:]) or not np.array_equal(lats,s['lat'][:]) or not np.array_equal(lons,s['lon'][:]):raise ValueError('温盐文件网格不一致')
            depth=np.asarray(t['depth'][:],dtype=float)
            temp=np.ma.filled(t['t_an'][0,:,iy,ix],np.nan);sal=np.ma.filled(s['s_an'][0,:,iy,ix],np.nan)
            selected={'lon':float(lons[ix]),'lat':float(lats[iy])}
        cell_bottom=terrain(selected['lon'],selected['lat'])
    if cell_bottom['elevation_m']>=0:raise ValueError('最近的1°温盐网格位于陆地，未自动跨海岸寻找其他剖面')
    mask=np.isfinite(temp)&np.isfinite(sal)&(depth<=-cell_bottom['elevation_m'])
    if mask.sum()<2:raise ValueError('最近的温盐网格有效层不足，可能位于陆地或沿岸缺测区')
    z=depth[mask];tv=temp[mask];sv=sal[mask]
    pressure=gsw.p_from_z(-z,selected['lat'])
    absolute=gsw.SA_from_SP(sv,pressure,selected['lon'],selected['lat'])
    speed=gsw.sound_speed_t_exact(absolute,tv,pressure)
    if not np.isfinite(speed).all():raise ValueError('声速计算存在无效值')
    rows=[dict(zip(['depth_m','temperature_c','practical_salinity','pressure_dbar','absolute_salinity_g_kg','sound_speed_m_s'],map(float,values))) for values in zip(z,tv,sv,pressure,absolute,speed)]
    return {'requested':{'lon':lon,'lat':lat},'selected':selected,'period':PERIODS[period]['label'],'period_id':period,'rows':rows,'missing_depths_m':depth[~(np.isfinite(temp)&np.isfinite(sal))].tolist(),'bottom':bottom,'grid_bottom':cell_bottom,'depth_limit_m':float(z[-1]),'missing_or_excluded_layers':int(len(depth)-mask.sum()),'temperature_file':str(tp[0].relative_to(ROOT)).replace('\\','/'),'salinity_file':str(sp[0].relative_to(ROOT)).replace('\\','/'),'method':'TEOS-10 / GSW sound_speed_t_exact','warnings':['2005—2017年温盐气候平均场，非实时观测。','采用最近1°温盐格点，不进行空间插值；地形来自1角分ETOPO1基岩版本。','只保留有效且不深于温盐格点海底的层；未填补缺测，未外推到海底。','单点环境剖面不包含传播路径、海底声学参数和声源接收设置，尚不能直接代替完整仿真环境。']}
