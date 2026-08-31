"""
LCS700 演示数据 —— 逐字提取自 docs/RunchTech_V01.html 的 JS 常量。

用途：骨架占位页渲染、无真机时 AI 诊断降级填充、报告列表种子。
所有 SVG 图标保存为原始 inner-markup 字符串（含 <path>/<circle>/<rect>），
由 ui.widgets.SvgGlyph 解析绘制（无图片资源）。
"""

# ── 默认设备（本地持久化：QSettings ui/devices / ui/deleted_devices 镜像 lc_userdevs/lc_deldefaults） ──

DEFAULT_DEVICES = [
    {"id": "d0", "n": "您的设备1：DTS", "icon": "sedan", "cls": "",
     "system": "国六商用车诊断系统", "obd": "适用：3.5T以上柴油卡车"},
    {"id": "d1", "n": "您的设备2：X5", "icon": "suv", "cls": "orange",
     "system": "乘用车全系统诊断仪", "obd": "适用：2.0L~3.0L 乘用车"},
    {"id": "d2", "n": "您的设备3：正德友邦", "icon": "truck", "cls": "green",
     "system": "重卡 ECU 诊断系统", "obd": "适用：6×4 重型牵引车"},
]

# ── 设备 / 通用图标（24 viewBox inner markup，stroke 绘制） ──

DEV_ICONS = {
    "sedan": '<path d="M5 17h14l-2-6H7zM6 17v2M18 17v2"/><circle cx="8" cy="19" r="1.5"/><circle cx="16" cy="19" r="1.5"/>',
    "suv": '<path d="M4 16l2-7h12l2 7M5 16h14v3H5z"/><circle cx="7.5" cy="19" r="1.4"/><circle cx="16.5" cy="19" r="1.4"/><path d="M6 9h12"/>',
    "truck": '<path d="M2 14h20v3H2zM3 14l2-5h14l2 5M5 14v3M19 14v3M7 9h10M9 9V7h6v2"/><circle cx="7" cy="19" r="1.4"/><circle cx="17" cy="19" r="1.4"/>',
    "ev": '<path d="M5 4h11v12H5zM16 8h3l2 4v4h-5M5 16h11"/><circle cx="7.5" cy="19" r="1.4"/><circle cx="17.5" cy="19" r="1.4"/><path d="M9 7l3 2-3 2"/>',
    "wrench": '<path d="M14.7 6.3a4.5 4.5 0 0 0-6 6L3 18l3 3 5.7-5.7a4.5 4.5 0 0 0 6-6L14 12l-2-2z"/>',
    "chip": '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3"/>',
    "battery": '<rect x="2" y="7" width="16" height="10" rx="2"/><path d="M22 11v2"/><rect x="4" y="9" width="10" height="6" rx="1"/>',
    "gauge": '<path d="M3 12a9 9 0 0 1 18 0"/><path d="M12 12l4-4"/><circle cx="12" cy="12" r="1.5"/>',
    "car2": '<path d="M3 13l2-5h14l2 5M4 13h16v4H4z"/><circle cx="7" cy="18" r="1.5"/><circle cx="17" cy="18" r="1.5"/><path d="M6 8h12"/>',
    "radar": '<circle cx="12" cy="12" r="3"/><path d="M12 5a7 7 0 0 1 7 7M5 12a7 7 0 0 1 7-7M12 19a7 7 0 0 0 7-7"/>',
    "bluetooth": '<path d="M17.7 7.7L12 2h-1v7.6L6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 11 14.4V22h1l5.7-5.7-4.3-4.3 4.3-4.3zM13 5.8l1.9 1.9L13 9.6V5.8zm1.9 10.5L13 18.2v-3.8l1.9 1.9z"/>',
    "engine": '<path d="M3 6h6v4h2V6h6v8h-2v-2H9v2H3zM3 6V4h6v2M11 6V4h6v2"/>',
}

