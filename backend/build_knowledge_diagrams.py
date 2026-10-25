from pathlib import Path
import json,math,html
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'public/assets/knowledge';OUT.mkdir(parents=True,exist_ok=True)
def text(x,y,s,size=15,color='#314967',anchor='start'):
 return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}">{html.escape(s)}</text>'
def line(x1,y1,x2,y2,color='#b4c6d9',dash='',arrow=False):
 return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2" stroke-dasharray="{dash}"'+(' marker-end="url(#arrow)"' if arrow else '')+'/>'
def box(x,y,w,h,label,sub='',color='#2f83cd'):
 return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{color}10" stroke="{color}"/>'+text(x+w/2,y+29,label,17,color,'middle')+text(x+w/2,y+53,sub,12,'#637c92','middle')
def save(name,title,subtitle,body):
 svg=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 440"><defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#7c99b5"/></marker></defs><rect width="760" height="440" rx="16" fill="#f6faff"/><g font-family="Microsoft YaHei,Segoe UI,sans-serif">{text(28,40,title,23,'#183b61')}{text(28,65,subtitle,12,'#7a90a6')}{body}{line(28,405,732,405,'#dfebf4')}{text(28,425,'课程原理示意 · 不作为求解器计算结果',11,'#879aac')}</g></svg>'''
 (OUT/(name+'.svg')).write_text(svg,encoding='utf-8')
body=box(35,155,185,76,'声压 p','压力扰动 · Pa')+box(285,155,185,76,'声阻抗 Z = ρc','介质性质')+box(535,155,185,76,'声强 I','能量流率 · W/m²')
body+=line(230,193,272,193,arrow=True)+line(480,193,522,193,arrow=True)+text(380,290,'平面行波： I = pᵣₘₛ² / (ρc)',25,'#267dbe','middle')+text(380,337,'声压与声强换算，必须保留介质与参考约定',14,'#637c92','middle')
save('quantities','声学量之间的关系','以平面行波为例；一般复声场须考虑声压与速度的相位关系。',body)
body=line(78,346,706,346,arrow=True)+line(78,346,78,95,arrow=True)+text(360,382,'距离 r（对数坐标）',14)+text(24,123,'TL',16)
for i in range(4):body+=line(78,346-i*60,696,346-i*60,'#e0ebf4')
body+='<path d="M90 340 L660 120" fill="none" stroke="#5c86e2" stroke-width="4"/><path d="M90 340 L660 230" fill="none" stroke="#2db89d" stroke-width="4"/>'
body+=text(407,147,'球面扩展：20 log₁₀ r',18,'#5c86e2')+text(400,279,'柱面远场斜率：10 log₁₀ r',17,'#259d86')+text(110,113,'理想几何扩展；不含吸收与反射损失',12,'#637c92')
save('spreading','传播损失与几何扩展','比较的是理想扩展斜率；真实波导的参考、过渡与损耗应另行处理。',body)
cfg=json.loads((ROOT/'.local/config.json').read_text(encoding='utf-8'))
env=Path(cfg['toolbox_path'])/'tests/Munk/MunkK.env';rows=[]
for row in env.read_text(encoding='utf-8').splitlines()[5:]:
 if row.startswith("'A'"):break
 try:
  vals=row.replace('/','').split();rows.append((float(vals[0]),float(vals[1])))
 except (ValueError,IndexError):pass
points=' '.join(f'{95+(c-1490)*5.6:.1f},{105+z/5000*265:.1f}' for z,c in rows)
body=line(95,100,95,373,arrow=True)+line(95,100,475,100,arrow=True)+text(178,87,'声速 c（m/s）',14)+text(26,119,'深度',13)
for z in [0,1000,2000,3000,4000,5000]:
 y=105+z/5000*265;body+=line(95,y,473,y,'#e5edf6')+text(84,y+4,str(z),11,'#7b8fa4','end')
for c in [1490,1510,1530,1550]:body+=text(95+(c-1490)*5.6,391,str(c),11,'#7b8fa4','middle')
body+=f'<polyline points="{points}" fill="none" stroke="#338db4" stroke-width="4"/>'+box(505,134,222,75,'Munk 输入剖面','读取教师包 ENV 离散数据','#338db4')+text(517,249,'约 1300 m 附近形成声速极小区',12)+text(517,280,'声道轴附近：低声速区',13,'#288daf')+text(517,309,'离开轴线：声速增大',13)+text(517,361,'此图展示环境输入，不是声场输出',11,'#879aac')
save('ssp','声速剖面与深海声道','曲线直接读取 at/tests/Munk/MunkK.env；深度向下增加。',body)
body='<rect x="70" y="125" width="620" height="195" fill="#e4f5ff"/><rect x="70" y="320" width="620" height="65" fill="#ede1cd"/>'
body+=line(70,125,690,125,'#48a5c7')+line(70,320,690,320,'#bd9661')+text(80,111,'理想压力释放海面：p = 0',16,'#2682ac')+text(80,352,'理想刚性底：∂p/∂n = 0',16,'#9a754b')
body+='<circle cx="195" cy="230" r="9" fill="#2a9fbf"/><circle cx="565" cy="230" r="9" fill="#7d74d3"/>'+text(165,263,'声源',14)+text(540,263,'接收器',14)+line(217,230,542,230,'#92b6cc','5 5',True)+text(384,199,'水层中的声场',17,'#527c98','middle')
save('boundary','海面与海底边界','两种理想边界用于解释原理；真实吸收/弹性海底需采用相应介质条件。',body)
body=box(281,97,195,68,'Helmholtz 方程','频域传播问题','#688ad8')
for x,label,sub,color in [(30,'简正波','垂向模态展开','#9d7bce'),(281,'射线 / 波束','轨迹与有限宽波束','#398eb8'),(532,'抛物方程','沿距离步进近似','#b99452')]:
 body+=line(380,172,x+97,241,arrow=True)+box(x,244,195,82,label,sub,color)
body+=text(380,370,'环境、边界、频率与精度目标共同决定方法选择',14,'#637c92','middle')
save('methods','三类传播方法的共同出发点','不同展开、近似和数值实现有各自适用条件；不能只凭模型名称判断准确性。',body)
body=line(90,112,665,112,'#49a7c4')+line(90,342,665,342,'#bf9a68')
colors=['#6595dd','#ad81d3','#50b4a4']
for i,col in enumerate(colors,1):
 pts=' '.join(f'{180+(i-1)*165+45*math.sin(i*math.pi*j/80):.1f},{112+230*j/80:.1f}' for j in range(81))
 body+=f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="3"/>'+text(180+(i-1)*165,371,f'示意模态 {i}',13,col,'middle')
body+=line(92,208,650,208,'#b495c3','4 4')+text(670,213,'源深',13)+text(380,95,'声源所在深度改变各模态激发权重',14,'#637c92','middle')
save('modes','源深与模态激发','这里使用理想形状示意，不是 Munk 求解器输出的实际模态函数。',body)
body='<rect x="50" y="118" width="660" height="230" fill="#e9f5fd"/>'+line(50,118,710,118,'#78b7d2')+line(50,348,710,348,'#bc9c79')
body+='<circle cx="95" cy="236" r="7" fill="#377ea6"/>'
for dy,color in [(-85,'#7d85cd'),(0,'#379eab'),(85,'#bca04e')]:body+=f'<path d="M95 236 C240 {236+dy},330 {236+dy},425 236 S620 {236-dy},695 236" fill="none" stroke="{color}" stroke-width="3"/>'
body+=text(67,276,'声源',13)+text(380,94,'声速结构改变传播轨迹',16,'#4c7596','middle')+text(380,379,'相对水平的掠射角：cos θ / c = 常数',17,'#368ba2','middle')
save('rays','声线折射与多路径','仅作轨迹原理示意；焦散、阴影和衍射不能由此图定量判断。',body)
body=''
for x,label,sub in [(25,'ENV','环境与频率'),(272,'KRAKEN','模态计算'),(519,'MOD','模态文件')]:body+=box(x,122,210,72,label,sub)
for x,label,sub in [(25,'FLP','源与接收网格'),(272,'FIELD','接收声场'),(519,'SHD → TL','复声压与损失')]:body+=box(x,278,210,72,label,sub,'#b8904c')
body+=line(240,158,259,158,arrow=True)+line(487,158,506,158,arrow=True)+line(240,314,259,314,arrow=True)+line(487,314,506,314,arrow=True)+line(624,201,395,264,arrow=True)
save('pipeline','AT 声场计算的输入输出','本包 kraken.m 串联 kraken.exe 与 field.exe；每次网页任务保存独立输入和输出。',body)
body=line(95,103,674,103,arrow=True)+line(95,103,95,350,arrow=True)
for i in range(9):body+=line(95+i*64,110,95+i*64,350,'#d9e5ef')
for i in range(6):body+=line(95,110+i*48,664,110+i*48,'#d9e5ef')
body+=line(95,206,664,206,'#638ec7')+text(349,85,'距离 r →',15)+text(20,132,'深度 z',13)+text(685,211,'接收层',12,'#638ec7')+text(380,386,'请求深度 → 最近网格深度 → 提取该层曲线',17,'#577897','middle')
save('grid','距离—深度采样与接收曲线','输出采样密度不等于求解器内部数值误差；须记录实际接收深度和单位。',body)
body=box(25,158,210,82,'CTD 观测','温度 · 盐度 · 深度','#40a496')+box(273,158,210,82,'声速剖面','公式 · 单位 · 站位','#658ad0')+box(521,158,210,82,'模型环境','边界 · 源 · 接收条件','#b18bc8')
body+=line(240,199,260,199,arrow=True)+line(488,199,508,199,arrow=True)+text(380,302,'历史报告图片 ≠ 原始数据文件 ≠ 当前海域实测环境',17,'#617d99','middle')+text(380,354,'ASIAEX 2001 / SW06 2006：保留实验年份与站位上下文',13,'#8b9eaf','middle')
save('observation','从观测资料到声学环境','本项目尚未导入实验原始数据；Munk 任务仍采用教师理想示例。',body)
print('Created',len(list(OUT.glob('*.svg'))),'source-aware vector diagrams')
