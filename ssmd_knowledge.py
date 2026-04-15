"""
SSMD Conversational AI Engine
A GPT-like conversational knowledge engine for SSMD.
Uses intent detection, entity extraction, dynamic response composition,
and conversation memory for natural-sounding answers.
"""

import re
import random
from collections import OrderedDict

# ══════════════════════════════════════════════════════════════
#  KNOWLEDGE DATA
# ══════════════════════════════════════════════════════════════
SSMD_VERSION = "2026.03.16.76a2"
SSMD_PACKAGE = "ssmd_2026.03.16.76a2_lin"

PLATFORMS = {"CWF": "Clear Water Forest", "GNR": "Granite Rapids",
             "SRF": "Sierra Forest", "DMR": "Diamond Rapids"}

SUPPORTED_OS = [
    {"os": "Ubuntu 23.04", "kernel": "5.19 or newer"},
    {"os": "CentOS 8", "kernel": "5.19 or newer"},
    {"os": "Windows Server 2022", "note": "不支援 CWF"},
]

TOOLS = {
    "ssmd": {"name": "SSMD", "desc": "主程式，執行壓力測試與記憶體診斷",
             "usage": "sudo ./ssmd -f <flow_file> [options]",
             "options": {"-f <file>": "指定 flow 設定檔", "-u <key=value>": "覆寫 user variable",
                         "-t <seconds>": "設定執行時間", "-h": "顯示說明"}},
    "ssmon": {"name": "SSMON", "desc": "即時系統遙測監測",
              "usage": "sudo ./ssmon [options]",
              "options": {"-l <level>": "層級 0=Socket 1=Core 2=Thread",
                          "-p <profile>": "1=CPU 2=Mem 3=All",
                          "-c <config>": "指定設定檔", "-d <delay>": "更新延遲", "-h": "說明"}},
    "sysinfo": {"name": "SysInfo", "desc": "系統資訊查詢",
                "usage": "sudo ./sysinfo [options]",
                "options": {"-e": "列出所有支援項目", "-c -p": "處理器資訊",
                            "-d -o": "DIMM 資訊"}},
}

