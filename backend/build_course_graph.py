"""Curated course ontology. Citations are checked PDF pages / packaged source files.
Hierarchy and learning order are editorial organization, not scientific causal claims.
"""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
chapters=[
 ('basics','声学基础','#68a8ff','从物理量、分贝和波动方程开始，建立计算与读图的共同语言。'),
 ('environment','海洋环境','#67dbc3','理解声速剖面、海面与海底，明确仿真环境的物理假设。'),
 ('methods','声传播方法','#be9bff','比较简正波、射线/波束和抛物方程，理解每种方法的适用条件。'),
 ('toolbox','AT 仿真流程','#ffcd73','从环境文件到求解器，串联 MATLAB 调用与输出读取。'),
 ('analysis','结果分析','#ff91bb','解释传播损失、网格和数值检查，避免把示例计算当作实测结论。'),
 ('observations','观测与应用','#83d2f5','把实验观测与声学环境联系起来，区分历史报告、原始数据和模型输入。')]
nodes=[];edges=[]
def edge(a,b,label,group='related',note='',references=None):
 edges.append({'id':f'e{len(edges)+1:03}','source':a,'target':b,'label':label,'type':group,'group':group,'note':note,'references':references or []})
nodes.append({'id':'course','label':'海洋声学','kind':'course','overview':'围绕“环境—原理—求解—结果”组织课程知识。可直接浏览知识、查看教材图片，也可跳转到已接通的 Munk 声场仿真。','source_claim_ids':[],'references':[],'color':'#a5c4ff'})
for i,(id,label,color,description) in enumerate(chapters,1):
 nodes.append({'id':id,'label':label,'kind':'chapter','number':i,'color':color,'overview':description,'source_claim_ids':[],'references':[]})
 edge('course',id,'课程单元','hierarchy')

def ref(page,source='S17',locator=''):
 return {'source_id':source,'pdf_page':page,'locator':locator or f'PDF 第 {page} 页'}
def code(locator):return {'source_id':'PROJECT' if locator.startswith('backend/') else 'S20','locator':locator}
def add(id,label,chapter,overview,points,references,*,formula='',conditions='',mistake='',example='',diagram='',tags=None,simulation=False):
 color=next(x[2] for x in chapters if x[0]==chapter)
 claim='K'+str(sum(n['kind']=='knowledge' for n in nodes)+1).zfill(3)
 nodes.append({'id':id,'label':label,'kind':'knowledge','chapter':chapter,'color':color,'overview':overview,'key_points':points,'references':references,'formula':formula,'conditions':conditions,'misconception':mistake,'example':example,'diagram':diagram,'tags':tags or ['核心知识'],'simulation':simulation,'source_claim_ids':[claim]})
 edge(chapter,id,'包含知识点','hierarchy')

