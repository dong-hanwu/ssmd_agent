"""
SSMD Web Agent - Intel System Stress & Memory Diagnostics Assistant
A web-based intelligent agent for SSMD usage support and dashboard.
Supports per-session conversation memory for context-aware chat.
Author: Dong-han Wu
"""

from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from ssmd_knowledge import SSMDKnowledge
from version_scanner import scan_all_versions, compare_versions
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app)

# Per-session knowledge instances (simple in-memory store)
_sessions = {}
# Cache version scan results
_version_cache = None


def _get_kb():
    """Get or create a knowledge instance for the current session."""
    sid = session.get("sid")
    if not sid:
        sid = secrets.token_hex(16)
        session["sid"] = sid
    if sid not in _sessions:
        _sessions[sid] = SSMDKnowledge()
    return _sessions[sid]


def _get_versions():
    """Get cached version scan results."""
    global _version_cache
    if _version_cache is None:
        _version_cache = scan_all_versions()
    return _version_cache


@app.route("/")
def index():
    """Main page with chat + dashboard."""
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """Chat endpoint - receives user question, returns answer."""
    data = request.get_json()
    user_msg = data.get("message", "").strip()
    if not user_msg:
        return jsonify({"reply": "請輸入您的問題。"})

    kb = _get_kb()
    reply = kb.answer(user_msg)
    return jsonify({"reply": reply})


@app.route("/api/chat/reset", methods=["POST"])
def reset_chat():
    """Reset the conversation history."""
    sid = session.get("sid")
    if sid and sid in _sessions:
        _sessions[sid] = SSMDKnowledge()
    return jsonify({"status": "ok"})


@app.route("/api/dashboard")
def dashboard_data():
    """Return structured dashboard data for the frontend."""
    kb = SSMDKnowledge()
    return jsonify(kb.get_dashboard_data())


@app.route("/api/flows")
def flows_data():
    """Return all available flow configurations."""
    kb = SSMDKnowledge()
    return jsonify(kb.get_flows_detail())


@app.route("/api/command", methods=["POST"])
def generate_command():
    """Generate a command based on user requirements."""
    data = request.get_json()
    requirement = data.get("requirement", "")
    kb = _get_kb()
    return jsonify({"command": kb.generate_command(requirement)})


@app.route("/api/versions")
def versions():
    """Return all scanned SSMD version data."""
    return jsonify(_get_versions())


@app.route("/api/versions/compare")
def versions_compare():
    """Compare two versions. ?v1=xxx&v2=yyy"""
    v1_str = request.args.get("v1", "")
    v2_str = request.args.get("v2", "")
    all_versions = _get_versions()

    v1_data = next((v for v in all_versions if v["version"] == v1_str), None)
    v2_data = next((v for v in all_versions if v["version"] == v2_str), None)

    if not v1_data or not v2_data:
        return jsonify({"error": "Version not found"}), 404

    diff = compare_versions(v1_data, v2_data)
    return jsonify(diff)


@app.route("/api/versions/refresh", methods=["POST"])
def versions_refresh():
    """Force rescan of all versions."""
    global _version_cache
    _version_cache = None
    return jsonify({"status": "ok", "versions": _get_versions()})


if __name__ == "__main__":
    # Pre-scan versions on startup
    print("=" * 60)
    print("  SSMD Web Agent Starting...")
    versions_found = _get_versions()
    print(f"  Scanned {len(versions_found)} SSMD version(s)")
    for v in versions_found:
        print(f"    - v{v['version']} ({v.get('flow_count', '?')} flows, {v.get('libraries_total', '?')} libs)")
    print(f"  Open browser: http://localhost:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)