# ── Flow definitions (full data for dynamic composition) ─────
FLOWS = OrderedDict([
    ("flowStressTdpCWF.json", {
        "category": "TDP", "cat_name": "TDP 壓力測試",
        "desc": "CWF 平台 TDP 壓力測試，可選超頻模式逼近 TDP 功耗上限",
        "cmd": "sudo ./ssmd -f Flows/TDP/flowStressTdpCWF.json",
        "plugin": "FlowPluginMixedWorkloads",
        "purpose": "驗證系統在 TDP 功耗下的穩定性",
        "vars": OrderedDict([
            ("oc_enable", {"d": "0", "t": "啟用超頻（⚠️ 可能損壞系統）。設 1 開啟"}),
            ("near_tdp_target", {"d": "97.0", "t": "超頻功耗目標，TDP 的百分比"}),
            ("oc_voltchange_max", {"d": "200", "t": "最大允許電壓調整 (mV)"}),
            ("oc_voltchange_amount", {"d": "2", "t": "每步電壓增量 (1/1024 mV)"}),
            ("oc_voltchange_delay", {"d": "700", "t": "電壓調整間延遲 (ms)"}),
            ("corestress_intensity", {"d": "92", "t": "壓力強度百分比"}),
            ("corestress_socketmask", {"d": "0xf", "t": "Socket 遮罩"}),
            ("corestress_coremask", {"d": "0xfff...fff", "t": "Core 遮罩"}),
            ("telemetry", {"d": "true", "t": "收集遙測數據"}),
            ("telemetry_period", {"d": "100", "t": "遙測頻率 (ms)"}),
        ]),
        "tips": [
            "Near-TDP 模式指令：`sudo ./ssmd -f Flows/TDP/flowStressTdpCWF.json -u oc_enable=1`",
            "預設壓力強度是 92%，比 CoreStress 的 100% 低一些，是為了搭配超頻",
            "超頻時會自動逐步提高 core 和 uncore 電壓，直到功耗達到目標值",
        ],
    }),
    ("flowStressCoreAVX256CWF.json", {
        "category": "CoreStress", "cat_name": "核心壓力測試",
        "desc": "CWF 平台 AVX256 核心壓力測試，驅動所有核心產生高功耗",
        "cmd": "sudo ./ssmd -f Flows/CoreStress/flowStressCoreAVX256CWF.json",
        "plugin": "FlowPluginMixedWorkloads",
        "purpose": "測試 CPU 核心在持續壓力下的穩定性與散熱能力",
        "vars": OrderedDict([
            ("corestress_socketmask", {"d": "0xf", "t": "Socket 遮罩"}),
            ("corestress_coremask", {"d": "0xfff...fff", "t": "Core 遮罩"}),
            ("corestress_intensity", {"d": "100", "t": "壓力強度百分比 (0-100)"}),
            ("corestress_dutycycleperiod", {"d": "10000000", "t": "Duty cycle 週期 (TSC ticks)"}),
            ("telemetry", {"d": "true", "t": "收集遙測數據"}),
            ("telemetry_period", {"d": "50", "t": "遙測頻率 (ms)"}),
            ("telemetry_filename", {"d": '""', "t": "遙測輸出檔 (JSON)，空=不記錄"}),
        ]),
        "tips": [
            "這是最基本的核心壓力測試，使用 AVX256 指令集",
            "如果只想測特定核心，可以調整 coremask",
        ],
    }),
    ("flowStressPMaxCWF.json", {
        "category": "PMax", "cat_name": "PMax 最大功耗壓力",
        "desc": "CWF 平台 PMax 測試，結合 Core+Uncore+Link 壓力，產生 Sleep→Idle→Stress 循環",
        "cmd": "sudo ./ssmd -f Flows/PMax/flowStressPMaxCWF.json",
        "plugin": "FlowPluginMixedWorkloads",
        "purpose": "驅動系統達到最大功耗，測試電源供應和散熱極限",
        "vars": OrderedDict([
            ("sleep_time", {"d": "5000", "t": "Sleep 階段 (ms)"}),
            ("idle_time", {"d": "5000", "t": "Idle 階段 (ms)"}),
            ("stress_time", {"d": "3000", "t": "Stress 階段 (ms)"}),
            ("corestress", {"d": "true", "t": "啟用核心壓力"}),
            ("corestress_intensity", {"d": "100", "t": "核心壓力強度"}),
            ("uncorestress", {"d": "true", "t": "啟用 Uncore 壓力"}),
            ("uncorestress_intensity", {"d": "100", "t": "Uncore 強度"}),
            ("linkstress", {"d": "false", "t": "啟用 Link 壓力"}),
            ("linkstress_intensity", {"d": "100", "t": "Link 強度"}),
            ("telemetry", {"d": "false", "t": "收集遙測數據"}),
        ]),
        "tips": [
            "PMax 與 TDP 的關鍵差異：PMax 會做 Sleep→Idle→Stress 循環，TDP 是持續壓力",
            "預設不含 Link stress，要加的話設 `linkstress=true`",
            "這個測試是最吃電的，確保散熱系統充足",
        ],
    }),
    ("flowStressDdrWriteAVX128.json", {
        "category": "DdrStress", "cat_name": "DDR 記憶體壓力",
        "desc": "AVX128 DDR 寫入壓力測試",
        "cmd": "sudo ./ssmd -f Flows/DdrStress/flowStressDdrWriteAVX128.json",
        "plugin": "FlowPluginMixedWorkloads",
        "purpose": "對 DIMM 產生溫度與功耗壓力",
        "vars": OrderedDict([
            ("workload", {"d": "WLPlugin_stress_mlcx_wronly_avx128nt", "t": "Workload plugin"}),
            ("lpu_select_expr", {"d": "15%/numa", "t": "LPU 選擇 (CLI 用 pct 代替 %)"}),
            ("memorystress_memsize", {"d": "${_L3*2/_CORES_PER_SOCKET}", "t": "每執行緒記憶體"}),
            ("memorystress_intensity", {"d": "100", "t": "壓力強度"}),
        ]),
        "tips": ["AVX128 是最基本的，頻寬較低但相容性最好"],
    }),
    ("flowStressDdrWriteAVX256.json", {
        "category": "DdrStress", "cat_name": "DDR 記憶體壓力",
        "desc": "AVX256 DDR 寫入壓力測試（推薦）",
        "cmd": "sudo ./ssmd -f Flows/DdrStress/flowStressDdrWriteAVX256.json",
        "plugin": "FlowPluginMixedWorkloads",
        "purpose": "對 DIMM 產生中高程度的溫度與功耗壓力",
        "vars": OrderedDict([
            ("workload", {"d": "WLPlugin_stress_mlcx_wronly_avx256nt", "t": "Workload plugin"}),
            ("lpu_select_expr", {"d": "15%/numa", "t": "LPU 選擇"}),
            ("memorystress_memsize", {"d": "${_L3*2/_CORES_PER_SOCKET}", "t": "每執行緒記憶體"}),
            ("memorystress_intensity", {"d": "100", "t": "壓力強度"}),
        ]),
        "tips": ["這是 DDR 壓力測試中最常用的版本"],
    }),
    ("flowStressDdrWriteAVX512.json", {
        "category": "DdrStress", "cat_name": "DDR 記憶體壓力",
        "desc": "AVX512 DDR 寫入壓力測試",
        "cmd": "sudo ./ssmd -f Flows/DdrStress/flowStressDdrWriteAVX512.json",
        "plugin": "FlowPluginMixedWorkloads",
        "purpose": "最大 DDR 頻寬壓力",
        "vars": OrderedDict([
            ("workload", {"d": "WLPlugin_stress_mlcx_wronly_avx512nt", "t": "Workload plugin"}),
            ("lpu_select_expr", {"d": "15%/numa", "t": "LPU 選擇"}),
            ("memorystress_memsize", {"d": "${_L3*2/_CORES_PER_SOCKET}", "t": "每執行緒記憶體"}),
            ("memorystress_intensity", {"d": "100", "t": "壓力強度"}),
        ]),
        "tips": ["AVX512 頻寬最高，但不是所有平台都支援"],
    }),
    ("flowStressUpiLinks.json", {
        "category": "InterconnectStress", "cat_name": "UPI 互連壓力",
        "desc": "UPI Link 壓力測試，測試 Socket 間互連流量",
        "cmd": "sudo ./ssmd -f Flows/InterconnectStress/flowStressUpiLinks.json",
        "plugin": "FlowPluginMixedWorkloads",
        "purpose": "驗證多 Socket 系統的 UPI 連結穩定性和頻寬",
        "vars": OrderedDict([
            ("workload", {"d": "WLPlugin_stress_mlcx_wronly_avx128", "t": "Workload plugin"}),
            ("max_threads", {"d": "528", "t": "最大執行緒數"}),
            ("socketmask", {"d": "0xf", "t": "Socket 遮罩"}),
            ("coremask", {"d": "0xFFF...FFF", "t": "Core 遮罩"}),
            ("threadmask", {"d": "0x3", "t": "Thread 遮罩"}),
            ("intensity", {"d": "100", "t": "壓力強度"}),
        ]),
        "tips": [
            "需要多 Socket 系統才有意義",
            "使用 threads_sharing_memory=2 讓 thread pair 跨 NUMA 共享記憶體",
        ],
    }),
    ("flowMemScreenRead.json", {
        "category": "MemoryScreen", "cat_name": "記憶體篩檢",
        "desc": "DDR 讀取篩檢",
        "cmd": "sudo ./ssmd -f Flows/MemoryScreen/flowMemScreenRead.json",
        "plugin": "FlowPluginMemoryScreen",
        "purpose": "快速讀取測試，驗證記憶體讀取路徑完整性",
        "vars": OrderedDict([
            ("memsize", {"d": "0x40000000", "t": "篩檢大小 (0=全部)"}),
            ("blocksize", {"d": "0x800000", "t": "區塊大小"}),
            ("max_threads", {"d": "528", "t": "最大執行緒"}),
            ("memory_reserve", {"d": "15", "t": "OS 保留 %"}),
            ("numa_focus", {"d": "near", "t": "NUMA 策略 (near/far/numaX)"}),
        ]),
        "tips": ["如果要快速檢查記憶體，read screen 速度最快"],
    }),
    ("flowMemScreenWrite.json", {
        "category": "MemoryScreen", "cat_name": "記憶體篩檢",
        "desc": "DDR 寫入篩檢",
        "cmd": "sudo ./ssmd -f Flows/MemoryScreen/flowMemScreenWrite.json",
        "plugin": "FlowPluginMemoryScreen",
        "purpose": "寫入測試，驗證記憶體寫入路徑完整性",
        "vars": OrderedDict([
            ("memsize", {"d": "0x80000000", "t": "篩檢大小"}),
            ("blocksize", {"d": "0x800000", "t": "區塊大小"}),
            ("memory_reserve", {"d": "15", "t": "OS 保留 %"}),
            ("numa_focus", {"d": "near", "t": "NUMA 策略"}),
        ]),
        "tips": [],
    }),
    ("flowMemScreenMarch.json", {
        "category": "MemoryScreen", "cat_name": "記憶體篩檢",
        "desc": "March C- 完整記憶體診斷演算法",
        "cmd": "sudo ./ssmd -f Flows/MemoryScreen/flowMemScreenMarch.json",
        "plugin": "FlowPluginMemoryScreen",
        "purpose": "最完整的記憶體故障偵測，使用 March C- 演算法",
        "vars": OrderedDict([
            ("memsize", {"d": "0", "t": "篩檢大小 (0=全部)"}),
            ("blocksize", {"d": "0x40000000", "t": "區塊大小 (1GB)"}),
            ("max_threads", {"d": "32", "t": "最大執行緒"}),
            ("memory_reserve", {"d": "15", "t": "OS 保留 %"}),
            ("numa_reserve", {"d": "0x80000000", "t": "每 NUMA 保留"}),
            ("pagetracking", {"d": "false", "t": "追蹤已篩檢 physical page"}),
            ("numa_focus", {"d": '""', "t": "NUMA 目標 (空=全部)"}),
        ]),
        "tips": [
            "March C- 是業界標準記憶體診斷演算法，覆蓋率最高",
            "全記憶體篩檢需要較長時間，建議先用小容量測試",
            "演算法：`{ A(w1,w0,r0,w1,r1) }` + `{ A(w0); U(r0,w1); U(r1,w0); D(r0,w1); D(r1,w0); D(r0) }`",
        ],
    }),
    ("flowMemScreenStuckAt.json", {
        "category": "MemoryScreen", "cat_name": "記憶體篩檢",
        "desc": "Stuck-At 記憶體故障偵測",
        "cmd": "sudo ./ssmd -f Flows/MemoryScreen/flowMemScreenStuckAt.json",
        "plugin": "FlowPluginMemoryScreen",
        "purpose": "偵測記憶體 bit 卡住在 0 或 1 的故障",
        "vars": OrderedDict([
            ("memsize", {"d": "0", "t": "篩檢大小 (0=全部)"}),
            ("blocksize", {"d": "0x40000000", "t": "區塊大小"}),
            ("max_threads", {"d": "32", "t": "最大執行緒"}),
            ("pagetracking", {"d": "false", "t": "追蹤 physical page"}),
            ("numa_focus", {"d": '""', "t": "NUMA 目標"}),
        ]),
        "tips": ["Stuck-At 測試速度比 March 快，適合快速初步篩檢"],
    }),
    ("flowTurboCheckCWF.json", {
        "category": "TurboCheck", "cat_name": "Turbo 頻率驗證",
        "desc": "CWF 平台 Turbo 頻率驗證，支援多種測試模式",
        "cmd": "sudo ./ssmd -f Flows/TurboCheck/flowTurboCheckCWF.json",
        "plugin": "FlowPluginCorePerformance",
        "purpose": "驗證不同 active core 數量下 Turbo 頻率是否達標",
        "vars": OrderedDict([
            ("test_mode", {"d": "0x1", "t": "模式遮罩: Bit0=全核 Bit1=單核Max Bit2=Sweep"}),
            ("level_mask", {"d": "0x3F", "t": "測試層級遮罩"}),
            ("sweep_core_start", {"d": "1", "t": "Sweep 起始核心數"}),
            ("sweep_core_stop", {"d": "5", "t": "Sweep 結束核心數"}),
            ("sweep_core_step", {"d": "1", "t": "步進"}),
            ("workload_duration", {"d": "5000", "t": "每次迭代 (ms)"}),
            ("sweep_active_buckets", {"d": "0xFFFFFFFF", "t": "SST-PP TRL buckets"}),
            ("turbo_output_filename", {"d": '""', "t": "結果輸出檔"}),
        ]),
        "tips": [
            "test_mode=0x7 可以一次跑全部三種模式",
            "Sweep 模式會從 start 到 stop 逐步增加 active core 數",
            "此 flow 僅供參考用途，不用於正式 validation",
        ],
    }),
])