add('acoustic_pressure','声压与水听器','basics','声压是声波引起的压力扰动。水听器把水中的声学信号转换为可记录的电信号，计算模型则用声压场描述传播。',['声源与接收器的位置共同确定传播问题。','声压传感器与速度/矢量传感器测量的物理量不同。'],[ref(29),ref(30)],mistake='不要把声压 p 与声强 I 当作同一个量。',diagram='quantities')
add('acoustic_intensity','声强与能流','basics','声强表示单位面积上的平均声能流率；它既与声压有关，也与质点速度有关。',['声强有传播方向，时间平均需要考虑声压和速度的相位关系。','平面行波中可由均方根声压与介质阻抗计算声强。'],[ref(31),ref(32)],formula='I = pᵣₘₛ² / (ρc)',conditions='该简式用于平面行波；一般复声场应使用声压与速度的复共轭关系。',diagram='quantities')
add('acoustic_impedance','声阻抗','basics','平面行波的特性声阻抗为介质密度与声速的乘积。比较不同介质中的声压与声强时，需要考虑阻抗差异。',['水和海底介质可以具有不同阻抗。','用 20 log 的声压比替代 10 log 的声强比时，需要满足相应阻抗约定。'],[ref(32),ref(33)],formula='Z = ρc',diagram='quantities')
add('decibel','分贝与参考量','basics','分贝表达两个量的对数比值。声强比采用 10 log₁₀，声压幅值比在相同阻抗约定下采用 20 log₁₀。',['声压级常以 1 μPa 为参考。','传播损失的参考是同源 1 m 处的参考场，不能与声压级的参考单位混用。'],[ref(32),ref(33)],formula='ΔL = 10 log₁₀(I₁/I₂) = 20 log₁₀(|p₁|/|p₂|)',conditions='声压比等价式需采用相同阻抗约定。',mistake='“80 dB TL”不能直接解释为“80 dB re 1 μPa 的接收声压级”。',diagram='spreading')
add('spherical_spreading','球面扩展','basics','均匀、无界、无损介质中的点声源，声能分布在球面上，声强随距离平方的倒数减小。',['用于理解几何扩展，不包含吸收和边界反射损失。','距离增加 10 倍，球面扩展损失增加 20 dB。'],[ref(33)],formula='TL = 20 log₁₀(r / 1 m)',conditions='均匀、无界、无损介质；r 为传播距离。',example='从 10 m 到 100 m，几何扩展损失增量为 20 dB。',diagram='spreading')
add('cylindrical_spreading','柱面扩展','basics','在理想平面边界波导的远场，声能受垂向限制，几何扩展趋向柱面形式。',['点源近场仍可能表现为球面扩展，随后经历过渡。','10 log₁₀ 的斜率不能作为任意真实波导的完整损失模型。'],[ref(34)],formula='理想远场扩展斜率：10 log₁₀ r',conditions='理想波导远场；实际截距与近场过渡、边界和损耗有关。',mistake='不要把这条理想扩展律直接替代 KRAKEN 声场。',diagram='spreading')
add('helmholtz','Helmholtz 方程','basics','对时间变量进行频域变换后，波动方程转化为 Helmholtz 方程。多种声传播方法是在不同条件下求解这一类问题。',['局部波数由频率与声速确定。','问题维度、边界、声源几何和环境变化决定合适的求解方法。'],[ref(90),ref(91)],formula='∇²p + k²p = 0；k = 2πf / c',conditions='此处写出恒密度、无源区域的简式；变密度、源项和边界应另行处理。',diagram='methods')

add('sound_speed_profile','声速剖面 SSP','environment','声速剖面描述声速随深度的变化，是判断折射、声道及模型环境的重要输入。',['典型剖面可含混合层、温跃层与深层近等温区。','真实剖面可能随距离、季节和时间变化。'],[ref(22),ref(23)],formula='c = c(T, S, z)',mistake='示例剖面不等于指定海域的实测剖面。',diagram='ssp')
add('temperature_salinity','温度、盐度与压力','environment','海水声速由温度、盐度与静压力等因素共同决定；深度常作为静压力的代理量进入经验公式。',['上层海洋的季节与日变化会改变声速结构。','高精度走时应用应选择与条件匹配的声速公式。'],[ref(22)],conditions='经验声速公式有自己的温盐深适用范围；不能无限外推。',diagram='ssp')
add('deep_sound_channel','深海声道','environment','深海声道的轴线对应声速极小值附近；部分声能可以经内部折射长距离传播，减少与有损边界的相互作用。',['不是所有发射角都被声道约束。','轴线深度与有效角度范围随海域和剖面变化。'],[ref(23),ref(43),ref(44)],mistake='不能把某个海域示例的声道轴深度当作全球常数。',diagram='ssp')
add('surface_duct','表面声道','environment','近海面混合层可形成表面声道。被束缚的传播路径反复与海面相互作用，传播效果受海况、混合层和频率影响。',['浅声道在低频下可能不能有效束缚声能。','上层加热可破坏原有导声结构。'],[ref(44),ref(45)],conditions='教材所述近表层环境；声道有效性应由具体剖面和频率判断。',diagram='ssp')
add('pressure_release_surface','压力释放海面','environment','理想压力释放边界要求海面处声压为零。在相应模态问题中，垂向模态函数在海面也为零。',['这是边界理想化，不是对任意粗糙海面散射的完整描述。','数值结果中的近零残差不宜直接解释为巨大但有意义的 TL。'],[ref(357,locator='式 5.4')],formula='p(z = 0) = 0',conditions='理想压力释放边界。',diagram='boundary')
add('rigid_bottom','刚性海底边界','environment','理想刚性海底对应法向速度为零，并使相应模态的法向导数为零。',['真实海底通常不能一概当作刚性边界。','吸收、流体半空间和弹性底条件需要分别建模。'],[ref(357,locator='式 5.4')],formula='∂p/∂n = 0',conditions='理想刚性边界。',diagram='boundary')
add('seabed','海底介质与损耗','environment','海底结构与介质参数会影响反射和能量损耗，尤其在浅水、低频或较多海底相互作用的情形下。',['海底可具有分层沉积物和更深的地壳结构。','密度、声速、吸收及弹性性质不能只用一个“水深”参数代替。'],[ref(27),ref(28)],mistake='有了水深，并不等于已经确定海底边界条件。',diagram='boundary')
add('range_dependence','距离相关环境','environment','声速、水深或底质随传播距离改变时，环境具有距离相关性。距离无关假设是便于计算的近似。',['海洋锋面和海山是教材中的距离相关例子。','环境变化可引起折射、模态耦合或额外边界作用。'],[ref(51),ref(52),ref(53)],conditions='须依据具体环境判断近似是否合理。',diagram='methods')
add('munk_profile','Munk 理想剖面','environment','Munk 剖面是研究深海传播特性的理想声速模型，可用于展示深声道及模态形态。',['教材给出连续解析剖面；教师工具包使用离散深度—声速输入。','本项目运行的是工具包的 5000 m Munk 示例。'],[ref(375),ref(376),code('at/tests/Munk/MunkK.env')],formula='c(z) = c₀[1 + ε(η − 1 + e⁻η)]；η = 2(z − zₐ)/B',conditions='参数与离散输入以所用示例为准，不能把理想模型当作实测环境。',diagram='ssp',simulation=True)

