"""
中文汉化目录：87 个 landlab 组件的中文名、中文说明与常用参数中文释义。
====================================================================
覆盖不全的条目自动回退显示英文原文；由 i18n 模块按界面语言取用。

结构:
  COMPONENT_ZH["组件名"] = {"name": "中文名", "doc": "中文说明"}
  PARAM_ZH["组件名"]["参数名"] = "中文释义"
"""

COMPONENT_ZH = {
    # ---------------- 水流与汇流 ----------------
    "FlowAccumulator": {"name": "汇流累积器", "doc": "计算水流方向与汇水面积，最常用的水流组件；可选择挂接洼地处理器"},
    "FlowDirectorSteepest": {"name": "最陡坡流向", "doc": "每个节点流向最低的邻点（单流向），简单快速"},
    "FlowDirectorD8": {"name": "D8 流向", "doc": "八方向最陡下降（单流向），规则网格经典算法"},
    "FlowDirectorMFD": {"name": "多流向 MFD", "doc": "水流按坡度分配给多个下坡邻点，漫散型汇流"},
    "FlowDirectorDINF": {"name": "D-infinity 流向", "doc": "D∞ 三角面双流向分配算法"},
    "LossyFlowAccumulator": {"name": "损耗汇流累积器", "doc": "汇流过程中可损失水量（入渗/填洼），用于水文损失模拟"},
    # ---------------- 洼地处理 ----------------
    "PriorityFloodFlowRouter": {"name": "优先洪水汇流路由(自动填洼)", "doc": "Priority Flood 算法：填洼与汇流一步完成，大网格速度快（教程v2核心组件）；支持 fill/breach 洼地处理"},
    "DepressionFinderAndRouter": {"name": "洼地查找与路由", "doc": "经典填洼算法：识别洼地并把水流改道至溢出路径，常配 FlowAccumulator 使用"},
    "LakeMapperBarnes": {"name": "Barnes 湖泊填充", "doc": "高效填洼/湖泊标注算法（Barnes 2020）"},
    "SinkFiller": {"name": "洼地填充器", "doc": "填充 DEM 中的洼地使水流可连通"},
    "SinkFillerBarnes": {"name": "Barnes 洼地填充", "doc": "Barnes 高效洼地填充实现"},
    "PotentialityFlowRouter": {"name": "势能流路由", "doc": "忽略现有地形的势能最优流路，用于重建古水系"},
    # ---------------- 河道侵蚀与沉积 ----------------
    "FastscapeEroder": {"name": "快速基岩侵蚀", "doc": "流功率基岩河道下切（Fastscape/BMP 隐式快速解，Braun & Willett 2013），教程默认侵蚀组件"},
    "StreamPowerEroder": {"name": "流功率侵蚀", "doc": "经典河流功率侵蚀 E=K·A^m·S^n 显式实现"},
    "StreamPowerSmoothThresholdEroder": {"name": "平滑阈值流功率侵蚀", "doc": "带平滑可导阈值的流功率侵蚀，数值稳定；K_sp 留空则按 'E=K·A^m·S^n 由面积-坡度自动定K'"},
    "Space": {"name": "SPACE 基岩-沉积侵蚀", "doc": "基岩+沉积层耦合侵蚀模型（Shobe 2017），教程v1使用"},
    "SpaceLargeScaleEroder": {"name": "SPACE 大尺度侵蚀", "doc": "SPACE 的大网格加速版，教程v2配合优先洪水路由使用"},
    "ErosionDeposition": {"name": "侵蚀-沉积模型", "doc": "Davy & Lague 侵蚀-沉积模型，含沉积物再搬运"},
    "SedDepEroder": {"name": "泥沙相关侵蚀", "doc": "侵蚀率随沉积物覆盖度变化的河道侵蚀"},
    "SharedStreamPower": {"name": "共享流功率模型", "doc": "Hergarten 2021 流功率框架（河网节点共享求解）"},
    "GravelBedrockEroder": {"name": "砾石-基岩侵蚀", "doc": "砾石输运与基岩侵蚀耦合（推移质框架）"},
    "GravelRiverTransporter": {"name": "砾石河流输运", "doc": "砾石河道推移质输运与分选"},
    "AreaSlopeTransporter": {"name": "面积-坡度输运", "doc": "基于面积-坡度关系的泥沙输运"},
    "LateralEroder": {"name": "侧向侵蚀", "doc": "河岸侧向侵蚀与曲流发育"},
    "ConcentrationTrackerForSpace": {"name": "SPACE 浓度示踪", "doc": "配合 SPACE 追踪沉积物来源浓度"},
    "ThresholdEroder": {"name": "阈值侵蚀", "doc": "带临界剪切力/功率阈值的侵蚀"},
    # ---------------- 坡面过程 ----------------
    "LinearDiffuser": {"name": "线性坡面扩散", "doc": "土壤蠕动线性扩散夷平（D∇²z），教程全程使用"},
    "DepthDependentDiffuser": {"name": "深度依赖扩散", "doc": "扩散率随土壤层厚度变化的坡面过程"},
    "TaylorNonLinearDiffuser": {"name": "Taylor 非线性扩散", "doc": "坡度相关非线性扩散（Taylor 修正）"},
    "DepthDependentTaylorDiffuser": {"name": "深度依赖Taylor扩散", "doc": "同时考虑土层厚度与坡度非线性的扩散"},
    "PerronNLDiffuse": {"name": "Perron 非线性扩散", "doc": "Perron 隐式非线性扩散，稳定性好"},
    "TransportLengthHillslopeDiffuser": {"name": "输运长度坡面扩散", "doc": "基于输运长度理论（Ganti 2012）的坡面泥沙"},
    "DepthSlopeProductErosion": {"name": "深度-坡度积侵蚀", "doc": "以深度×坡度为驱动力的侵蚀"},
    "DetachmentLtdErosion": {"name": "搬运限制侵蚀", "doc": "搬运限制型坡面侵蚀（无沉积）"},
    "DischargeDiffuser": {"name": "流量扩散", "doc": "扩散系数随流量的坡面扩散"},
    "LinearDiffusionOverlandFlowRouter": {"name": "线性扩散坡面流", "doc": "线性扩散波近似的地表水路由"},
    "ConcentrationTrackerForDiffusion": {"name": "扩散浓度示踪", "doc": "配合 LinearDiffuser 追踪泥沙来源浓度"},
    "SimpleSubmarineDiffuser": {"name": "简单海底扩散", "doc": "海底环境下的深度依赖扩散（水深控制）"},
    # ---------------- 风化与土壤 ----------------
    "ExponentialWeatherer": {"name": "指数风化", "doc": "指数衰减土壤生产函数（更新 soil__depth）"},
    "ExponentialWeathererIntegrated": {"name": "积分指数风化", "doc": "积分形式的指数风化（计算 cumulative 日照/风化深度）"},
    "SoilInfiltrationGreenAmpt": {"name": "Green-Ampt 入渗", "doc": "Green-Ampt 降雨入渗模型（更新土壤水与入渗率）"},
    "SoilMoisture": {"name": "土壤水分", "doc": "土壤水动态（渗透/蒸发/补给）模型"},
    # ---------------- 水文与气候 ----------------
    "OverlandFlow": {"name": "二维地表径流", "doc": "扩散波二维坡面汇流（de Almeida 格式）"},
    "OverlandFlowBates": {"name": "Bates 地表径流", "doc": "Bates 2010 的浅水近似坡面流"},
    "KinwaveOverlandFlowModel": {"name": "运动波坡面流", "doc": "运动波近似的地表径流（显式）"},
    "KinwaveImplicitOverlandFlow": {"name": "隐式运动波坡面流", "doc": "运动波坡面流的隐式求解，步长更自由"},
    "KinematicWaveRengers": {"name": "运动波(Rengers)", "doc": "Rengers 运动波坡面流变体"},
    "GroundwaterDupuitPercolator": {"name": "Dupuit 地下水渗流", "doc": "Dupuit 假设下的二维地下水流动与基流"},
    "RiverFlowDynamics": {"name": "河流动力学", "doc": "一维浅水方程河道水流（含动量）"},
    "DimensionlessDischarge": {"name": "无量纲流量", "doc": "由汇水面积估算无量纲流量/输沙能力"},
    "PotentialEvapotranspiration": {"name": "潜在蒸散发", "doc": "计算潜在蒸散发速率场"},
    "Radiation": {"name": "太阳辐射", "doc": "地形太阳辐射量（坡向/遮蔽）计算"},
    # ---------------- 构造与地质 ----------------
    "Flexure": {"name": "岩石圈挠曲(3D)", "doc": "弹性薄板挠曲：荷载（山体/沉积）导致区域沉降"},
    "Flexure1D": {"name": "一维挠曲", "doc": "剖面方向的一维弹性挠曲"},
    "gFlex": {"name": "gFlex 挠曲接口", "doc": "调用 gFlex 库的高级岩石圈挠曲（需另装）"},
    "NormalFault": {"name": "正断层", "doc": "沿断层线两盘差异升降（块断构造）"},
    "ListricKinematicExtender": {"name": "铲式伸展构造", "doc": "铲式正断层控制的伸展盆地模拟"},
    "Lithology": {"name": "岩性层", "doc": "管理多层岩性（侵蚀系数等随岩性变化），供其他组件查询"},
    "LithoLayers": {"name": "多层岩性", "doc": "生成平行的多岩层结构（倾向/层厚可调）"},
    "CarbonateProducer": {"name": "碳酸盐生产", "doc": "浅水环境碳酸盐岩生产与堆积"},
    "FractureGridGenerator": {"name": "裂隙网格生成", "doc": "生成带裂隙方位场的网格（供风化用）"},
    # ---------------- 生态与扰动 ----------------
    "Vegetation": {"name": "植被生长", "doc": "植被覆盖随水分动态生长/衰减（旧版接口 update）"},
    "SpeciesEvolver": {"name": "物种演化器", "doc": "地形变化驱动的物种演化分支模拟"},
    "FireGenerator": {"name": "火干扰生成器", "doc": "随机火灾事件序列（供植被/侵蚀扰动）"},
    # ---------------- 滑坡与块体运动 ----------------
    "LandslideProbability": {"name": "滑坡概率", "doc": "无限斜坡法蒙特卡洛滑坡概率"},
    "BedrockLandslider": {"name": "基岩滑坡", "doc": "随机基岩滑坡事件（临界坡度触发）"},
    "MassWastingRunout": {"name": "块体运动堆积", "doc": "滑坡体 runout 运移-堆积 Cellular 模型"},
    # ---------------- 海岸与海洋 ----------------
    "TidalFlowCalculator": {"name": "潮流计算", "doc": "潮汐流场计算（海岸地貌用）"},
    # ---------------- 河网泥沙 ----------------
    "NetworkSedimentTransporter": {"name": "河网泥沙输运", "doc": "在河网（NetworkModelGrid）上输运泥沙颗粒"},
    "SedimentPulserAtLinks": {"name": "河段泥沙注入", "doc": "向指定河段注入泥沙颗粒"},
    "SedimentPulserEachParcel": {"name": "逐颗粒泥沙注入", "doc": "按颗粒逐个注入泥沙"},
    "BedParcelInitializerArea": {"name": "河床粒径初始化(面积)", "doc": "按汇水面积设定河床泥沙粒径分布"},
    "BedParcelInitializerDepth": {"name": "河床粒径初始化(水深)", "doc": "按水深设定河床泥沙粒径分布"},
    "BedParcelInitializerDischarge": {"name": "河床粒径初始化(流量)", "doc": "按流量设定河床泥沙粒径分布"},
    "BedParcelInitializerUserD50": {"name": "河床粒径初始化(自定义D50)", "doc": "用户直接指定中值粒径 D50"},
    # ---------------- 地形分析 ----------------
    "ChiFinder": {"name": "χ 指数计算", "doc": "计算河道 χ 指数（Perron & Royden 2013，用于分水岭迁移与河道不平衡分析），输出 channel__chi_index"},
    "SteepnessFinder": {"name": "陡峭指数 ksn", "doc": "归一化河道陡峭指数 ksn=E^(m/n) 计算"},
    "ChannelProfiler": {"name": "河道纵剖面", "doc": "从出水口向上提取河道纵剖面（最大/指定汇水区）"},
    "Profiler": {"name": "通用剖面", "doc": "沿自定义节点序列或坡度下降路径取剖面"},
    "TrickleDownProfiler": {"name": "顺流剖面", "doc": "从给定起点沿最陡下降的 trickle 剖面"},
    "HackCalculator": {"name": "Hack 定律计算", "doc": "主河道长度-汇水面积关系（Hack 定律）"},
    "DrainageDensity": {"name": "河网密度", "doc": "计算河网密度（河道长度/面积）"},
    "HeightAboveDrainageCalculator": {"name": "河流以上高度", "doc": "计算各点到最近河道的相对高度（HAD）"},
    # ---------------- 其他 ----------------
    "PrecipitationDistribution": {"name": "降水事件生成器", "doc": "泊松过程随机暴雨事件序列（强度/历时）"},
    "SpatialPrecipitationDistribution": {"name": "空间降水分布", "doc": "带空间结构的风暴事件（风暴中心移动）"},
    "AdvectionSolverTVD": {"name": "TVD 平流求解器", "doc": "总变差减小(TVD)标量场平流（如示踪物搬运）"},
    "VegCA": {"name": "植被元胞自动机", "doc": "植被-火烧-气候 Cellular 自动机（旧版接口 update）"},
}