SSMON_CONFIGS = OrderedDict([
    ("ssmonConfigDefault.json", {"name": "Default", "desc": "綜合：頻率/電壓/溫度/功耗 + Memory/UPI/PCIe BW", "cmd": "sudo ./ssmon"}),
    ("ssmonConfigCpuBasic.json", {"name": "CPU Basic", "desc": "Core/Uncore/Compute/IO 域頻率詳情", "cmd": "sudo ./ssmon -c Configs/ssmonConfigCpuBasic.json"}),
    ("ssmonConfigMemBasic.json", {"name": "Memory Basic", "desc": "DIMM 溫度、功耗、讀寫頻寬", "cmd": "sudo ./ssmon -c Configs/ssmonConfigMemBasic.json"}),
    ("ssmonConfigCState.json", {"name": "C-State", "desc": "C0/C1/C6 Core + PC2/PC6 Package 殘留率", "cmd": "sudo ./ssmon -c Configs/ssmonConfigCState.json"}),
    ("ssmonConfigMinMax.json", {"name": "Min/Max", "desc": "Power/Temp/Voltage 的 Min/Avg/Max 統計", "cmd": "sudo ./ssmon -c Configs/ssmonConfigMinMax.json"}),
    ("ssmonConfigPcieBasic.json", {"name": "PCIe Basic", "desc": "PCIe 讀寫頻寬", "cmd": "sudo ./ssmon -c Configs/ssmonConfigPcieBasic.json"}),
    ("ssmonConfigUpiBasic.json", {"name": "UPI Basic", "desc": "UPI 發送/接收頻寬", "cmd": "sudo ./ssmon -c Configs/ssmonConfigUpiBasic.json"}),
    ("ssmonConfigProcState.json", {"name": "Processor State", "desc": "原始暫存器：CPUID/PlatformInfo/Power/Thermal", "cmd": "sudo ./ssmon -c Configs/ssmonConfigProcState.json"}),
    ("ssmonConfigTRL.json", {"name": "TRL", "desc": "頻率/Utilization/IPC/Power + Limit Log", "cmd": "sudo ./ssmon -c Configs/ssmonConfigTRL.json"}),
])

TELEMETRY_TYPES = {
    "PackagePower": "Package 功耗 (W)", "PackagePowerAlt": "Package 功耗替代讀數 (W)",
    "PackageTemperature": "Package 溫度 (°C)", "PlatformPower": "平台整體功耗 (W)",
    "ThreadCoreFrequency": "核心頻率 (MHz)", "UncoreFrequency": "Uncore 頻率 (MHz)",
    "UncoreVoltage": "Uncore 電壓 (V)", "CoreC0Residency": "C0 殘留率 (%)",
    "CoreC6Residency": "C6 殘留率 (%)", "ThreadUtilization": "使用率 (%)",
    "ThreadIPC": "IPC", "DdrDimmPower": "DIMM 功耗 (W)",
    "PackageLogThermalThrottle": "Thermal Throttle 日誌",
    "PackageLogProcHot": "PROCHOT 日誌",
    "PackageLogPowerLimit": "功耗限制日誌",
}

SYSINFO_TYPES = {
    "ProcessorCPUID": "處理器 CPUID", "EnabledCoreCount": "核心數", "EnabledThreadCount": "執行緒數",
    "CoreBaseFrequency": "基礎頻率 (MHz)", "CoreMaxFrequency": "最大頻率 (MHz)",
    "PackageTDP": "TDP (W)", "PackageMaxTemperature": "最大溫度 (°C)",
    "HwpEnable": "HWP 狀態", "SamplePart": "是否 Sample 部件",
    "RaplPL1Power": "PL1 功耗 (W)", "RaplPL2Power": "PL2 功耗 (W)",
}

QUICK_COMMANDS = OrderedDict([
    ("tdp_stress", {"desc": "TDP 壓力測試", "cmd": "sudo ./ssmd -f Flows/TDP/flowStressTdpCWF.json"}),
    ("near_tdp", {"desc": "Near-TDP（超頻）", "cmd": "sudo ./ssmd -f Flows/TDP/flowStressTdpCWF.json -u oc_enable=1", "note": "⚠️ 超頻可能損壞系統"}),
    ("avx256_stress", {"desc": "AVX256 核心壓力", "cmd": "sudo ./ssmd -f Flows/CoreStress/flowStressCoreAVX256CWF.json"}),
    ("max_turbo", {"desc": "Turbo 頻率驗證", "cmd": "sudo ./ssmd -f Flows/TurboCheck/flowTurboCheckCWF.json"}),
    ("pmax_stress", {"desc": "PMax 最大功耗", "cmd": "sudo ./ssmd -f Flows/PMax/flowStressPMaxCWF.json"}),
    ("ddr128", {"desc": "DDR 壓力 AVX128", "cmd": "sudo ./ssmd -f Flows/DdrStress/flowStressDdrWriteAVX128.json"}),
    ("ddr256", {"desc": "DDR 壓力 AVX256", "cmd": "sudo ./ssmd -f Flows/DdrStress/flowStressDdrWriteAVX256.json"}),
    ("ddr512", {"desc": "DDR 壓力 AVX512", "cmd": "sudo ./ssmd -f Flows/DdrStress/flowStressDdrWriteAVX512.json"}),
    ("upi", {"desc": "UPI 壓力", "cmd": "sudo ./ssmd -f Flows/InterconnectStress/flowStressUpiLinks.json"}),
    ("mem_read", {"desc": "Read 記憶體篩檢", "cmd": "sudo ./ssmd -f Flows/MemoryScreen/flowMemScreenRead.json"}),
    ("mem_write", {"desc": "Write 記憶體篩檢", "cmd": "sudo ./ssmd -f Flows/MemoryScreen/flowMemScreenWrite.json"}),
    ("mem_march", {"desc": "March 記憶體篩檢", "cmd": "sudo ./ssmd -f Flows/MemoryScreen/flowMemScreenMarch.json"}),
    ("mem_stuck", {"desc": "StuckAt 篩檢", "cmd": "sudo ./ssmd -f Flows/MemoryScreen/flowMemScreenStuckAt.json"}),
    ("mon_socket", {"desc": "Socket 監測", "cmd": "sudo ./ssmon"}),
    ("mon_core", {"desc": "Core 監測", "cmd": "sudo ./ssmon -l 1"}),
    ("mon_thread", {"desc": "Thread 監測", "cmd": "sudo ./ssmon -l 2"}),
    ("mon_cpu", {"desc": "CPU Profile 監測", "cmd": "sudo ./ssmon -p 1 -l 2"}),
    ("mon_mem", {"desc": "Memory Profile 監測", "cmd": "sudo ./ssmon -p 2 -l 2"}),
    ("mon_all", {"desc": "All Profile", "cmd": "sudo ./ssmon -p 3 -l 2"}),
    ("si_all", {"desc": "列出處理器項目", "cmd": "sudo ./sysinfo -e"}),
    ("si_cpu", {"desc": "處理器資訊", "cmd": "sudo ./sysinfo -c -p"}),
    ("si_dimm", {"desc": "DIMM 資訊", "cmd": "sudo ./sysinfo -d -o"}),
    ("driver", {"desc": "安裝驅動", "cmd": "cd Drivers && make && sudo insmod cpuaccess.ko"}),
])

DRIVER_INFO = {
    "linux": {
        "name": "CPU Access Driver (cpuaccess.ko)",
        "steps": [
            "安裝 kernel headers",
            "  CentOS: `sudo yum update && sudo yum install \"kernel-devel-$(uname -r)\"`",
            "  Ubuntu: `sudo apt-get update && sudo apt-get install linux-headers-$(uname -r)` 及 `sudo apt install gcc-12`",
            "編譯：`cd Drivers && make`",
            "載入：`sudo insmod cpuaccess.ko`",
            "驗證：`ls /dev/cpuaccess`",
            "開機自動載入：`make bootupdate`",
            "卸載：`sudo rmmod cpuaccess`",
        ],
        "flags": {
            "EXCLUSIVE_ACCESS": "`make CUSTOM_FLAGS=-DEXCLUSIVE_ACCESS` — 限制單一 process 存取",
            "CKC_01": "`make CUSTOM_FLAGS=-DCKC_01` — kernel < 6.4.0 相容",
        },
    },
    "windows": {"name": "SSA Driver", "steps": ["以管理員執行 `setup/SSADriverInstaller.exe`"]},
}


# ══════════════════════════════════════════════════════════════
#  INTENT DETECTION ENGINE
# ══════════════════════════════════════════════════════════════

class Intent:
    GREETING = "greeting"
    OVERVIEW = "overview"
    INSTALL = "install"
    TDP = "tdp"
    CORE_STRESS = "core_stress"
    PMAX = "pmax"
    DDR_STRESS = "ddr_stress"
    UPI_STRESS = "upi_stress"
    MEM_SCREEN = "mem_screen"
    TURBO = "turbo"
    SSMON = "ssmon"
    SYSINFO = "sysinfo"
    PARAM = "param"
    TIME = "time"
    LOG = "log"
    COMPARE = "compare"
    PLATFORM = "platform"
    SPECIFIC_FLOW = "specific_flow"
    HOW_TO = "how_to"
    TROUBLESHOOT = "troubleshoot"
    SCENARIO = "scenario"
    UNKNOWN = "unknown"