add('normal_mode_field','简正波方法','methods','在波导中用一组垂向模态及其传播因子表示声场。源深与接收深度通过模态函数影响各项贡献。',['基础展开适用于教材所述距离无关波导。','距离相关环境可采用耦合模态或特定近似扩展。'],[ref(356),ref(359),ref(421)],formula='p(r,z) = Σₘ Aₘ(r) ψₘ(z)',conditions='示意展开；归一化、密度因子和传播因子以具体推导为准。',diagram='modes',simulation=True)
add('source_depth','声源深度','methods','源位置的模态函数决定激发权重。改变源深会改变各模态对最终声场的贡献。',['不能只凭“靠近声道轴”就断言全部接收位置损失最小。','比较源深时应保持其他环境、频率和接收网格一致。'],[ref(359,locator='式 5.13–5.14')],example='可运行 50 Hz 下源深 500 m 与 1000 m 两组，比较同一接收深度曲线。',diagram='modes',simulation=True)
add('mode_excitation','模态激发权重','methods','声源对各模态的激发与源位置的模态函数值有关，而接收位置又决定各模态的观测权重。',['源位于某模态的节点附近时，该模态的激发可能很弱。','最终声场需要综合所有有效模态及其相位。'],[ref(359)],diagram='modes')
add('modal_sum','模态叠加','methods','简正波声场由各模态的复贡献相加得到。不同模态的传播相位导致空间干涉结构。',['幅值与相位都参与相干复声压求和。','先求复声压和再转 TL，与先求模态强度和不同。'],[ref(359)],diagram='modes')
add('coherent_modal_sum','相干与非相干求和','methods','相干求和保留模态间相位关系；非相干约定按相应强度贡献组合，二者可能给出不同的损失结构。',['比较图表时应记录采用的求和类型。','频率平滑不能随意视为任意非相干计算的等价替代。'],[ref(359,locator='式 5.17–5.18')],conditions='当前网页 Munk 模板使用 FIELD 的相干设置。',diagram='modes')
add('ray_method','射线方法','methods','射线与波前正交，用轨迹描述声能传播方向。折射、边界反射和多路径可由射线图直观理解。',['射线轨迹对声速剖面和数值离散敏感。','阴影区与焦散附近，几何射线需要特别处理。'],[ref(175),ref(194)],conditions='射线近似有适用范围；不能用零条射线直接断言真实声压为零。',diagram='rays')
add('snell','Snell 定律','methods','在水平分层介质中，射线掠射角与局部声速满足不变量关系，可用来解释声线转向。',['这里角度 θ 相对水平定义。','若采用相对法线的角度，三角函数形式会改变。'],[ref(176),ref(217)],formula='cos θ(z) / c(z) = 常数',conditions='水平分层介质中的射线关系。',mistake='不要把“相对水平”与“相对法线”的角度混用。',diagram='rays')
add('caustic_shadow','焦散与阴影区','methods','几何射线预测中，射线管截面趋于零产生焦散；没有射线经过的区域形成几何阴影。',['射线近似可在焦散处给出非物理的无限声强。','真实波动解通常保持有限，并可通过衍射在几何阴影区有声能。'],[ref(194)],diagram='rays')
add('gaussian_beams','高斯波束','methods','高斯波束在中心射线附近描述有限宽度的场，帮助处理纯几何射线场的某些问题。',['波束并非只有一条无宽度曲线。','BELLHOP 的实际输出与运行选项、波束设置有关。'],[ref(199),ref(201)],conditions='教材介绍的近轴波束思路；具体实现需查看求解器选项。',diagram='rays')
add('parabolic_equation','抛物方程 PE','methods','通过对 Helmholtz 方程作传播方向相关的近似，得到可沿距离步进计算的波场方程。',['标准 PE 包含远场与小角度/近轴近似。','不同宽角算法和实现具有不同精度与限制。'],[ref(477),ref(478)],formula='2ik₀ ∂u/∂r + ∂²u/∂z² + k₀²(n² − 1)u = 0',conditions='展示标准恒密度二维 PE；不是所有 PE 实现的统一完整方程。',diagram='methods')
add('coupled_modes','耦合模态与绝热近似','methods','距离相关问题可使用局部模态描述。耦合模态考虑模态间能量转移，绝热近似则忽略相关交叉耦合。',['“简正波只能算距离无关环境”过于绝对。','是否可用绝热近似，要看环境变化和目标精度。'],[ref(421),ref(427)],diagram='methods')

