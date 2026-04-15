# SSMD Web Agent

> **Intel System Stress & Memory Diagnostics — Web-based Intelligent Assistant & Dashboard**

Author: **Dong-han Wu**

---

## Overview

SSMD Web Agent 是一個基於 Flask 的網頁應用程式，提供：

1. 🤖 **AI 智能助手** — GPT 風格的對話式問答，回答所有 SSMD 使用問題
2. 📊 **Dashboard** — 快速總覽目前 SSMD 版本的所有內容
3. 📦 **版本歷史比較** — 自動掃描本地所有 SSMD 套件，比較版本差異
4. 📖 **指令參考** — 快速查詢常用指令，支援搜尋與一鍵複製

## Quick Start

### 1. 安裝相依套件

```bash
pip install -r requirements.txt
```

### 2. 放置 SSMD 套件

將 SSMD 套件解壓到以下任一位置：

- 專案根目錄：`ssmd_agent/ssmd_YYYY.MM.DD.XXXX_lin/`
- ssmd 子目錄：`ssmd_agent/ssmd/ssmd_YYYY.MM.DD.XXXX_lin/`

系統會自動掃描所有版本。

### 3. 啟動伺服器

```bash
python app.py
```

伺服器會啟動在 `http://localhost:5000`。

## Project Structure

```
ssmd_agent/
├── app.py                  # Flask 主程式（路由、API endpoints）
├── ssmd_knowledge.py       # AI 對話引擎（意圖偵測、動態回答）
├── version_scanner.py      # 版本掃描器（自動解析 SSMD 套件）
├── templates/
│   └── index.html          # 前端介面（Dashboard + Chat + Versions + Reference）
├── requirements.txt        # Python 相依套件
├── .gitignore              # Git 排除規則
├── ssmd_2026.03.16.76a2_lin/   # SSMD 最新版本套件（不上傳 Git）
├── ssmd/                       # 過往版本目錄（不上傳 Git）
│   ├── ssmd_2025.11.10.4ed3_lin/
│   └── ssmd_2026.01.26.2446_lin/
└── README.md               # 本文件
```

## Features

### AI 助手

- **意圖偵測引擎** — 25+ 組規則，自動辨識使用者意圖
- **實體擷取** — 自動偵測 flow 名稱、平台代號、AVX 寬度等
- **動態回答組合** — 根據問題細節組裝精準回答
- **對話記憶** — 支援上下文追問（per-session）
- **場景推薦** — 描述「新機驗收」等場景，自動規劃測試流程

### Dashboard

- 版本資訊總覽
- Flow 測試分類與參數
- SSMON 監測設定檔
- 遙測指標類型
- 支援平台與作業系統

### 版本歷史比較

- 自動掃描本地所有 SSMD 套件目錄
- 視覺化時間軸顯示各版本
- 任意兩版本差異比較（Flows、Configs、Libraries、Plugins、Platforms）

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | 主頁面 |
| `/api/chat` | POST | AI 對話 `{message: "..."}` |
| `/api/chat/reset` | POST | 重置對話歷史 |
| `/api/dashboard` | GET | Dashboard 資料 |
| `/api/flows` | GET | 所有 Flow 詳細資料 |
| `/api/command` | POST | 產生指令 `{requirement: "..."}` |
| `/api/versions` | GET | 所有版本掃描結果 |
| `/api/versions/compare` | GET | 比較兩版本 `?v1=xxx&v2=yyy` |
| `/api/versions/refresh` | POST | 強制重新掃描版本 |

## Supported SSMD Versions

系統會自動掃描以下目錄中的 SSMD 套件：
- 專案根目錄下的 `ssmd_*_lin/`
- `ssmd/` 子目錄下的 `ssmd_*_lin/`

新增版本只需將套件解壓到上述任一位置，然後重啟伺服器或呼叫 `/api/versions/refresh`。

## Tech Stack

- **Backend**: Python 3 + Flask
- **Frontend**: Vanilla HTML/CSS/JS (Single Page Application)
- **AI Engine**: Rule-based intent detection + dynamic response composition
- **No external AI API required** — 所有知識都內建在 `ssmd_knowledge.py`

## License

Internal use only — Intel Confidential.

---

*Created by Dong-han Wu*