# 64 viewBox 专用诊断仪图标（special 页 grid 卡）
IC64 = {
    "ebs": '<circle cx="32" cy="32" r="14"/><circle cx="32" cy="32" r="4"/><path d="M32 18v-4M32 50v-4M18 32h-4M50 32h-4"/>',
    "abs": '<circle cx="26" cy="32" r="16"/><circle cx="26" cy="32" r="5"/><path d="M26 16v-5M26 53v-5"/>',
    "tebs": '<rect x="8" y="20" width="30" height="20" rx="3"/><rect x="38" y="20" width="18" height="20" rx="3"/><circle cx="18" cy="46" r="4"/><circle cx="30" cy="46" r="4"/><circle cx="46" cy="46" r="4"/>',
    "tabs": '<rect x="8" y="18" width="28" height="22" rx="3"/><rect x="38" y="18" width="16" height="22" rx="3"/><circle cx="18" cy="46" r="4"/><circle cx="30" cy="46" r="4"/><circle cx="46" cy="46" r="4"/>',
    "ecas": '<rect x="12" y="12" width="40" height="16" rx="3"/><path d="M16 40c0-6 5-6 5-12M32 40c0-6 5-6 5-12M48 40c0-6-5-6-5-12"/><path d="M12 48h40"/>',
    "adas": '<rect x="24" y="14" width="16" height="26" rx="2"/><circle cx="32" cy="20" r="2.5"/><path d="M22 30a12 12 0 0 1 0 14M14 26a22 22 0 0 1 0 22M42 30a12 12 0 0 0 0 14M50 26a22 22 0 0 0 0 22"/>',
    "other": '<rect x="16" y="16" width="32" height="32" rx="4"/><rect x="24" y="24" width="16" height="16" rx="2"/>',
    "epb": '<circle cx="32" cy="32" r="20"/><path d="M25 22v20M25 22h6a8 8 0 0 1 0 16h-8"/>',
    "retarder": '<circle cx="32" cy="32" r="16"/><circle cx="32" cy="32" r="4"/>',
    "amt": '<circle cx="22" cy="32" r="10"/><circle cx="42" cy="32" r="10"/><path d="M32 22v20M22 32h20"/>',
}

# 24 viewBox 小图标（高级功能 / 设置 / 更新等）
SMALL = {
    "can": '<path d="M10 42V22M32 42V22M54 42V22"/><path d="M10 26c8 5 14 5 22 0s14-5 22 0M10 38c8 5 14 5 22 0s14-5 22 0"/>',
    "obd": '<path d="M6 6h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z"/><path d="M9 6V4M15 6V4"/>',
    "eobd": '<path d="M7 7h10v7H7z"/><circle cx="9.5" cy="10.5" r="1"/><circle cx="14.5" cy="10.5" r="1"/>',
    "check": '<path d="M4 12l2.5-4.5H13L16 12M5.5 12v4M14.5 12v4"/><circle cx="8" cy="17" r="1.6"/><circle cx="15" cy="17" r="1.6"/><path d="M12.5 9.5l1 1 2-2"/>',
    "software": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h6M9 13h6M9 17h4"/>',
    "hardware": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    "home": '<path d="M3 12l9-9 9 9M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
    "theme": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>',
}

# ── 故障现象（两级：8 类 → 29 项） ──

SYMPTOMS = [
    {"cat": "油耗动力", "items": ["动力不足", "油耗高"]},
    {"cat": "起动熄火", "items": ["起动机转无法起动", "起动机不转无法起动", "行驶中异常熄火国六禁止起动", "冷车难起动"]},
    {"cat": "DPF系统", "items": ["DPF无法再生(排温不起)", "DPF无法再生(转速不起)", "DPF频繁再生"]},
    {"cat": "SCR系统", "items": ["尿素喷嘴结晶堵塞", "排放超标", "尿素消耗大", "不烧尿素"]},
    {"cat": "限速限扭", "items": ["限速1500/限速1000", "打转向灯发动机限速", "国六限速20Km/h", "车辆下坡后限速"]},
    {"cat": "功能失效", "items": ["排气制动失效", "发动机制动失效", "远程油门无反应", "亮故障灯"]},
    {"cat": "怠速相关", "items": ["怠速不稳", "发动机怠速升高"]},
    {"cat": "发动机本体", "items": ["发动机高温", "怠速冒黑烟", "急加速冒黑烟"]},
]