add('matlab_kraken_wrapper','KRAKEN / FIELD 调用','toolbox','教师包 kraken.m 先运行 kraken.exe，再调用 field.exe 计算接收网格上的声场。',['KRAKEN 求模态，FIELD 按指定几何计算场。','网页使用独立任务目录，保留每次新生成的文件。'],[code('at/kraken.m:8–17'),code('backend/matlab/run_ocean_case.m')],example='网页“检查计划→确认运行”调用固定 MATLAB 入口，不执行任意模型代码。',diagram='pipeline',simulation=True)
add('bellhop','BELLHOP 工具','toolbox','BELLHOP 是教师包提供的射线/波束传播工具。MATLAB 包装函数查找并运行 bellhop.exe。',['方法知识可先看射线与高斯波束节点。','不同运行选项产生的声线、到达结构或声场需要配套读取。'],[code('at/bellhop.m'),ref(175),ref(199)],conditions='工具包已安装；网页首版尚未接入 BELLHOP 任务提交。',diagram='rays')
add('ram','RAM 工具','toolbox','RAM 是资料包中的抛物方程求解工具。可与 PE 原理一起学习，理解沿距离步进的波场计算。',['工具输入与 KRAKEN 的 ENV / FLP 工作流不同。','接入前应核对运行输入、输出读取及网格约定。'],[code('at/ram.m'),ref(477),ref(478)],conditions='工具包已安装；网页尚未接入 RAM 任务提交。',diagram='methods')
add('env_file','ENV 环境文件','toolbox','ENV 描述频率、介质层、声速剖面和边界等信息。参数值、格式与求解器选项需要同时正确。',['本模板检查标题、介质层数和源深标记后才修改输入。','生成后用 read_env 回读，核对实际频率与源深。'],[code('at/tests/Munk/MunkK.env'),code('at/ReadWrite/read_env.m'),code('backend/matlab/run_ocean_case.m')],diagram='pipeline')
add('flp_file','FLP 场计算文件','toolbox','FLP 指定 FIELD 场计算的选项及源、接收深度和距离网格，与模态文件共同生成声场。',['ENV 和 FLP 中的源深需要一致。','接收深度与距离采样决定最终声场网格。'],[code('at/tests/Munk/MunkK.flp'),code('backend/matlab/run_ocean_case.m')],diagram='pipeline')
add('field_executable','FIELD 与模态文件','toolbox','KRAKEN 生成模态文件，FIELD 读取模态与场计算输入，输出接收位置的复声压。',['仅有模态文件并不等于已经得到所需网格声场。','项目包装函数已串联两步，不应无依据重复调用。'],[code('at/kraken.m:8–17')],diagram='pipeline')
add('binary_shd_pressure','SHD 复声压输出','toolbox','本包二进制 SHD 读取器返回指定频率的复声压数组，按方位、源深、接收深、距离组织。',['读取器的维度约定需核对，不能只看数组大小猜含义。','复声压既有幅值也有相位；转换 TL 使用幅值。'],[code('at/ReadWrite/read_shd_bin.m:96–102'),code('backend/matlab/run_ocean_case.m')],formula='θ × zₛ × zᵣ × r',conditions='所核对的本包 reader 与指定频率；其他格式/版本需要重新核查。',diagram='pipeline')
add('munk_case','Munk 网页仿真案例','toolbox','已接通 MATLAB R2024a 与 KRAKEN / FIELD，可以在网页选择频率、源深和接收网格并得到本次计算结果。',['已完成 50/100 Hz 与 500/1000 m 源深四组核验。','每次任务保存 ENV、FLP、SHD、PRT、CSV、JSON 和图表。'],[code('at/tests/Munk/MunkK.env'),code('backend/matlab/run_ocean_case.m')],conditions='5000 m 理想深海示例，当前频率输入范围 10–200 Hz。',diagram='pipeline',simulation=True)