# Pattern → (intent, priority)
INTENT_RULES = [
    # greetings
    (r"^(hi|hello|hey|你好|哈囉|嗨|早安|午安|晚安|安安)\s*[!！.。]?\s*$", Intent.GREETING, 10),
    (r"^(謝|thanks|thank|感謝|thx)", Intent.GREETING, 10),
    # overview
    (r"(什麼是|what.?is|介紹|overview|概述|ssmd.?是|總覽|簡介)", Intent.OVERVIEW, 8),
    # install
    (r"(install|安裝|driver|驅動|insmod|載入|load.?driver|kernel.?module|cpuaccess|bootupdate|rmmod)", Intent.INSTALL, 9),
    # specific flows (check before generic intents)
    (r"flowstress|flowmem|flowturbo", Intent.SPECIFIC_FLOW, 12),
    # scenario (user describes a real-world need)
    (r"(驗收|批次|伺服器|server.?farm|新機|出廠|量產|production|burn.?in|老化|qualify|qualification)", Intent.SCENARIO, 11),
    # compare
    (r"(差異|差別|不同|比較|compare|differ|vs\.?|versus|哪個好|該選|怎麼選|建議用)", Intent.COMPARE, 11),
    # tdp
    (r"(tdp|thermal.?design|near.?tdp|oc_enable|overclock|超頻|近tdp)", Intent.TDP, 9),
    # pmax  (must be before "power" fallback)
    (r"(pmax|p.?max|最大功耗|sleep.*idle.*stress|power.?cycle|功耗循環)", Intent.PMAX, 9),
    # core stress
    (r"(core.?stress|avx.?256|avx256|核心壓力|cpu.?stress|core.?avx)", Intent.CORE_STRESS, 9),
    # ddr
    (r"(ddr|dimm.?stress|dimm.?壓力|記憶體壓力|memory.?stress|mem.?stress|dram|avx.?128|avx.?512)", Intent.DDR_STRESS, 9),
    # upi
    (r"(upi|interconnect|互連|link.?stress|socket.?間|qpi)", Intent.UPI_STRESS, 9),
    # memory screen
    (r"(memory.?screen|記憶體篩檢|mem.?screen|march|stuck.?at|診斷|screening|篩檢|故障偵測)", Intent.MEM_SCREEN, 9),
    # turbo
    (r"(turbo.?check|turbo.?freq|頻率驗證|turbo.?驗證|max.?turbo|turbo)", Intent.TURBO, 8),
    # ssmon
    (r"(ssmon|monitor|監測|遙測|觀測|即時|real.?time|telemetry.?monitor)", Intent.SSMON, 8),
    # sysinfo
    (r"(sysinfo|系統資訊|processor.?info|cpu.?info|dimm.?info|系統配置|硬體)", Intent.SYSINFO, 8),
    # param / user variable
    (r"(user.?var|參數|variable|\-u |override|覆寫|自訂|custom|設定值|預設|default|怎麼改|怎麼設)", Intent.PARAM, 7),
    # time / duration
    (r"(時間|time|duration|多久|限時|\-t |timeout|持續|幾分鐘|幾小時|小時|分鐘|秒)", Intent.TIME, 8),
    # log
    (r"(log|日誌|logging|debug|除錯|紀錄|記錄檔)", Intent.LOG, 7),
    # platform/os
    (r"(support|支援|os|作業系統|linux|windows|ubuntu|centos|platform|平台|cwf|gnr|srf|dmr)", Intent.PLATFORM, 6),
    # troubleshoot
    (r"(error|錯誤|fail|失敗|問題|不行|不能|沒有|找不到|crash|hang|無法)", Intent.TROUBLESHOOT, 7),
    # how-to (catch-all for command questions)
    (r"(怎麼|如何|how.?to|指令|command|命令|執行|跑|run|用法|怎樣)", Intent.HOW_TO, 5),
    # power / temp generic → ssmon
    (r"(溫度|功耗|power|temperature|freq|頻率|電壓|voltage|c.?state|殘留)", Intent.SSMON, 5),
]


def detect_intents(question: str):
    """Return a list of (intent, score) sorted by score desc."""
    q = question.lower().strip()
    results = {}
    for pattern, intent, priority in INTENT_RULES:
        matches = re.findall(pattern, q, re.IGNORECASE)
        if matches:
            score = priority + len(matches)
            if intent not in results or results[intent] < score:
                results[intent] = score
    return sorted(results.items(), key=lambda x: -x[1])


def extract_entities(question: str):
    """Extract mentioned flow names, platforms, tools, numbers, etc."""
    q = question.lower()
    entities = {"flows": [], "platforms": [], "tools": [], "numbers": [], "avx_width": None}

    for fname in FLOWS:
        if fname.lower().replace(".json", "").replace("flow", "") in q.replace(" ", ""):
            entities["flows"].append(fname)

    for code in PLATFORMS:
        if code.lower() in q:
            entities["platforms"].append(code)

    for tool in ["ssmd", "ssmon", "sysinfo"]:
        if tool in q:
            entities["tools"].append(tool)

    nums = re.findall(r'\b(\d+)\b', q)
    entities["numbers"] = [int(n) for n in nums]

    if "avx512" in q or "avx 512" in q:
        entities["avx_width"] = 512
    elif "avx256" in q or "avx 256" in q:
        entities["avx_width"] = 256
    elif "avx128" in q or "avx 128" in q:
        entities["avx_width"] = 128

    return entities


# ══════════════════════════════════════════════════════════════
#  CONVERSATIONAL RESPONSE COMPOSER
# ══════════════════════════════════════════════════════════════

def _openers():
    return random.choice([
        "好的，讓我來說明一下。\n\n",
        "沒問題，以下是相關資訊：\n\n",
        "這是個好問題！\n\n",
        "當然可以，讓我幫你整理一下。\n\n",
        "了解，以下是我的建議：\n\n",
        "讓我為你解答。\n\n",
        "好的，這邊跟你說明。\n\n",
        "收到！讓我來幫你分析。\n\n",
    ])

def _follow_up(topics):
    if not topics:
        return ""
    suggestions = random.sample(topics, min(3, len(topics)))
    lines = "\n\n---\n💡 **你可能還想了解：**\n"
    for s in suggestions:
        lines += f"- {s}\n"
    return lines


def _var_table(flow_info, show_all=False):
    """Build a markdown table of user variables."""
    if "vars" not in flow_info or not flow_info["vars"]:
        return ""
    items = list(flow_info["vars"].items())
    if not show_all and len(items) > 6:
        items = items[:6]
        truncated = True
    else:
        truncated = False
    t = "\n| 參數 | 預設值 | 說明 |\n|------|--------|------|\n"
    for k, v in items:
        t += f"| `{k}` | `{v['d']}` | {v['t']} |\n"
    if truncated:
        t += f"\n_（還有其他參數，可以問我「{list(flow_info['vars'].keys())[-1]} 的完整參數」了解更多）_\n"
    return t


def _compose_flow_answer(flow_key, flow_info, context_hint=""):
    """Compose a natural answer about a specific flow."""
    parts = []
    parts.append(f"**{flow_info['desc']}**\n\n")
    parts.append(f"這個測試的主要目的是**{flow_info['purpose']}**，使用的 plugin 是 `{flow_info['plugin']}`。\n")
    parts.append(f"\n執行指令：\n```bash\n{flow_info['cmd']}\n```\n")

    if flow_key == "flowStressTdpCWF.json":
        parts.append("\n如果你想做 **Near-TDP（超頻模式）**，加上 `-u oc_enable=1`：\n")
        parts.append(f"```bash\n{flow_info['cmd']} -u oc_enable=1\n```\n")
        parts.append("⚠️ 不過要提醒你，超頻可能會損壞系統，請確保散熱充足。\n")

    if flow_info.get("vars"):
        parts.append("\n以下是重要的可調參數：\n")
        parts.append(_var_table(flow_info))

    if flow_info.get("tips"):
        parts.append("\n💡 **小提示：**\n")
        for tip in flow_info["tips"]:
            parts.append(f"- {tip}\n")

    parts.append(f"\n如果你想設定測試時間，加上 `-t 秒數`，例如跑 10 分鐘：\n```bash\n{flow_info['cmd']} -t 600\n```")
    return "".join(parts)