# ── 专用诊断仪 / 高级功能 / EBS 子系统 ──

SPECIAL_ITEMS = [
    {"n": "EBS", "sub": "电子制动系统", "ic": "ebs", "to": "ebs"},
    {"n": "ABS", "sub": "防抱死刹车系统", "ic": "abs", "to": "ebs"},
    {"n": "TEBS", "sub": "挂车电子制动系统", "ic": "tebs", "to": "ebs"},
    {"n": "TABS", "sub": "挂车防抱死刹车", "ic": "tabs", "to": "ebs"},
    {"n": "ECAS", "sub": "空气悬架", "ic": "ecas", "to": "ebs"},
    {"n": "ADAS", "sub": "摄像头/雷达", "ic": "adas", "to": "prompt"},
    {"n": "其他系统", "sub": "CAN 总线", "ic": "other", "to": "prompt"},
    {"n": "EPB", "sub": "电子驻车制动", "ic": "epb", "to": "prompt"},
    {"n": "Retarder", "sub": "缓速器系统", "ic": "retarder", "to": "prompt"},
    {"n": "AMT", "sub": "自动变速箱系统", "ic": "amt", "to": "prompt"},
]

ADVANCED_ITEMS = [
    {"n": "CAN 节点搜索", "ic": "can", "to": "can"},
    {"n": "读 OBD 电压", "ic": "obd", "to": "prompt"},
    {"n": "EOBD 通用诊断", "ic": "eobd", "to": "prompt"},
    {"n": "车辆年检", "ic": "check", "to": "prompt"},
]

EBS_ECU = [
    "EBS 系统自识别", "威伯科 WABCO-EBS3", "威伯科 WABCO-EBS1(K线)",
    "威伯科 WABCO-EBS1(K线-奔驰)", "克诺尔 KNORR-EBS5", "科密 KORMEE-EBS/IEBS",
    "万安 VE-EBS",
]

EBS_FUNCS = [
    {"n": "系统版本信息", "d": "电控系统软件/硬件版本", "to": "ebs-info"},
    {"n": "故障码功能", "d": "读取 / 解析 / 清除 DTC", "to": "ebs-dtc"},
    {"n": "数据流功能", "d": "实时数据流监测与录制", "to": "ebs-dataflow"},
    {"n": "功能测试", "d": "执行器 / 传感器测试", "to": "ebs-test"},
    {"n": "匹配设置", "d": "参数配置与编码", "to": "ebs-match"},
]

EBS_INFO = [
    ["系统供应商", "威伯科 WABCO"], ["ECU 部件号", "04L 906 056 HX"],
    ["软件版本", "V20.03"], ["硬件版本", "H05"],
    ["Bootloader 版本", "8.10.0"], ["诊断协议", "UDS / ISO 14229"],
    ["CAN 总线速率", "500 kbps"], ["VIN 码", "LSVAM4187C2123456"],
    ["系统日期", "2026-08-25"], ["编程次数", "17"], ["里程数", "42,680 km"],
]

EBS_DTC = [
    ["P01000F9", "空气质量计(HFM)的电源线过高", "当前故障"],
    ["P019312", "轨压传感器电压信号高于上限", "当前故障"],
    ["P0251F1", "高压油泵油量计量单元(MelN) 驱动电路开路", "当前故障"],
    ["P0098J3", "(轨压)压力控制阀(PCV)驱动电路开路", "当前故障"],
    ["P024212", "增压压力传感器电压信号高于上限", "当前故障"],
    ["P21C713", "外部继电器开路故障", "当前故障"],
    ["P043517", "SCR 催化剂上游温度传感器信号电压过高", "当前故障"],
    ["P203FF8", "尿素液位低激活锁死", "当前故障"],
    ["P213A13", "废气再循环(EGR) H桥驱动电路开路", "当前故障"],
    ["P208A13", "里程表驱动电路开路", "当前故障"],
]