add('transmission_loss','传播损失 TL','analysis','传播损失比较接收场与同源参考场的强度或声压。判断 TL 数值之前，应先明确参考场、阻抗与求和约定。',['本网页按 AT FIELD 归一化复声压计算 −20 log₁₀|p|。','TL 是场与参考的比值，不是直接测量的声压级。'],[ref(33),ref(359),code('backend/matlab/run_ocean_case.m')],formula='TL = −20 log₁₀(|p| / |p₀|)',conditions='声压式采用相同阻抗约定；网页归一化参考遵循 AT FIELD。',diagram='spreading',simulation=True)
add('receiver_depth','接收深度与采样','analysis','接收深度影响所观测模态的权重。网页取最接近请求深度的网格点，并记录其实际深度与误差。',['请求 1005 m 并不保证网格中恰有 1005 m。','比较曲线需要对齐实际接收深度。'],[ref(359),code('backend/matlab/run_ocean_case.m')],diagram='grid',simulation=True)
add('range_depth_grid','距离—深度网格','analysis','声场图是离散距离与深度上的计算值。网格数量决定输出采样密度，不会自动改变物理环境。',['更密的接收网格只是更密的场采样，不等于求解器内部误差已经收敛。','输出图与 CSV 要保留明确的 m / km 单位。'],[code('backend/matlab/run_ocean_case.m')],conditions='这里说明本网页输出采样；求解器内部网格与精度控制需另外检查。',diagram='grid')
add('near_zero_pressure','近零声压与无效值','analysis','声压近零时，对数换算会产生很大的 TL 或无穷值。需要区分物理零值与数值残差。',['当前实现过滤 |p| < 10⁻¹² 及非有限 TL。','有效比例反映本次网格的可显示值比例，不是模型准确率。'],[ref(357),code('backend/matlab/run_ocean_case.m')],mistake='99.6% 的有效比例不能解释为仿真有 99.6% 的准确率。',diagram='grid')
add('comparison','控制变量比较','analysis','比较频率或源深的影响时，应固定其他输入、参考约定、接收深度和读图尺度。',['本网页声场图统一使用 40–110 dB 色标。','不能仅凭全网格中位 TL 判断某个接收位置的最优方案。'],[code('backend/matlab/run_ocean_case.m'),code('backend/app.py:plot_result')],conditions='项目分析约定；实际最优目标还需明确距离、接收位置、带宽等。',diagram='grid',simulation=True)
add('convergence_zone','会聚区','analysis','在特定深海剖面和源位置条件下，折射路径可在距离方向周期性聚焦，产生较高声强区。',['教材示例的会聚区间距随剖面与海域变化。','几何阴影区在波动解中仍可出现有限声能。'],[ref(40),ref(41),ref(42)],conditions='教材特定条件和例子；间距不能当作通用常数。',diagram='rays')