def compose_greeting(question):
    q = question.lower()
    if any(w in q for w in ["謝", "thank", "thx", "感謝"]):
        return random.choice([
            "不客氣！有任何其他 SSMD 的問題隨時問我 😊",
            "很高興能幫上忙！如果還有疑問，儘管問吧 👍",
            "不會不會，這是我的專長！還有什麼需要協助的嗎？",
        ])
    return random.choice([
        "嗨！👋 我是 SSMD 智能助手。\n\n我對 SSMD 套件的每個工具、每個參數都瞭若指掌，包括 ssmd、ssmon、sysinfo 等工具的使用方式。\n\n你可以直接告訴我你想做什麼（例如「我想測 TDP 壓力」、「怎麼看記憶體溫度」），我會給你最適合的指令和建議！",
        "你好！😄 我是你的 SSMD 小幫手。\n\n不管是壓力測試、記憶體篩檢、系統監測，還是驅動安裝，都可以問我。直接描述你的需求就好，不需要記指令！",
    ])


def compose_overview():
    return f"""SSMD 全名是 **System Stress & Memory Diagnostics**，是 Intel 為 Xeon 數據中心平台開發的一套壓力測試與記憶體診斷框架。

簡單來說，它能做三大類事情：

1. ⚡ **CPU/DRAM 功耗與溫度壓力測試** — 包括 TDP、Core AVX、PMax 等
2. 🔗 **高速連結壓力測試** — UPI、DDR 頻寬壓力
3. 🔍 **記憶體診斷** — March C-、Stuck-At 等故障偵測演算法

目前的版本是 **{SSMD_VERSION}**，支援的平台有 {', '.join(f'**{k}** ({v})' for k,v in PLATFORMS.items())}。

套件裡有三個主要工具：
- **ssmd** — 主程式，用來跑各種測試
- **ssmon** — 即時監測工具，看頻率、溫度、功耗等
- **sysinfo** — 查詢系統硬體配置

基本的使用流程是：
```bash
# 1. 解壓套件
tar xvzf ssmd_{SSMD_VERSION}_lin.tar.gz

# 2. 安裝驅動（Linux）
cd Drivers && make && sudo insmod cpuaccess.ko

# 3. 執行測試（以 TDP 壓力為例）
sudo ./ssmd -f Flows/TDP/flowStressTdpCWF.json

# 4. 監測系統狀態
sudo ./ssmon
```

你想深入了解哪個部分呢？我可以詳細介紹任何一個測試或工具。"""


def compose_install(entities):
    parts = ["""好的，來說說驅動安裝的流程。\n\n"""]
    parts.append("### Linux 系統\n\n")
    parts.append("SSMD 在 Linux 上需要一個叫 **cpuaccess** 的 kernel module，步驟如下：\n\n")
    parts.append("**第一步：安裝 kernel headers**\n")
    parts.append("```bash\n# Ubuntu\nsudo apt-get update\nsudo apt-get install linux-headers-$(uname -r)\nsudo apt install gcc-12\n\n# CentOS\nsudo yum update\nsudo yum install \"kernel-devel-$(uname -r)\"\n```\n\n")
    parts.append("**第二步：編譯並載入驅動**\n")
    parts.append("```bash\ncd Drivers\nmake\nsudo insmod cpuaccess.ko\n```\n\n")
    parts.append("**第三步：確認成功**\n")
    parts.append("```bash\nls /dev/cpuaccess\n```\n如果看到這個裝置檔就代表成功了。\n\n")
    parts.append("如果想讓它**開機自動載入**：\n```bash\nmake bootupdate\n```\n\n")
    parts.append("### Windows 系統\n\n")
    parts.append("Windows 比較簡單，以管理員身分執行 `setup/SSADriverInstaller.exe` 按照精靈操作就好。\n\n")
    parts.append("### 額外的編譯選項\n\n")
    parts.append("如果遇到特殊情況：\n")
    parts.append("- 要限制只能單一 process 存取：`make CUSTOM_FLAGS=-DEXCLUSIVE_ACCESS`\n")
    parts.append("- Kernel < 6.4.0 的相容性問題：`make CUSTOM_FLAGS=-DCKC_01`\n")
    return "".join(parts)


def compose_ssmon(question, entities):
    q = question.lower()
    parts = []

    # detect sub-topic
    wants_cstate = any(w in q for w in ["c-state", "cstate", "c0", "c6", "殘留", "residency", "休眠"])
    wants_temp = any(w in q for w in ["溫度", "temperature", "temp", "thermal"])
    wants_power = any(w in q for w in ["功耗", "power", "watt", "瓦"])
    wants_freq = any(w in q for w in ["頻率", "freq", "frequency", "mhz"])
    wants_mem = any(w in q for w in ["記憶體", "memory", "dimm", "bandwidth", "頻寬", "bw"])
    wants_upi = any(w in q for w in ["upi", "interconnect"])
    wants_pcie = any(w in q for w in ["pcie", "pci"])

    parts.append("**SSMON** 是 SSMD 套件裡的即時監測工具，可以持續顯示系統的各項遙測數據。\n\n")

    if wants_cstate:
        parts.append("你想看 C-State 殘留率的話，用這個設定檔最合適：\n")
        parts.append("```bash\nsudo ./ssmon -c Configs/ssmonConfigCState.json\n```\n")
        parts.append("它會顯示每個核心的 **C0**（活躍）、**C1**、**C6**（深度休眠）殘留率，以及 Package 層級的 **PC2**、**PC6**。\n\n")
        parts.append("加上 `-l 1` 可以看到 per-core 的數據。\n")
    elif wants_temp and wants_power:
        parts.append("想同時看溫度和功耗的話，推薦用 **Min/Max 統計設定**：\n")
        parts.append("```bash\nsudo ./ssmon -c Configs/ssmonConfigMinMax.json\n```\n")
        parts.append("它會顯示 PackagePower 和 PackageTemperature 的 **最小值、平均值、最大值**，方便你一眼看出趨勢。\n")
    elif wants_temp:
        parts.append("要看溫度的話，最快的方式：\n")
        parts.append("```bash\nsudo ./ssmon\n```\n")
        parts.append("預設模式就包含 `PackageTemperature`。如果想看更細的 Min/Max：\n")
        parts.append("```bash\nsudo ./ssmon -c Configs/ssmonConfigMinMax.json\n```\n")
    elif wants_power:
        parts.append("功耗監測的話：\n")
        parts.append("```bash\nsudo ./ssmon\n```\n")
        parts.append("預設就有 `PackagePowerAlt` 欄位。想看 Min/Avg/Max 統計：\n")
        parts.append("```bash\nsudo ./ssmon -c Configs/ssmonConfigMinMax.json\n```\n")
    elif wants_freq:
        parts.append("頻率監測推薦用 **CPU Basic** 設定：\n")
        parts.append("```bash\nsudo ./ssmon -c Configs/ssmonConfigCpuBasic.json\n```\n")
        parts.append("它會顯示 Core 頻率、Uncore 頻率（包含各 Compute/IO/CBB 域）非常詳細。\n")
    elif wants_mem:
        parts.append("記憶體相關的監測用這個：\n")
        parts.append("```bash\nsudo ./ssmon -c Configs/ssmonConfigMemBasic.json\n```\n")
        parts.append("可以看到每條 DIMM 的**溫度、功耗、讀寫頻寬**。\n")
    elif wants_upi:
        parts.append("UPI 頻寬監測：\n")
        parts.append("```bash\nsudo ./ssmon -c Configs/ssmonConfigUpiBasic.json\n```\n")
    elif wants_pcie:
        parts.append("PCIe 頻寬監測：\n")
        parts.append("```bash\nsudo ./ssmon -c Configs/ssmonConfigPcieBasic.json\n```\n")
    else:
        # general ssmon overview
        parts.append("基本的使用方式是這樣的：\n\n")
        parts.append("```bash\n# Socket 層級（預設，資訊最精簡）\nsudo ./ssmon\n\n# Core 層級（看每個核心）\nsudo ./ssmon -l 1\n\n# Thread 層級（最詳細）\nsudo ./ssmon -l 2\n```\n\n")
        parts.append("也可以選 **Profile** 來切換監測面向：\n")
        parts.append("```bash\nsudo ./ssmon -p 1 -l 2   # CPU Profile\nsudo ./ssmon -p 2 -l 2   # Memory Profile\nsudo ./ssmon -p 3 -l 2   # All\n```\n\n")
        parts.append("另外有一系列預設的設定檔，各有不同專注面向：\n\n")
        parts.append("| 設定檔 | 用途 |\n|--------|------|\n")
        for cfg_name, cfg in SSMON_CONFIGS.items():
            parts.append(f"| **{cfg['name']}** | {cfg['desc']} |\n")
        parts.append(f"\n使用方式：`sudo ./ssmon -c Configs/<設定檔名>`\n")

    parts.append("\n你想看哪方面的數據呢？我可以給你更精確的建議。")
    return "".join(parts)