EBS_DF = [
    {"n": "点火开关信号", "u": "", "k": "key"}, {"n": "发动机转速", "u": "转/分钟", "k": "rpm"},
    {"n": "低怠速设定值", "u": "转/分钟", "k": "idleL"}, {"n": "喷油量设定值", "u": "毫克/冲程", "k": "injT"},
    {"n": "当前喷油量", "u": "毫克/冲程", "k": "injN"}, {"n": "1 缸发动机转速", "u": "转/分钟", "k": "cyl1"},
    {"n": "2 缸发动机转速", "u": "转/分钟", "k": "cyl2"}, {"n": "3 缸发动机转速", "u": "转/分钟", "k": "cyl3"},
    {"n": "4 缸发动机转速", "u": "转/分钟", "k": "cyl4"}, {"n": "发动机状态", "u": "", "k": "engSt"},
    {"n": "发动机运行时间", "u": "秒", "k": "engTime"}, {"n": "环境温度", "u": "°C", "k": "ambT"},
    {"n": "进气温度", "u": "°C", "k": "inT"}, {"n": "大气压力", "u": "kPa", "k": "atmP"}, {"n": "系统电压", "u": "V", "k": "batV"},
]

EBS_TEST = [
    ["1 缸喷油器断缸测试", "就绪", "ok", "act"], ["2 缸喷油器断缸测试", "就绪", "ok", "act"],
    ["冷却风扇低速测试", "就绪", "ok", "act"], ["冷却风扇高速测试", "就绪", "ok", "act"],
    ["空调压缩机离合器", "就绪", "ok", "act"], ["EGR 阀开度控制", "受限", "warn", "lock"],
    ["节气门自适应复位", "就绪", "ok", "act"], ["排气制动阀", "就绪", "ok", "act"],
]

MATCH_GROUPS = [
    {"n": "整车参数 1", "items": [
        {"k": "EBS 功能参数", "v": "单 ECU", "t": "select", "opts": ["单 ECU", "集成式", "分体式"]},
        {"k": "车辆类型", "v": "牵引车", "t": "select", "opts": ["牵引车", "半挂车", "自卸车"]},
        {"k": "通信波特率 (KB)", "v": "500", "t": "select", "opts": ["125", "250", "500", "1000"]},
        {"k": "整车储气筒压力", "v": "8.0", "t": "select", "opts": ["8.0", "8.5", "9.0", "9.5", "10.0"]},
        {"k": "是否识别 CAN 故障", "v": "使能", "t": "select", "opts": ["使能", "禁止"]},
    ]},
    {"n": "桥轴轮间距 ESC", "items": [
        {"k": "ESC 静态检测", "v": "使能", "t": "radio", "opts": ["使能", "禁止"]},
        {"k": "ESC 动态检测", "v": "使能", "t": "radio", "opts": ["使能", "禁止"]},
    ]},
    {"n": "车轮制动器控制", "items": [
        {"k": "制动器控制模式", "v": "前盘后鼓", "t": "select", "opts": ["前盘后鼓", "前后盘", "前鼓后鼓", "前后鼓盘"]},
        {"k": "悬架型式", "v": "气囊", "t": "select", "opts": ["空载", "满载", "气囊", "钢板"]},
        {"k": "车型", "v": "6×4", "t": "input"},
    ]},
    {"n": "轴荷", "items": [
        {"k": "一轴轴荷", "v": "", "t": "input"}, {"k": "二轴轴荷", "v": "", "t": "input"},
        {"k": "三轴轴荷", "v": "", "t": "input"},
    ]},
    {"n": "ecu 报文发送", "items": [
        {"k": "TSC1_ER", "v": "使能", "t": "radio", "opts": ["使能", "禁止"]},
        {"k": "TSC1_DR", "v": "使能", "t": "radio", "opts": ["使能", "禁止"]},
        {"k": "HRW", "v": "使能", "t": "radio", "opts": ["使能", "禁止"]},
    ]},
]