add('ctd','CTD 与环境观测','observations','CTD 观测提供温度、盐度和深度相关信息，是认识水体环境、进一步构建声速剖面的资料来源。',['必须同时记录站位、采样时间、深度和变量单位。','温盐图表与可直接计算的原始数据文件不是同一种资料。'],[ref(54,'S15','3.7 节、表 38'),ref(84,'S07','10.1 节')],diagram='observation')
add('ASIAEX_CTD','ASIAEX 2001 实验','observations','报告介绍 ASIAEX 南海实验的船载 CTD 温盐观测，并提供位置与水深等信息。',['可用于学习实验环境和观测组织。','年份和站位是不可省略的上下文。'],[ref(54,'S15','3.7 节、表 38')],conditions='2001 年历史实验资料；不代表当前指定海域。',diagram='observation',tags=['实验资料'])
add('SW06_CTD','SW06 2006 实验','observations','SW06 报告描述船载 CTD 对实验区域的空间温盐观测，配有观测位置表。',['可与 ASIAEX 比较观测组织与环境资料表达方式。','复现实验声场还需要原始数据与声源接收器条件。'],[ref(84,'S07','10.1 节')],conditions='2006 年历史实验；当前项目未宣称复现实验声场。',diagram='observation',tags=['实验资料'])
add('temperature_salinity_profiles','温盐观测到声速输入','observations','使用观测环境建模，需要把温盐深资料按适用声速公式转换，并检查单位、剖面范围和采样信息。',['报告图片可帮助理解，但不能直接作为原始数值数据。','当前 Munk 案例仍使用教师示例，不使用报告中的观测数据。'],[ref(22),ref(54,'S15'),ref(84,'S07')],conditions='这里是资料处理的教学流程；尚未接入观测数据导入。',diagram='observation')
add('validation','示例与实验验证','observations','数值示例成功运行验证了调用流程。要验证真实海域预测，还需独立观测数据、匹配实验条件与误差分析。',['运行成功、图像漂亮和物理准确是不同层次。','环境、源和接收条件需与验证数据对齐。'],[ref(52),ref(53),code('backend/matlab/run_ocean_case.m')],mistake='不要把 Munk 示例跑通写成 ASIAEX 或 SW06 实验已经复现。',diagram='observation')

