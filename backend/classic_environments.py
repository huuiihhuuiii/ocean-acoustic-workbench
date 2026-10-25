"""Explicit teaching environments; not observations or untouched AT fixtures."""
import json,hashlib
from pathlib import Path

def matched_munk():
    cfg=json.loads((Path(__file__).resolve().parents[1]/'.local/config.json').read_text(encoding='utf-8'))
    path=Path(cfg['toolbox_path'])/'tests/Munk/MunkK.env'
    raw=path.read_text(encoding='ascii').splitlines()
    stop=next(i for i,l in enumerate(raw) if l.strip().startswith("'A'"))
    points=[]
    for line in raw[5:stop]:
        values=line.split('!')[0].replace('/',' ').split()
        if len(values)<2:raise ValueError('Munk声速表格式异常')
        points.append({'depth_m':float(values[0]),'sound_speed_m_s':float(values[1])})
    bottom=[float(v) for v in raw[stop+1].replace('/',' ').split()]
    if points[0]['depth_m']!=0 or points[-1]['depth_m']!=5000:raise ValueError('Munk剖面范围异常')
    return {'ssp':points,'water_depth_m':5000.0,'water_density_g_cm3':float(raw[5].split()[3]),
        'bottom':{'speed_m_s':bottom[1],'density_g_cm3':bottom[3],'attenuation_db_wavelength':bottom[4]},
        'provenance':{'source':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},
        'assumptions':['模型对比/收敛场景使用AT Munk声速节点，统一采用C线性插值；与单次KRAKEN的原始N²线性模板不同。','同一水平分层平底、流体半空间海底及压力释放海面；不代表真实海域。']}

def prepare(plan):
    d=100.0 if plan.template=='pekeris_100m' else 5000.0
    if max(plan.source_depths_m)>=d or plan.receiver_depth_m>=d:
        raise ValueError(f'此算例声源和接收深度必须小于 {d:g} m')
    return {'ssp':[{'depth_m':0.0,'sound_speed_m_s':1500.0},{'depth_m':d,'sound_speed_m_s':1500.0}],
        'water_depth_m':d,'water_density_g_cm3':1.0,
        'bottom':{'speed_m_s':2000.0 if d==100 else 1600.0,'density_g_cm3':1.8,'attenuation_db_wavelength':0.0},
        'assumptions':['教学算例：1500 m/s 等声速水体、压力释放海面、流体半空间海底、平底。','Pekeris 为理想化浅海波导；等声速深水用于声线几何检查。','这些是明确设定的教学变体，不是原样运行的 AT 官方算例；不是实测海域。']}
