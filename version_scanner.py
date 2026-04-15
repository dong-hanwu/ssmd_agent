"""
SSMD Version Scanner — Automatically scans all SSMD packages in the workspace
and extracts version metadata for comparison.
"""

import os
import json
import re
from pathlib import Path

# Base directory for SSMD packages
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _find_ssmd_packages():
    """Discover all ssmd_YYYY.MM.DD.XXXX_lin directories."""
    packages = []
    pattern = re.compile(r"ssmd_(\d{4}\.\d{2}\.\d{2}\.\w+)_lin")

    # Search in base dir and ssmd/ subdir
    search_dirs = [BASE_DIR, os.path.join(BASE_DIR, "ssmd")]
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for entry in os.listdir(search_dir):
            m = pattern.match(entry)
            if m:
                pkg_path = os.path.join(search_dir, entry)
                # Handle nested directory (ssmd/ssmd_xxx/ssmd_xxx/)
                inner = os.path.join(pkg_path, entry)
                if os.path.isdir(inner) and os.path.exists(os.path.join(inner, "README.txt")):
                    pkg_path = inner
                if os.path.exists(os.path.join(pkg_path, "README.txt")):
                    packages.append({"version": m.group(1), "path": pkg_path})

    # Sort by version (newest first)
    packages.sort(key=lambda p: p["version"], reverse=True)
    return packages


def _scan_flows(pkg_path):
    """List all flow JSON files."""
    flows_dir = os.path.join(pkg_path, "Flows")
    flows = []
    if not os.path.isdir(flows_dir):
        return flows
    for root, dirs, files in os.walk(flows_dir):
        for f in files:
            if f.endswith(".json"):
                # Get relative path from Flows/
                rel = os.path.relpath(os.path.join(root, f), flows_dir).replace("\\", "/")
                flows.append(rel)
    flows.sort()
    return flows


def _scan_configs(pkg_path):
    """List SSMON config files."""
    configs_dir = os.path.join(pkg_path, "Configs")
    configs = []
    if not os.path.isdir(configs_dir):
        return configs
    for f in os.listdir(configs_dir):
        if f.startswith("ssmonConfig") and f.endswith(".json"):
            configs.append(f)
    configs.sort()
    return configs


def _scan_libraries(pkg_path):
    """Count and list .so library files."""
    lib_dir = os.path.join(pkg_path, "Libraries")
    libs = []
    if not os.path.isdir(lib_dir):
        return libs
    for f in os.listdir(lib_dir):
        if f.endswith(".so"):
            libs.append(f)
    libs.sort()
    return libs