CAN_LIST = [
    "CAN 网络扫描(OBD:6和14针脚网络)",
    "CAN 网络扫描(OBD:3和11针脚网络)",
    "CAN 网络扫描(OBD:11和12针脚网络)-重汽",
    "CAN 网络扫描(OBD:8和12针脚网络)-东风",
    "CAN 网络扫描(OBD:1和9针脚网络)-潍柴",
    "整车 CAN 网络扫描【快速扫描】",
]

# ── 设置（settings 页） ──

SETTINGS = [
    {"n": "主题", "d": "深色/浅色模式（白天与黑夜工作场景）", "type": "theme", "cur": "dark"},
    {"n": "语言", "d": "界面显示语言", "type": "select", "options": ["简体中文", "繁體中文", "English"], "cur": "简体中文"},
    {"n": "字体大小", "d": "界面文字显示大小", "type": "select", "options": ["小", "标准", "大"], "cur": "标准"},
    {"n": "电源管理", "d": "暗屏时间 · 自动关机", "type": "select",
     "options": ["暗屏 5min 关机 15min", "暗屏 10min 关机 30min", "暗屏 15min 关机 60min", "暗屏 30min 关机 60min", "从不"],
     "cur": "暗屏 10min 关机 30min"},
    {"n": "屏幕亮度", "d": "当前亮度", "type": "slider", "min": 0, "max": 100, "val": 80},
    {"n": "系统音量", "d": "提示音与按键音", "type": "slider", "min": 0, "max": 100, "val": 80},
    {"n": "单位制", "d": "压力 / 温度 / 长度", "type": "select", "options": ["公制 (kPa / °C / mm)", "英制 (psi / °F / in)"], "cur": "公制 (kPa / °C / mm)"},
    {"n": "启动界面", "d": "应用启动时默认显示页", "type": "select", "options": ["主界面", "设备选择", "高级功能"], "cur": "主界面"},
    {"n": "数据自动上传", "d": "诊断记录同步至云端", "type": "toggle", "val": True},
    {"n": "清除缓存", "d": "释放本地存储空间", "type": "action", "action": "clearCache"},
    {"n": "关于设备", "d": "版本信息 · 序列号", "type": "about"},
]

# ── 软件更新 ──

UPDATES = [
    {"n": "软件", "ic": "software", "rows": [
        {"k": "软件版本", "v": "2.4.1", "new": "2.4.3"},
        {"k": "诊断模板", "v": "3.6.2", "new": "3.6.5"},
        {"k": "文件大小", "v": "186 MB"},
        {"k": "更新内容", "v": "优化国六诊断 / 新增远程控制"},
    ], "btn": "立即更新", "btnCls": ""},
    {"n": "硬件", "ic": "hardware", "rows": [
        {"k": "固件版本", "v": "1.8.7"}, {"k": "传感器驱动", "v": "已最新"}, {"k": "更新内容", "v": "暂无更新"},
    ], "btn": "暂无可用更新", "btnCls": "disabled"},
    {"n": "首页", "ic": "home", "rows": [
        {"k": "当前首页", "v": "产品介绍", "link": True},
        {"k": "资源数据", "v": "本地资源解压"},
        {"k": "网页缓存", "v": "清理网页缓存", "link": True},
        {"k": "更新内容", "v": "界面交互优化"},
    ], "btn": "首页设置", "btnCls": "green"},
]

# ── 远程协助 ──

REMOTE_CTRL_STEPS = [
    ("第一步", "请对端设备联网，并按照操作 <b>【协助】→【要求对方控制我的设备】</b>"),
    ("第二步", "请对端设备告诉您，他设备上显示的 <b>ID 号</b>"),
    ("第三步", "在右侧输入框输入对端 ID，点击「连接对方」等待对方确认"),
]

# ── 建议排查步骤（AI 诊断页右详情唯一数据源，5 步富文本） ──

