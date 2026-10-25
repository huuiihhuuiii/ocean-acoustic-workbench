"""Validated, numeric-only, range-independent WOA18 KRAKEN environment."""
import numpy as np
import ocean_data

def prepare(plan):
    data=ocean_data.profile(plan.longitude,plan.latitude,plan.period)
    rows=data['rows'];depth=np.array([r['depth_m'] for r in rows]);speed=np.array([r['sound_speed_m_s'] for r in rows])
    limit=min(data['depth_limit_m'],-data['bottom']['elevation_m'],-data['grid_bottom']['elevation_m'])
    if depth[0]!=0:raise ValueError('剖面缺少海面层，不能生成环境')
    if plan.water_depth_m>limit:raise ValueError(f'所设水深超过有效环境范围 {limit:g} m；不外推剖面，请缩小水深或换用年/季节数据')
    if any(z<plan.water_depth_m for z in data.get('missing_depths_m',[])):raise ValueError('所设水深内存在缺测层，不能跨缺测生成环境')
    if max(plan.source_depths_m)>=plan.water_depth_m or plan.receiver_depth_m>=plan.water_depth_m:raise ValueError('声源和接收深度必须小于所设水深')
    inside=depth<plan.water_depth_m
    points=[{'depth_m':float(z),'sound_speed_m_s':float(c)} for z,c in zip(depth[inside],speed[inside])]
    points.append({'depth_m':plan.water_depth_m,'sound_speed_m_s':float(np.interp(plan.water_depth_m,depth,speed))})
    if getattr(plan,'solver','kraken')=='kraken' and plan.bottom_speed_m_s<=max(p['sound_speed_m_s'] for p in points):raise ValueError('当前流体半空间模板要求海底声速高于水体最大声速，以计算可俘获模态')
    return {'profile':data,'ssp':points,'water_depth_m':plan.water_depth_m,'water_density_g_cm3':1.025,'bottom':{'speed_m_s':plan.bottom_speed_m_s,'density_g_cm3':plan.bottom_density_g_cm3,'attenuation_db_wavelength':plan.bottom_attenuation},'assumptions':['水平分层、距离无关，沿整个距离使用同一剖面和平底。','海面压力释放，水体常密度1.025 g/cm³，水体吸收取0；海底为均匀流体半空间。','海底参数为用户设定，不来自WOA18/ETOPO1。','所设水深可小于ETOPO1水深，这是截断的教学环境，不代表完整真实海底。']}

def env_text(environment,frequency,source_depth,depth_points):
    d=environment['water_depth_m'];ssp=environment['ssp'];bottom=environment['bottom'];density=environment['water_density_g_cm3']
    # C: piecewise-linear SSP, V: pressure-release surface, W: dB/wavelength.
    lines=["'Custom range-independent environment'",f'{frequency:.9g}','1',"'CVW'",f'0 0.0 {d:.9g}']
    lines += [f"{p['depth_m']:.9g} {p['sound_speed_m_s']:.12g} 0.0 {density:.9g} 0.0 0.0 /" for p in ssp]
    lines += ["'A' 0.0",f"{d:.9g} {bottom['speed_m_s']:.9g} 0.0 {bottom['density_g_cm3']:.9g} {bottom['attenuation_db_wavelength']:.9g} 0.0 /",f"{min(p['sound_speed_m_s'] for p in ssp)*.9:.9g} {bottom['speed_m_s']:.9g}",'0.0 ! RMAX','1 ! NSD',f'{source_depth:.9g} / ! SD',f'{depth_points} ! NRD',f'0.0 {d:.9g} / ! RD']
    return '\n'.join(lines)+'\n'