def _scan_platforms(pkg_path):
    """Extract platform identification from regdefs.json."""
    regdefs = os.path.join(pkg_path, "regdefs.json")
    if not os.path.exists(regdefs):
        return []
    try:
        with open(regdefs, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        ident = data.get("identification", {})
        return sorted(ident.keys())
    except Exception:
        return []


def _scan_supported_platforms(pkg_path):
    """Extract officially supported platforms from README."""
    readme = os.path.join(pkg_path, "README.txt")
    if not os.path.exists(readme):
        return []
    try:
        with open(readme, "r", encoding="utf-8", errors="ignore") as fp:
            text = fp.read()
        # Look for "Supported Platforms" section
        m = re.search(r"Supported Platforms\s*-+\s*(.*?)(?:\n\n|\n[A-Z])", text, re.DOTALL)
        if m:
            lines = m.group(1).strip().split("\n")
            platforms = []
            for line in lines:
                line = line.strip()
                if line and re.match(r"\d+\.", line):
                    platforms.append(re.sub(r"^\d+\.\s*", "", line).strip())
            return platforms
        # If no explicit section, infer from flows
        return []
    except Exception:
        return []


def _scan_supported_os(pkg_path):
    """Extract OS support from README."""
    readme = os.path.join(pkg_path, "README.txt")
    if not os.path.exists(readme):
        return []
    try:
        with open(readme, "r", encoding="utf-8", errors="ignore") as fp:
            text = fp.read()
        os_list = []
        if "Ubuntu 23.04" in text:
            os_list.append("Ubuntu 23.04 (kernel 5.19+)")
        if "CentOS 8" in text:
            os_list.append("CentOS 8 (kernel 5.19+)")
        if "Windows Server 2022" in text:
            note = ""
            if "not supported for Clear Water Forest" in text:
                note = " (不支援 CWF)"
            os_list.append(f"Windows Server 2022{note}")
        return os_list
    except Exception:
        return []


def _scan_workload_types(pkg_path):
    """Extract unique workload tests from README."""
    readme = os.path.join(pkg_path, "README.txt")
    if not os.path.exists(readme):
        return []
    try:
        with open(readme, "r", encoding="utf-8", errors="ignore") as fp:
            text = fp.read()
        tests = []
        # Look for numbered test list
        for m in re.finditer(r"\d+\.\s+([\w\s\.]+):\s+sudo\s+\./ssmd\s+-f\s+(\S+)", text):
            tests.append({"name": m.group(1).strip(), "cmd": m.group(2).strip()})
        return tests
    except Exception:
        return []


def _has_flow_subdirectories(pkg_path):
    """Check if flows are organized into category subdirectories."""
    flows_dir = os.path.join(pkg_path, "Flows")
    if not os.path.isdir(flows_dir):
        return False
    for entry in os.listdir(flows_dir):
        if os.path.isdir(os.path.join(flows_dir, entry)):
            return True
    return False


def _get_flow_categories(pkg_path):
    """Get flow subdirectory names (if any)."""
    flows_dir = os.path.join(pkg_path, "Flows")
    cats = []
    if not os.path.isdir(flows_dir):
        return cats
    for entry in sorted(os.listdir(flows_dir)):
        if os.path.isdir(os.path.join(flows_dir, entry)):
            cats.append(entry)
    return cats


def scan_package(pkg_info):
    """Full scan of one SSMD package."""
    path = pkg_info["path"]
    version = pkg_info["version"]

    flows = _scan_flows(path)
    configs = _scan_configs(path)
    libs = _scan_libraries(path)
    all_platforms = _scan_platforms(path)
    supported_platforms = _scan_supported_platforms(path)
    supported_os = _scan_supported_os(path)
    workload_types = _scan_workload_types(path)
    has_subdirs = _has_flow_subdirectories(path)
    flow_categories = _get_flow_categories(path)

    # Classify libraries
    wl_plugins = [l for l in libs if "WLPlugin" in l]
    flow_plugins = [l for l in libs if "FlowPlugin" in l]
    system_libs = [l for l in libs if l not in wl_plugins and l not in flow_plugins]

    return {
        "version": version,
        "package_name": f"ssmd_{version}_lin",
        "flows": flows,
        "flow_count": len(flows),
        "flow_categories": flow_categories,
        "has_flow_subdirs": has_subdirs,
        "configs": configs,
        "config_count": len(configs),
        "libraries_total": len(libs),
        "workload_plugins": len(wl_plugins),
        "flow_plugins": len(flow_plugins),
        "system_libs": len(system_libs),
        "all_platforms": all_platforms,
        "supported_platforms": supported_platforms,
        "supported_os": supported_os,
        "workload_types": workload_types,
        "wl_plugin_names": [l.replace("lib", "").replace(".so", "") for l in wl_plugins],
    }


def scan_all_versions():
    """Scan all SSMD packages and return structured data."""
    packages = _find_ssmd_packages()
    results = []
    for pkg in packages:
        try:
            data = scan_package(pkg)
            results.append(data)
        except Exception as e:
            results.append({"version": pkg["version"], "error": str(e)})
    return results


def compare_versions(v1_data, v2_data):
    """Compare two version scan results and return a diff."""
    diff = {
        "v1": v1_data["version"],
        "v2": v2_data["version"],
        "changes": [],
    }

    # Flow changes
    f1 = set(os.path.basename(f) for f in v1_data["flows"])
    f2 = set(os.path.basename(f) for f in v2_data["flows"])
    added_flows = f2 - f1
    removed_flows = f1 - f2
    if added_flows:
        diff["changes"].append({
            "category": "Flows",
            "type": "added",
            "icon": "🆕",
            "items": sorted(added_flows),
            "summary": f"新增 {len(added_flows)} 個 flow",
        })
    if removed_flows:
        diff["changes"].append({
            "category": "Flows",
            "type": "removed",
            "icon": "🗑",
            "items": sorted(removed_flows),
            "summary": f"移除 {len(removed_flows)} 個 flow",
        })

    # Config changes
    c1 = set(v1_data["configs"])
    c2 = set(v2_data["configs"])
    added_configs = c2 - c1
    removed_configs = c1 - c2
    if added_configs:
        diff["changes"].append({
            "category": "Configs",
            "type": "added",
            "icon": "🆕",
            "items": sorted(added_configs),
            "summary": f"新增 {len(added_configs)} 個 SSMON 設定檔",
        })
    if removed_configs:
        diff["changes"].append({
            "category": "Configs",
            "type": "removed",
            "icon": "🗑",
            "items": sorted(removed_configs),
            "summary": f"移除 {len(removed_configs)} 個 SSMON 設定檔",
        })

    # Library count change
    lib_diff = v2_data["libraries_total"] - v1_data["libraries_total"]
    if lib_diff != 0:
        diff["changes"].append({
            "category": "Libraries",
            "type": "changed",
            "icon": "📦" if lib_diff > 0 else "📉",
            "items": [],
            "summary": f"函式庫 {v1_data['libraries_total']} → {v2_data['libraries_total']} ({'增加' if lib_diff > 0 else '減少'} {abs(lib_diff)} 個)",
        })

    # WL Plugin changes
    wl1 = set(v1_data.get("wl_plugin_names", []))
    wl2 = set(v2_data.get("wl_plugin_names", []))
    added_wl = wl2 - wl1
    removed_wl = wl1 - wl2
    if added_wl:
        diff["changes"].append({
            "category": "Workload Plugins",
            "type": "added",
            "icon": "⚡",
            "items": sorted(added_wl),
            "summary": f"新增 {len(added_wl)} 個 workload plugin",
        })
    if removed_wl:
        diff["changes"].append({
            "category": "Workload Plugins",
            "type": "removed",
            "icon": "🗑",
            "items": sorted(removed_wl),
            "summary": f"移除 {len(removed_wl)} 個 workload plugin",
        })

    # Platform changes
    p1 = set(v1_data.get("supported_platforms", []) or v1_data["all_platforms"])
    p2 = set(v2_data.get("supported_platforms", []) or v2_data["all_platforms"])
    added_p = p2 - p1
    if added_p:
        diff["changes"].append({
            "category": "Platforms",
            "type": "added",
            "icon": "🖥",
            "items": sorted(added_p),
            "summary": f"新增 {len(added_p)} 個平台支援",
        })

    # Structural changes
    if not v1_data["has_flow_subdirs"] and v2_data["has_flow_subdirs"]:
        diff["changes"].append({
            "category": "Structure",
            "type": "improved",
            "icon": "📂",
            "items": v2_data["flow_categories"],
            "summary": "Flows 改為分類子目錄結構",
        })

    # Workload types from README
    wt1 = set(t["name"] for t in v1_data.get("workload_types", []))
    wt2 = set(t["name"] for t in v2_data.get("workload_types", []))
    added_wt = wt2 - wt1
    removed_wt = wt1 - wt2
    if added_wt:
        diff["changes"].append({
            "category": "Workload Types",
            "type": "added",
            "icon": "🔥",
            "items": sorted(added_wt),
            "summary": f"新增 {len(added_wt)} 種測試類型",
        })
    if removed_wt:
        diff["changes"].append({
            "category": "Workload Types",
            "type": "removed",
            "icon": "🗑",
            "items": sorted(removed_wt),
            "summary": f"移除 {len(removed_wt)} 種測試類型",
        })

    return diff