DIAG_STEPS = [
    {"title": "轨压传感器及其5V供电、信号、搭铁线路",
     "lineDef": "线路定义说明（依据此车技术资料）：轨压传感器插头",
     "pins": [
         {"n": "1号针脚", "d": "搭铁，连接至ECU A25，开路、静态及低速参考均为0V。"},
         {"n": "2号针脚", "d": "信号线，连接至ECU A26，开路参考5V，连接线束静态约0.5V，低怠速约1.66V。"},
         {"n": "3号针脚", "d": "5V供电，连接至ECU A07，开路、静态及低速参考均为5V。"},
     ],
     "step1": "查什么——查传感器三根线是否全部正常",
     "position": "轨压传感器安装在发动机高压共轨管上，通常在共轨管端部或上方；未完全泄压前严禁拆卸传感器和任何高压油管。",
     "how": "钥匙ON，不启动，拔下传感器插头；黑表笔接电池负极，红表笔依次测车身线束插头端的3号、1号、2号针脚。",
     "see": "3号脚应为5V、1号脚应为0V。拔插头后的2号脚约为5V；任一异常先查插头腐蚀、线束磨损及共用5V模块。",
     "aid": "您也可以使用远驰系列的配套产品（如远驰的传感器检测模块，或全能王或者电路宝）对传感器进行针对性的驱动/信号模拟排查。",
     "warn": "表笔只能从插头背部探测，不能用粗探针撑大端子。"},
    {"title": "高压油泵常开式燃油计量单元及驱动线路",
     "lineDef": "线路定义说明（依据此车技术资料）：燃油计量单元（IMV）插头",
     "pins": [
         {"n": "1号针脚", "d": "ECU 控制端（PWM），参考占空比 20%~80%。"},
         {"n": "2号针脚", "d": "供电，钥匙ON 时为 12V 蓄电池电压。"},
         {"n": "3号针脚", "d": "搭铁，连接至 ECU 内部地。"},
     ],
     "step1": "查什么——查 IMV 线圈阻值与控制波形",
     "position": "IMV 集成于高压油泵内部，插头位于油泵顶部，靠近缸体外侧。",
     "how": "关闭钥匙，拔下 IMV 插头；用万用表测 1-3 脚阻值（正常 2.5~4.5Ω）。启动后用示波器测 1 脚 PWM 波形。",
     "see": "线圈开路/短路→更换油泵总成；PWM 波形异常→查 ECU 输出端与线束。",
     "aid": "远驰 IMV 检测模块可直接读取占空比与反馈电流，无需拆解油泵。",
     "warn": "高压油管内仍有残余油压，拆卸前需充分泄压，避免燃油喷射伤人。"},
    {"title": "空气流量计总成及进气温度信号线路",
     "lineDef": "线路定义说明（依据此车技术资料）：空气流量计（MAF）插头",
     "pins": [
         {"n": "1号针脚", "d": "12V 供电，钥匙ON 时为蓄电池电压。"},
         {"n": "2号针脚", "d": "信号输出，怠速约 1.0~1.5V，急加速跳变至 4V 以上。"},
         {"n": "3号针脚", "d": "搭铁。"},
         {"n": "4号针脚", "d": "进气温度信号，参考电压 0.5~3.5V（随温度变化）。"},
     ],
     "step1": "查什么——查供电、信号、搭铁及 IAT信号",
     "position": "MAF 位于进气管路中，靠近节气门上游。",
     "how": "钥匙ON，插头不拔，背测针脚：1 脚 12V、3 脚 0V、4 脚随温度变化。启动后 2 脚信号应随油门开度变化。",
     "see": "1 脚无电压→查保险与继电器；2 脚信号恒定→MAF 损坏；4 脚异常→IAT 传感器损坏。",
     "aid": "远驰示波器功能可同步监测 2 脚与 4 脚波形，快速区分 MAF 与 IAT 故障。",
     "warn": "禁止在发动机运转时拔插 MAF 插头，可能损坏 ECU 输入端。"},
    {"title": "DPF压差传感器、取压软管及线路",
     "lineDef": "线路定义说明（依据此车技术资料）：DPF 压差传感器插头",
     "pins": [
         {"n": "1号针脚", "d": "5V 供电。"},
         {"n": "2号针脚", "d": "信号输出，怠速约 0.5V，再生时跳升至 2~3V。"},
         {"n": "3号针脚", "d": "搭铁。"},
     ],
     "step1": "查什么——查取压管路是否堵塞/漏气",
     "position": "DPF 压差传感器安装在 DPF 前后两端，连接两根取压软管。",
     "how": "熄火后拆下两根取压软管，目视检查有无积碳堵塞；用气枪从一端吹气，应通畅无阻。钥匙ON 测 1 脚 5V、3 脚 0V。",
     "see": "管路堵塞→清理或更换；1 脚无 5V→查传感器供电线束；2 脚信号恒为 0→传感器损坏。",
     "aid": "远驰 DPF 检测模块可同时监测压差、排温和再生状态。",
     "warn": "DPF 内部温度极高，再生后立即拆卸可能被烫伤。"},
    {"title": "EGR阀总成及驱动、位置反馈线路",
     "lineDef": "线路定义说明（依据此车技术资料）：EGR 阀插头",
     "pins": [
         {"n": "1号针脚", "d": "12V 供电。"},
         {"n": "2号针脚", "d": "PWM 控制信号。"},
         {"n": "3号针脚", "d": "位置反馈信号，0.5~4.5V。"},
         {"n": "4号针脚", "d": "搭铁。"},
     ],
     "step1": "查什么——查驱动信号与位置反馈",
     "position": "EGR 阀位于排气歧管与进气歧管之间。",
     "how": "钥匙ON，背测 1 脚 12V、4 脚 0V；启动后用示波器观察 2 脚 PWM 与 3 脚反馈同步变化。",
     "see": "1 脚无电压→查保险；2 脚无 PWM→ECU 未发出指令或 EGR 损坏；3 脚无反馈→位置传感器损坏。",
     "aid": "远驰 EGR 主动驱动模块可强制开启 EGR，辅助判断阀门机械卡滞。",
     "warn": "高温区域作业，佩戴隔热手套，避免烫伤。"},
]