# Semantic links are source-grounded or explicitly marked as project conventions.
links=[
 ('acoustic_intensity','decibel','以对数比表达'),
 ('acoustic_pressure','acoustic_intensity','关联声强'),('acoustic_impedance','acoustic_intensity','参与换算'),('decibel','transmission_loss','表达对数比'),('spherical_spreading','transmission_loss','理想扩展基准'),('cylindrical_spreading','transmission_loss','理想扩展基准'),
 ('temperature_salinity','sound_speed_profile','决定声速'),('sound_speed_profile','deep_sound_channel','形成声道结构'),('sound_speed_profile','surface_duct','形成导声条件'),('sound_speed_profile','snell','决定折射'),('munk_profile','deep_sound_channel','理想化描述'),('seabed','transmission_loss','影响边界损耗'),('pressure_release_surface','normal_mode_field','提供边界条件'),('rigid_bottom','normal_mode_field','理想边界条件'),
 ('helmholtz','normal_mode_field','求解方法'),('helmholtz','parabolic_equation','近似出发点'),('source_depth','mode_excitation','改变权重'),('mode_excitation','modal_sum','参与声场组合'),('modal_sum','normal_mode_field','构成声场'),('coherent_modal_sum','modal_sum','规定求和约定'),('receiver_depth','normal_mode_field','影响观测权重'),('snell','ray_method','描述折射轨迹'),('ray_method','caustic_shadow','几何近似现象'),('gaussian_beams','ray_method','波束扩展'),('range_dependence','coupled_modes','距离相关处理'),('range_dependence','parabolic_equation','沿距离建模'),
 ('normal_mode_field','matlab_kraken_wrapper','由工具实现'),('ray_method','bellhop','对应方法'),('gaussian_beams','bellhop','对应波束方法'),('parabolic_equation','ram','对应方法'),('munk_profile','env_file','离散环境输入'),('env_file','matlab_kraken_wrapper','提供环境'),('matlab_kraken_wrapper','field_executable','串联调用'),('flp_file','field_executable','配置接收网格'),('field_executable','binary_shd_pressure','输出复声压'),('binary_shd_pressure','transmission_loss','换算 TL'),('munk_case','matlab_kraken_wrapper','实际调用'),('range_depth_grid','flp_file','确定输出采样'),('receiver_depth','range_depth_grid','选取实际深度'),('near_zero_pressure','transmission_loss','数值过滤'),('comparison','source_depth','比较变量'),('comparison','transmission_loss','统一参考与尺度'),('ray_method','convergence_zone','解释聚焦'),
 ('ASIAEX_CTD','ctd','报告包含观测'),('SW06_CTD','ctd','报告包含观测'),('ctd','temperature_salinity_profiles','提供温盐深资料'),('temperature_salinity_profiles','sound_speed_profile','转换环境输入'),('validation','munk_case','区分运行与验证'),('validation','ASIAEX_CTD','需匹配观测条件'),('validation','SW06_CTD','需匹配观测条件')]
byid={n['id']:n for n in nodes}
for a,b,label in links:
 refs=byid[a]['references']+byid[b]['references']
 edge(a,b,label,'related','教学整理的概念关联，物理说明与适用条件见两端知识点。',refs)
paths=[
 {'id':'first','title':'入门：从原理到声场','description':'先理解环境与方法，再读实际计算结果。','nodes':['acoustic_pressure','decibel','sound_speed_profile','pressure_release_surface','normal_mode_field','source_depth','munk_case','transmission_loss']},
 {'id':'run','title':'实践：跑通 Munk 案例','description':'对齐输入、执行与结果的每一步。','nodes':['munk_profile','env_file','flp_file','matlab_kraken_wrapper','field_executable','binary_shd_pressure','range_depth_grid','receiver_depth','comparison']},
 {'id':'choose','title':'进阶：比较传播方法','description':'从共同方程走向不同近似与环境条件。','nodes':['helmholtz','snell','ray_method','caustic_shadow','gaussian_beams','normal_mode_field','range_dependence','coupled_modes','parabolic_equation','validation']}]
for p in paths:
 for a,b in zip(p['nodes'],p['nodes'][1:]):
  if not any(e['source']==a and e['target']==b and e['group']=='prerequisite' for e in edges):edge(a,b,'建议顺序','prerequisite','教学建议的阅读顺序，不表示严格数学必要条件。')
graph={'schema_version':'0.2','title':'海洋声学课程知识图谱','chapters':[{'id':id,'label':label,'color':color,'description':desc,'number':i} for i,(id,label,color,desc) in enumerate(chapters,1)],'nodes':nodes,'edges':edges,'learning_paths':paths,'reference_design':{'title':'智慧树知识图谱使用手册','url':'https://jwc.shnu.edu.cn/_upload/article/files/26/c4/b28fc1cf49408c3fd3980aa81320/2f28c218-42a8-4d05-9ca0-4bc2bea382cc.pdf','pages':[164,165,167,169,170]},'status':'人工整理课程结构与知识说明；逐项提供所用教材页码或代码定位。'}
out=ROOT/'backend/data';out.mkdir(exist_ok=True)
(out/'course_graph.json').write_text(json.dumps(graph,ensure_ascii=False,indent=2),encoding='utf-8')
print('Course graph:',len([n for n in nodes if n['kind']=='knowledge']),'knowledge points;',len(edges),'typed edges')