# ---------------- 常用参数中文释义（未列出的回退英文 docstring） ----------------
PARAM_ZH = {
    "FastscapeEroder": {
        "K_sp": "侵蚀系数 K（1e-7 极硬岩 ~ 1e-4 软岩；越大下切越快）",
        "m_sp": "面积指数 m（典型 0.3~0.7，决定凹度 θ=m/n）",
        "n_sp": "坡度指数 n（0.5~2；n=2 时陡坡侵蚀剧增）",
        "threshold_sp": "侵蚀阈值（0=无；低于此侵蚀功率不下切）",
        "discharge_field": "用作'流量'的字段（默认汇水面积）",
        "erode_flooded_nodes": "是否侵蚀被填洼淹没的节点",
    },
    "StreamPowerEroder": {
        "K_sp": "侵蚀系数 K", "m_sp": "面积指数 m", "n_sp": "坡度指数 n",
        "threshold_sp": "侵蚀阈值",
    },
    "StreamPowerSmoothThresholdEroder": {
        "K_sp": "侵蚀系数 K（留空=组件按面积-坡度自动计算）",
        "m_sp": "面积指数 m", "n_sp": "坡度指数 n",
        "threshold_sp": "平滑侵蚀阈值",
    },
    "Space": {
        "K_sed": "沉积层侵蚀系数", "K_br": "基岩侵蚀系数",
        "phi": "孔隙率", "H_star": "沉积层有效厚度尺度",
        "v_s": "沉积层沉降速度", "m_sp": "面积指数 m", "n_sp": "坡度指数 n",
        "sp_crit_sed": "沉积层临界侵蚀面积", "sp_crit_br": "基岩临界侵蚀面积",
    },
    "SpaceLargeScaleEroder": {
        "K_sed": "沉积层侵蚀系数", "K_br": "基岩侵蚀系数",
        "phi": "孔隙率", "H_star": "沉积层有效厚度尺度",
        "v_s": "沉降速度", "m_sp": "面积指数 m", "n_sp": "坡度指数 n",
    },
    "ErosionDeposition": {
        "m": "面积指数", "n": "坡度指数", "v_s": "沉降速度",
        "F_f": "细粒(冲泻质)比例", "K": "侵蚀系数",
        "phi": "孔隙率",
    },
    "LinearDiffuser": {
        "linear_diffusivity": "扩散系数 D (m²/yr，典型 0.001~0.01；越大坡面越缓)",
        "method": "求解格式", "deposit": "是否允许沉积",
    },
    "FlowAccumulator": {
        "surface": "用于求流路的地形字段",
        "flow_director": "流向算法（Steepest/D8/MFD/DINF）",
        "depression_finder": "洼地处理器（留空=不处理洼地）",
        "runoff_rate": "产流率（None=单位汇水）",
    },
    "PriorityFloodFlowRouter": {
        "surface": "用于求流路的地形字段",
        "flow_metric": "流向算法（D8/D4/MFD/DINF）",
        "update_flow_depressions": "每步是否重新处理洼地",
        "depression_handler": "洼地处理方式（fill填充/breach开凿/route路由）",
        "runoff_rate": "产流率",
    },
    "DepressionFinderAndRouter": {
        "surface": "地形字段", "method": "洼地路由方法",
        "pits": "已知的洼地节点（可选）",
    },
    "ChiFinder": {
        "reference_concavity": "参考凹度 θ_ref（通常 0.4~0.5）",
        "min_drainage_area": "最小汇水面积阈值(m²)",
        "reference_area": "参考面积 A_ref",
        "use_true_dx": "使用真实距离（更准但更慢）",
    },
    "SteepnessFinder": {
        "reference_concavity": "参考凹度 θ_ref",
        "min_drainage_area": "最小汇水面积阈值(m²)",
        "discharge_field": "流量字段",
        "elevation_field": "高程字段",
    },
    "ChannelProfiler": {
        "number_of_watersheds": "提取的流域数",
        "main_channel_only": "只取主流（False=含支流）",
        "minimum_channel_threshold": "河道最小汇水面积(m²)",
        "outlet_nodes": "指定出水口节点（可选）",
    },
    "NormalFault": {
        "fault_trace": "断层线两端点坐标", "fault_dip_angle": "断层倾角(度)",
        "fault_throw_rate_through_time": "各时段断距速率(yr)",
        "raised_side": "上升盘", "dip_direction": "倾向",
    },
    "ExponentialWeatherer": {
        "soil_production_maximum_rate": "最大土壤生产速率 w0 (m/yr)",
        "soil_production_decay_depth": "衰减深度 d0 (m)",
    },
    "PrecipitationDistribution": {
        "mean_storm_duration": "平均暴雨历时", "mean_interstorm_duration": "平均间隔历时",
        "mean_storm_depth": "平均暴雨深度", "total_rainfall_timestep": "降雨时间步",
    },
    "Flexure": {
        "eet": "岩石圈有效弹性厚度 EET (m)",
        "method": "求解方法(Flexure/Flexure1D)",
    },
    "LithoLayers": {
        "rock_type": "各层岩石类型", "thicknesses": "各层厚度",
        "function": "层界面函数", "nodal_attributes": "各层属性值",
    },
    "LandslideProbability": {
        "friction_coefficient": "摩擦系数", "cohesion": "黏聚力",
        "landslide__min_number_of_iterations": "蒙特卡洛次数",
        "groundwater__depth_distribution": "地下水深度分布",
    },
    "GravelBedrockEroder": {
        "basin_width": "河宽系数", "abrasion_coefficient": "磨蚀系数",
        "sediment_porosity": "泥沙孔隙率", "transmissivity": "输移能力系数",
        "k_bedrock": "基岩侵蚀系数", "beta_bedrock": "磨蚀下切系数",
    },
    "OverlandFlow": {
        "alpha": "Bates粗糙度参数", "roughness": "曼宁糙率 n",
        "g": "重力加速度", "h_init": "初始水深",
    },
}