def compose_sysinfo():
    return """**sysinfo** 可以查詢系統的硬體配置，這在跑測試之前很有用，先確認系統的基本狀態。

最常用的幾個指令：

```bash
# 列出所有系統支援的資訊項目（看看能查什麼）
sudo ./sysinfo -e

# 查看處理器資訊（CPUID、核心數、頻率、TDP 等）
sudo ./sysinfo -c -p

# 查看記憶體 DIMM 資訊
sudo ./sysinfo -d -o
```

可以查到的資訊包括：ProcessorCPUID、核心數、基礎/最大頻率、TDP、PL1/PL2 功耗限制、HWP 狀態、是否為 Sample 部件等等。

💡 建議在跑任何壓力測試之前，先用 `sudo ./sysinfo -c -p` 確認系統配置是否正確，特別是核心數和 TDP 是否符合預期。"""


def compose_param(question, entities):
    q = question.lower()
    # If asking about a specific flow's params
    for fname, finfo in FLOWS.items():
        normalized_fname = fname.lower().replace(".json","").replace("flow","").replace("stress","").replace("screen","")
        normalized_q = q.replace(" ","").replace("-","").replace("_","")
        if normalized_fname.replace("_","") in normalized_q:
            return f"好的，來看看 **{fname}** 的完整參數列表：\n\n{_var_table(finfo, show_all=True)}\n\n使用 `-u` 來覆寫，例如：\n```bash\n{finfo['cmd']} -u corestress_intensity=80\n```\n\n多個參數可以連續加：\n```bash\n{finfo['cmd']} -u corestress_intensity=80 -u corestress_socketmask=0x1\n```"

    return """在 SSMD 中，每個 flow 設定檔都有一組 **user variables**（使用者變數），你可以在命令列用 `-u` 覆寫它們。

### 怎麼用

```bash
sudo ./ssmd -f <flow_file> -u <變數名>=<值>
```

多個參數就多加幾個 `-u`：
```bash
sudo ./ssmd -f Flows/TDP/flowStressTdpCWF.json -u oc_enable=1 -u near_tdp_target=95.0 -u corestress_intensity=80
```

### 幾個常見的通用參數

| 參數 | 說明 |
|------|------|
| `telemetry` | 是否收集遙測 (true/false) |
| `telemetry_period` | 遙測頻率 (ms) |
| `telemetry_filename` | 遙測輸出到檔案 |
| `corestress_intensity` | 壓力強度 (0-100%) |
| `corestress_socketmask` | 選擇 socket (bitvector) |
| `corestress_coremask` | 選擇 core (bitvector) |

### ⚠️ 小提醒
- CLI 上 `%` 要寫成 `pct`，例如：`-u lpu_select_expr=50pct/numa`
- bitvector 用十六進制：`-u corestress_socketmask=0x3`

如果你告訴我具體要調哪個 flow 的參數，我可以列出它完整的可調項目！"""


def compose_time():
    return """用 `-t` 參數就可以設定測試的持續時間（單位是秒）：

```bash
# 跑 5 分鐘
sudo ./ssmd -f Flows/TDP/flowStressTdpCWF.json -t 300

# 跑 1 小時
sudo ./ssmd -f Flows/CoreStress/flowStressCoreAVX256CWF.json -t 3600

# 跑 24 小時
sudo ./ssmd -f Flows/PMax/flowStressPMaxCWF.json -t 86400
```

如果不加 `-t`，測試會一直跑，直到你按 **Ctrl+C** 手動停止。

另外，**Turbo Check** 的每次迭代時間是用 `workload_duration` 參數控制的（預設 5000ms）：
```bash
sudo ./ssmd -f Flows/TurboCheck/flowTurboCheckCWF.json -u workload_duration=10000
```

你想跑多久的測試呢？我可以幫你組好完整指令。"""


def compose_log():
    return """SSMD 有兩套日誌設定：

### SSMD 日誌（`Configs/ssmd.logcfg.json`）
控制主程式的日誌輸出。預設是 `error` 級別、輸出到 `stdout`。

### SSMON 日誌（`Configs/ssmon.logcfg.json`）
控制監測工具的日誌。預設輸出到 `logs/ssmon.log` 檔案。

### 怎麼調整

日誌級別從少到多：`error` → `warning` → `info` → `debug` → `trace`

如果要 debug 的話，編輯設定檔把 `"min_log_level"` 改成 `"debug"` 就能看到更多資訊。`sink` 可以設成 `stdout`（螢幕）或 `file`（檔案）。

### 遙測數據記錄

如果你想把**測試過程的遙測數據**存檔（不是日誌，是 telemetry data），用 `telemetry_filename` 參數：
```bash
sudo ./ssmd -f Flows/TDP/flowStressTdpCWF.json -u telemetry_filename=my_telemetry.json
```
這會產生一個 JSON 格式的檔案，包含測試期間所有的功耗、溫度、頻率等數據。"""


def compose_platform():
    lines = ["目前 SSMD 支援的環境如下：\n\n"]
    lines.append("### 支援的 CPU 平台\n\n")
    for code, name in PLATFORMS.items():
        lines.append(f"- **{code}** — {name}\n")
    lines.append("\n### 支援的作業系統\n\n")
    for os_info in SUPPORTED_OS:
        note = f"（{os_info['note']}）" if os_info.get("note") else "✅"
        lines.append(f"- **{os_info['os']}** — kernel {os_info.get('kernel', '-')} {note}\n")
    lines.append("\n⚠️ 注意事項：\n")
    lines.append("- Flow 檔名中帶有平台代號（如 CWF），跑的時候要確認是否有對應你平台的版本\n")
    lines.append("- Linux kernel 版本需要 **5.19 以上**\n")
    lines.append("- Windows Server 2022 **不支援 CWF 平台**\n")
    return "".join(lines)


def compose_compare(question, entities):
    q = question.lower()

    if any(w in q for w in ["tdp", "pmax", "core"]):
        return """好問題！這三種壓力測試有不同的定位，我來比較一下：

### TDP vs Core Stress vs PMax

| 特性 | TDP Stress | Core AVX256 | PMax |
|------|-----------|-------------|------|
| **目標** | 逼近 TDP 功耗 | 持續全核壓力 | 最大功耗衝擊 |
| **預設強度** | 92% | 100% | 100% (含 Uncore) |
| **壓力類型** | Core only | Core only | Core + Uncore + Link |
| **模式** | 持續 | 持續 | Sleep→Idle→Stress 循環 |
| **超頻** | ✅ 支援 (oc_enable) | ❌ | ❌ |
| **適合場景** | 功耗驗證 | 散熱驗證 | 電源供應極限 |

**簡單來說：**
- 想驗證系統在**額定 TDP 下**穩不穩 → 用 **TDP Stress**
- 想測**持續高負載**下的溫度和穩定性 → 用 **Core AVX256**
- 想測**電源供應和散熱的極限** → 用 **PMax**（它會造成功耗瞬間劇烈變化）"""

    if any(w in q for w in ["ddr", "avx128", "avx256", "avx512", "記憶體壓力"]):
        return """DDR 壓力測試有三個版本，差異在 AVX 指令寬度：

| 版本 | 指令寬度 | 頻寬壓力 | 相容性 |
|------|---------|---------|--------|
| **AVX128** | 128-bit | 較低 | 最好 |
| **AVX256** | 256-bit | 中高 | 好 |
| **AVX512** | 512-bit | 最高 | 部分平台 |

**建議：**
- 一般測試用 **AVX256** 就好，頻寬夠高又相容性好
- 想壓到最大 DIMM 功耗/溫度，才需要 **AVX512**
- **AVX128** 適合只需要基本 DDR 壓力的場景"""

    if any(w in q for w in ["screen", "篩檢", "march", "stuck", "記憶體診斷"]):
        return """記憶體篩檢有四種模式，適合不同需求：

| 模式 | 速度 | 覆蓋率 | 適合場景 |
|------|------|--------|---------|
| **Read Screen** | ⚡ 最快 | 低 | 快速讀取路徑檢查 |
| **Write Screen** | ⚡ 快 | 低 | 快速寫入路徑檢查 |
| **Stuck-At** | 🔄 中等 | 中 | bit 卡住故障初篩 |
| **March C-** | 🐢 最慢 | ✅ 最高 | 完整 DRAM 診斷 |

**建議流程：**
1. 先跑 **Stuck-At** 快速初篩
2. 有疑慮再跑 **March C-** 做完整診斷
3. Read/Write Screen 適合做 DDR 頻寬壓力測試"""

    return """你想比較哪些功能呢？我可以幫你分析：

- **TDP vs Core Stress vs PMax** — 三種壓力測試的差異
- **DDR AVX128 vs AVX256 vs AVX512** — 不同頻寬的記憶體壓力
- **March vs Stuck-At vs Read/Write Screen** — 記憶體篩檢的選擇

直接告訴我你在考慮的選項就好！"""