# ── AI 动态信息（演示时序） ──

DYN_MSGS = [
    {"cls": "", "text": "正在与车辆通讯中..."},
    {"cls": "", "text": "正在识别OBD信息..."},
    {"cls": "", "text": "正在识别车辆信息..."},
    {"cls": "", "text": "正在识别发动机信息..."},
    {"cls": "thinking", "text": "正在思考中..."},
    {"cls": "done", "text": "诊断完成，已生成诊断报告。"},
]

# ── 演示车辆 / 故障码 / AI 结果（AI 诊断页降级填充） ──

DEMO_VEHICLE = {
    "vin": "LSVAM4187C2123456",
    "model": "2023 大众 途观 L 330TSI",
    "mileage": "42,680 km",
    "ecu": "云内_EDC17CV54",
}

DEMO_FAULTS = [
    {"code": "P0301", "desc": "第 1 缸失火检测到", "status": "cur"},
    {"code": "P0420", "desc": "催化转换器效率低于阈值", "status": "cur"},
    {"code": "U0121", "desc": "与 ABS 控制模块失去通信", "status": "his"},
]

DEMO_AI_REPORT = {
    "overallConclusion": "多个故障码集中在排放相关传感器链路，其中氧传感器反馈异常概率最高，优先检查其供电/信号波形。",
    "diagnosisList": [
        {"faultPoint": "氧传感器故障", "probability": "75%",
         "simpleExplanation": "检测到排放数据异常，氧传感器可能需要更换。此故障常引起油耗增加或怠速不稳。",
         "guideSteps": ["第一步，读取氧传感器电压波形，正常应在 0.1~0.9V 之间周期性跳变。",
                        "第二步，若波形恒定，检查氧传感器供电 12V 与加热器线路。"]},
        {"faultPoint": "催化转化器问题", "probability": "15%",
         "simpleExplanation": "催化转化效率低下。可能需要检修。由于长期积碳或尾气温度异常常引发。",
         "guideSteps": ["检查三元催化器前后氧传感器信号差值，判断转化效率。"]},
        {"faultPoint": "油箱盖未拧紧", "probability": "10%",
         "simpleExplanation": "燃油蒸汽泄漏触发发动机警告灯。只需重新拧紧并解锁后系统后自复位。",
         "guideSteps": ["重新拧紧油箱盖，行驶一段里程后观察警告灯是否熄灭。"]},
    ],
}