def compose_scenario(question):
    """For real-world scenario descriptions, compose a recommended testing plan."""
    q = question.lower()
    parts = ["了解你的需求！讓我幫你規劃一套測試流程。\n\n"]

    if any(w in q for w in ["驗收", "新機", "出廠", "server", "伺服器", "qualify"]):
        parts.append("### 📋 新伺服器驗收測試建議\n\n")
        parts.append("以下是我建議的完整驗收流程，按順序執行：\n\n")
        parts.append("**Step 1 — 系統資訊確認**\n")
        parts.append("```bash\nsudo ./sysinfo -c -p    # 確認 CPU 型號、核心數、TDP\nsudo ./sysinfo -d -o    # 確認 DIMM 配置\n```\n\n")
        parts.append("**Step 2 — 記憶體完整性篩檢**（建議先做，抓硬體問題）\n")
        parts.append("```bash\nsudo ./ssmd -f Flows/MemoryScreen/flowMemScreenMarch.json\n```\n\n")
        parts.append("**Step 3 — CPU 壓力測試**（30 分鐘起跳）\n")
        parts.append("```bash\nsudo ./ssmd -f Flows/TDP/flowStressTdpCWF.json -t 1800\n```\n\n")
        parts.append("**Step 4 — DDR 壓力測試**\n")
        parts.append("```bash\nsudo ./ssmd -f Flows/DdrStress/flowStressDdrWriteAVX256.json -t 1800\n```\n\n")
        parts.append("**Step 5 — 全程監測**（在另一個終端跑）\n")
        parts.append("```bash\nsudo ./ssmon -c Configs/ssmonConfigMinMax.json\n```\n\n")
        parts.append("⏱️ 如果時間充裕，建議 Step 3-4 各跑 **4-8 小時**以上，更能發現潛在問題。\n")

    elif any(w in q for w in ["burn", "老化", "量產", "production"]):
        parts.append("### 🔥 Burn-In 老化測試建議\n\n")
        parts.append("Burn-in 的目的是長時間高負載運行，篩出 infant mortality。\n\n")
        parts.append("**建議用 PMax 做 Burn-In**（功耗變化最大，最能暴露問題）：\n")
        parts.append("```bash\n# 跑 24 小時\nsudo ./ssmd -f Flows/PMax/flowStressPMaxCWF.json -t 86400\n```\n\n")
        parts.append("**搭配遙測記錄**，方便事後分析：\n")
        parts.append("```bash\nsudo ./ssmd -f Flows/PMax/flowStressPMaxCWF.json -t 86400 -u telemetry=true -u telemetry_filename=burnin_log.json\n```\n\n")
        parts.append("**另開一個終端做即時監測**：\n")
        parts.append("```bash\nsudo ./ssmon -c Configs/ssmonConfigMinMax.json\n```\n")

    else:
        parts.append("可以告訴我更多細節嗎？例如：\n")
        parts.append("- 你是在做**新機驗收**還是**量產 Burn-in**？\n")
        parts.append("- 主要關心的是 **CPU 穩定性**、**記憶體完整性**、還是**整體功耗**？\n")
        parts.append("- 有多少時間可以做測試？\n\n")
        parts.append("這樣我可以給你更精準的建議！")

    return "".join(parts)


def compose_how_to(question, entities):
    """For generic how-to questions, try to match the most relevant thing."""
    q = question.lower()

    # Build a scored list of related commands
    matches = []
    keywords_map = [
        (["tdp", "功耗壓力", "power stress"], "tdp_stress"),
        (["near", "超頻", "overclock"], "near_tdp"),
        (["avx", "核心", "core"], "avx256_stress"),
        (["turbo", "頻率"], "max_turbo"),
        (["pmax", "最大"], "pmax_stress"),
        (["ddr", "記憶體壓力", "dimm"], "ddr256"),
        (["upi", "互連"], "upi"),
        (["screen", "篩檢", "march", "診斷"], "mem_march"),
        (["monitor", "監測", "ssmon"], "mon_socket"),
        (["sysinfo", "系統", "硬體"], "si_all"),
        (["driver", "驅動", "安裝"], "driver"),
    ]

    for keywords, cmd_key in keywords_map:
        if any(kw in q for kw in keywords):
            if cmd_key in QUICK_COMMANDS:
                matches.append(QUICK_COMMANDS[cmd_key])

    if matches:
        parts = ["根據你的描述，以下是我建議的指令：\n\n"]
        for m in matches[:3]:
            parts.append(f"**{m['desc']}**\n```bash\n{m['cmd']}\n```\n")
            if "note" in m:
                parts.append(f"⚠️ {m['note']}\n")
            parts.append("\n")
        parts.append("需要調整任何參數的話，用 `-u` 加上去就好。想知道有哪些可調參數，可以接著問我！")
        return "".join(parts)

    return None  # fall through to default


def compose_troubleshoot(question):
    q = question.lower()
    parts = ["看起來你遇到了一些問題，讓我幫你排查一下。\n\n"]

    if any(w in q for w in ["cpuaccess", "driver", "驅動", "dev", "module", "insmod"]):
        parts.append("### 驅動相關問題\n\n")
        parts.append("1. **確認 kernel headers 已安裝**：\n```bash\nls /lib/modules/$(uname -r)/build\n```\n\n")
        parts.append("2. **重新編譯驅動**：\n```bash\ncd Drivers && make clean && make\n```\n\n")
        parts.append("3. **查看載入錯誤**：\n```bash\nsudo insmod cpuaccess.ko\ndmesg | tail -20\n```\n\n")
        parts.append("4. **Kernel 6.4+ 的問題**：試試 `make CUSTOM_FLAGS=-DCKC_01`\n")
    elif any(w in q for w in ["permission", "denied", "權限", "sudo"]):
        parts.append("SSMD 需要 **root 權限**才能存取硬體，所有指令都要加 `sudo`：\n")
        parts.append("```bash\nsudo ./ssmd -f Flows/TDP/flowStressTdpCWF.json\nsudo ./ssmon\nsudo ./sysinfo -e\n```\n")
    else:
        parts.append("一些常見的排查步驟：\n\n")
        parts.append("1. **驅動是否載入** — `ls /dev/cpuaccess`\n")
        parts.append("2. **是否有 root 權限** — 指令前加 `sudo`\n")
        parts.append("3. **kernel 版本** — 需要 5.19+，用 `uname -r` 確認\n")
        parts.append("4. **查看日誌** — 修改 `Configs/ssmd.logcfg.json` 把 `min_log_level` 改成 `debug`\n")
        parts.append("5. **Flow 檔是否存在** — 確認 Flows 目錄下有你要的 json 檔\n\n")
        parts.append("可以描述具體的錯誤訊息嗎？我能給你更精確的建議。")

    return "".join(parts)


# ══════════════════════════════════════════════════════════════
#  MAIN KNOWLEDGE CLASS
# ══════════════════════════════════════════════════════════════

class SSMDKnowledge:
    """Conversational SSMD knowledge engine with memory."""

    def __init__(self):
        self.conversation_history = []  # list of {"role": ..., "text": ...}
        self.last_intent = None
        self.last_flow = None

    def answer(self, question: str) -> str:
        """Main entry: detect intent, compose natural answer."""
        self.conversation_history.append({"role": "user", "text": question})

        intents = detect_intents(question)
        entities = extract_entities(question)
        primary_intent = intents[0][0] if intents else Intent.UNKNOWN

        # Handle context-dependent follow-ups
        reply = self._handle_follow_up(question, primary_intent, entities)
        if not reply:
            reply = self._dispatch(primary_intent, question, entities, intents)

        # Add follow-up suggestions based on what wasn't covered
        follow_ups = self._suggest_follow_ups(primary_intent)
        if follow_ups:
            reply += _follow_up(follow_ups)

        self.conversation_history.append({"role": "bot", "text": reply})
        self.last_intent = primary_intent
        return reply

    def _handle_follow_up(self, question, intent, entities):
        """Check if the question is a follow-up to the previous conversation."""
        if len(self.conversation_history) < 2:
            return None

        q = question.lower().strip()

        # Short question that refers to "it" / "that" / "這個" / "那個"
        if len(q) < 30 and any(w in q for w in ["它", "這個", "那個", "上面", "剛才"]):
            if self.last_flow and (intent == Intent.PARAM or "參數" in q or "怎麼" in q):
                finfo = FLOWS.get(self.last_flow)
                if finfo:
                    return f"你是說 **{self.last_flow}** 嗎？以下是它的完整參數：\n\n{_var_table(finfo, show_all=True)}\n\n用 `-u` 覆寫就好，例如：\n```bash\n{finfo['cmd']} -u corestress_intensity=80\n```"

        return None

    def _dispatch(self, intent, question, entities, all_intents):
        """Route to the appropriate composer."""
        opener = _openers()

        if intent == Intent.GREETING:
            return compose_greeting(question)

        if intent == Intent.OVERVIEW:
            return compose_overview()

        if intent == Intent.INSTALL:
            return opener + compose_install(entities)

        if intent == Intent.SCENARIO:
            return compose_scenario(question)

        if intent == Intent.SPECIFIC_FLOW:
            for fname, finfo in FLOWS.items():
                if fname.lower().replace(".json","").replace("flow","") in question.lower().replace(" ",""):
                    self.last_flow = fname
                    return opener + _compose_flow_answer(fname, finfo)
            return opener + (compose_how_to(question, entities) or self._fallback(question))

        if intent == Intent.COMPARE:
            return opener + compose_compare(question, entities)

        if intent == Intent.TDP:
            self.last_flow = "flowStressTdpCWF.json"
            return opener + _compose_flow_answer("flowStressTdpCWF.json", FLOWS["flowStressTdpCWF.json"])

        if intent == Intent.CORE_STRESS:
            self.last_flow = "flowStressCoreAVX256CWF.json"
            return opener + _compose_flow_answer("flowStressCoreAVX256CWF.json", FLOWS["flowStressCoreAVX256CWF.json"])

        if intent == Intent.PMAX:
            self.last_flow = "flowStressPMaxCWF.json"
            return opener + _compose_flow_answer("flowStressPMaxCWF.json", FLOWS["flowStressPMaxCWF.json"])

        if intent == Intent.DDR_STRESS:
            avx = entities.get("avx_width")
            if avx == 128:
                key = "flowStressDdrWriteAVX128.json"
            elif avx == 512:
                key = "flowStressDdrWriteAVX512.json"
            else:
                key = "flowStressDdrWriteAVX256.json"
            self.last_flow = key
            reply = _compose_flow_answer(key, FLOWS[key])
            if not avx:
                reply += "\n\n順帶一提，DDR 壓力有 AVX128/256/512 三個版本。**AVX256 是最常用的**，如果需要其他寬度可以跟我說。"
            return opener + reply

        if intent == Intent.UPI_STRESS:
            self.last_flow = "flowStressUpiLinks.json"
            return opener + _compose_flow_answer("flowStressUpiLinks.json", FLOWS["flowStressUpiLinks.json"])

        if intent == Intent.MEM_SCREEN:
            q = question.lower()
            if "march" in q:
                key = "flowMemScreenMarch.json"
            elif "stuck" in q:
                key = "flowMemScreenStuckAt.json"
            elif "write" in q or "寫" in q:
                key = "flowMemScreenWrite.json"
            elif "read" in q or "讀" in q:
                key = "flowMemScreenRead.json"
            else:
                return opener + compose_compare(question + " screen 篩檢", entities) + "\n\n如果不確定要用哪個，**March C-** 是覆蓋率最高的選擇：\n```bash\nsudo ./ssmd -f Flows/MemoryScreen/flowMemScreenMarch.json\n```"
            self.last_flow = key
            return opener + _compose_flow_answer(key, FLOWS[key])

        if intent == Intent.TURBO:
            self.last_flow = "flowTurboCheckCWF.json"
            return opener + _compose_flow_answer("flowTurboCheckCWF.json", FLOWS["flowTurboCheckCWF.json"])

        if intent == Intent.SSMON:
            return opener + compose_ssmon(question, entities)

        if intent == Intent.SYSINFO:
            return opener + compose_sysinfo()

        if intent == Intent.PARAM:
            return opener + compose_param(question, entities)

        if intent == Intent.TIME:
            return opener + compose_time()

        if intent == Intent.LOG:
            return opener + compose_log()

        if intent == Intent.PLATFORM:
            return opener + compose_platform()

        if intent == Intent.TROUBLESHOOT:
            return opener + compose_troubleshoot(question)

        if intent == Intent.HOW_TO:
            result = compose_how_to(question, entities)
            if result:
                return opener + result

        # Fallback
        return self._fallback(question)

    def _fallback(self, question):
        """Friendly fallback when we can't match intent."""
        return f"""嗯，我不太確定你具體想問什麼，不過沒關係！😊

你可以試著用更具體的方式描述你的需求，例如：

- 💬 「我想對 CWF 平台做 TDP 壓力測試」
- 💬 「怎麼看即時的 CPU 溫度和功耗」
- 💬 「記憶體篩檢要用哪個 flow」
- 💬 「TDP stress 和 PMax 有什麼差別」
- 💬 「flowStressTdpCWF.json 有哪些參數可以調」
- 💬 「我要驗收一批新伺服器，建議跑哪些測試」

或者直接告訴我你的場景，我來推薦最適合的測試組合！

目前 SSMD 支援的測試類型有：
- ⚡ TDP / Core AVX / PMax **壓力測試**
- 🧊 DDR **記憶體壓力**
- 🔗 UPI **互連壓力**
- 🔍 March / Stuck-At **記憶體篩檢**
- 🚀 Turbo **頻率驗證**
- 📊 SSMON **即時監測**"""

    def _suggest_follow_ups(self, current_intent):
        """Suggest related topics the user might want to explore next."""
        suggestions_map = {
            Intent.TDP: ["PMax 和 TDP 有什麼差異？", "怎麼監測壓力測試期間的溫度？", "如何設定測試時間？"],
            Intent.CORE_STRESS: ["TDP stress 和 Core stress 差在哪？", "怎麼只測特定核心？", "怎麼記錄遙測數據到檔案？"],
            Intent.PMAX: ["PMax 的 Sleep/Idle/Stress 循環可以調時間嗎？", "怎麼同時開啟 Link stress？", "怎麼監測功耗變化？"],
            Intent.DDR_STRESS: ["AVX128/256/512 差在哪？", "怎麼看記憶體頻寬？", "記憶體篩檢怎麼做？"],
            Intent.UPI_STRESS: ["怎麼看 UPI 頻寬？", "UPI 壓力需要什麼系統配置？"],
            Intent.MEM_SCREEN: ["March 和 Stuck-At 差在哪？", "怎麼篩檢全部記憶體？", "怎麼追蹤已篩檢的 page？"],
            Intent.TURBO: ["Turbo Check 的三種模式分別是什麼？", "怎麼把結果輸出到檔案？"],
            Intent.SSMON: ["有哪些 SSMON 設定檔可以用？", "怎麼看 C-State 殘留率？", "怎麼看 Min/Max 統計？"],
            Intent.INSTALL: ["安裝完驅動後怎麼跑第一個測試？", "Windows 上怎麼安裝？"],
            Intent.OVERVIEW: ["如何安裝驅動？", "最常用的壓力測試是哪個？", "怎麼即時監測系統？"],
            Intent.SCENARIO: ["怎麼看測試的即時狀態？", "如何記錄遙測數據？", "記憶體篩檢怎麼做？"],
        }
        return suggestions_map.get(current_intent, [])

    # ── Dashboard API ────────────────────────────────────────
    def get_dashboard_data(self):
        flow_cats = {}
        for fname, finfo in FLOWS.items():
            cat = finfo["category"]
            if cat not in flow_cats:
                flow_cats[cat] = {"name": finfo["cat_name"], "description": "", "flow_count": 0, "flow_names": []}
            flow_cats[cat]["flow_count"] += 1
            flow_cats[cat]["flow_names"].append(fname)

        return {
            "version": SSMD_VERSION, "package": SSMD_PACKAGE,
            "platforms": PLATFORMS, "supported_os": SUPPORTED_OS,
            "tools": {k: {"name": v["name"], "description": v["desc"], "usage": v["usage"]} for k,v in TOOLS.items()},
            "flow_categories": flow_cats,
            "ssmon_configs": {k: {"name": v["name"], "description": v["desc"]} for k,v in SSMON_CONFIGS.items()},
            "total_flows": len(FLOWS), "total_libraries": 47,
            "driver_info": DRIVER_INFO, "telemetry_types": TELEMETRY_TYPES,
            "sysinfo_types": SYSINFO_TYPES, "quick_commands": QUICK_COMMANDS,
        }

    def get_flows_detail(self):
        return {"flows": {k: v for k,v in FLOWS.items()}}

    def generate_command(self, requirement):
        return self.answer(requirement)