DEMO_REPORTS = [
    {"time": "2026-08-28 14:48", "dev": "DTS", "summary": "发动机故障灯亮，氧传感器故障（75%）"},
    {"time": "2026-08-27 09:32", "dev": "X5", "summary": "ABS 系统通信故障，偶发误报"},
    {"time": "2026-08-26 16:20", "dev": "正德友邦", "summary": "DPF 频繁再生，排气温度异常"},
]

# ── 账户 ──

ACCOUNT = {
    "name": "李翔", "avatar": "LX", "role": "认证技师 · 中级",
    "phone": "+86 138 0000 1234", "email": "lixiang@lunchi.tech",
    "no": "LC20260828", "shop": "北京·朝阳·华强汽修厂", "reg": "2024-03-15",
    "stat": [
        ("授权状态", "已激活", "ok"), ("有效期至", "2027-12-31", ""),
        ("诊断次数", "387", ""), ("本周诊断", "23", ""),
        ("绑定设备", "3 台", ""), ("云端报告", "52 份", ""),
        ("存储占用", "3.6 GB / 10 GB", ""),
    ],
}

# ── 页面配置（顶栏 title + 底栏上下文按钮，映射 HTML PAGE_CFG） ──

PAGE_CFG = {
    "home": {"title": None, "btns": [{"label": "开始AI智能诊断", "act": "startAi", "cls": "primary"}]},
    "special": {"title": "专用诊断仪", "btns": [{"label": "返回", "to": "home"}]},
    "advanced": {"title": "高级功能", "btns": [{"label": "返回", "to": "home"}]},
    "ebs": {"title": "电控系统", "btns": [{"label": "返回", "to": "special"}]},
    "ebs-func": {"title": "诊断功能", "btns": [{"label": "返回", "to": "ebs"}]},
    "ebs-info": {"title": "系统版本信息", "btns": [{"label": "返回", "to": "ebs-func"}]},
    "ebs-dtc": {"title": "故障码功能", "btns": [
        {"label": "帮助", "act": "dtcHelp"}, {"label": "复制故障码", "act": "dtcCopy"},
        {"label": "AI 诊断", "act": "dtcAi"}, {"label": "返回", "to": "ebs-func", "cls": "primary"}]},
    "ebs-dataflow": {"title": "数据流功能", "btns": [
        {"label": "重启", "act": "dfRestart"}, {"label": "快", "act": "dfFast"},
        {"label": "慢", "act": "dfSlow"}, {"label": "暂停", "act": "dfPause"},
        {"label": "返回", "to": "ebs-func", "cls": "primary"}]},
    "ebs-test": {"title": "功能测试", "btns": [{"label": "返回", "to": "ebs-func"}]},
    "ebs-match": {"title": "匹配设置", "btns": [{"label": "返回", "to": "ebs-func"}]},
    "can": {"title": "CAN 网络扫描", "btns": [{"label": "返回", "to": "advanced"}]},
    "account": {"title": "账户信息", "btns": [{"label": "返回", "to": "home"}]},
    "report": {"title": "诊断报告", "btns": [{"label": "返回", "to": "home"}]},
    "update": {"title": "软件更新", "btns": [{"label": "返回", "to": "home"}]},
    "settings": {"title": "系统设置", "btns": [{"label": "返回", "to": "home"}]},
    "remote": {"title": "远程协助", "btns": [{"label": "返回", "to": "home"}]},
    "remote-ctrl": {"title": "远程控制对方设备", "btns": [{"label": "取消", "act": "cancelRemote"}]},
    "remote-invite": {"title": "邀请对方控制我的设备", "btns": [{"label": "返回", "to": "remote"}]},
    "ai-diagn": {"title": None, "btns": [{"label": "返回", "to": "home"}]},
}
