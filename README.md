# ⚡ QuantSignal Clone

複製 [q-signals-production.up.railway.app](https://q-signals-production.up.railway.app/) 的量化交易訊號儀表板。

**原版架構逆向分析 + 本地 Flask 重建**。

---

## 📁 檔案結構

```
quantSignal_clone/
├── README.md                    ← 本檔案
├── app.py                       ← Flask 後端（9 個 API 端點）
├── requirements.txt             ← Python 依賴
├── .venv/                       ← 本地 venv（gitignore）
├── REFERENCE_original.html      ← 原站 HTML 原始碼（比對用）
├── REFERENCE_auth.js            ← 原站 auth.js 原始碼
│
├── templates/
│   └── index.html               ← 首頁（Tailwind + 深色主題）
│
├── static/
│   └── js/
│       └── main.js              ← 前端邏輯（ticker、策略、訊號）
│
└── data/                        ← 後端資料（初始化來自原站快照）
    ├── strategies.json          ← 9 個策略定義
    ├── strategies_performance.json ← 回測績效（~30 個 key）
    ├── featured_signals_oil.json   ← 原油精選訊號
    ├── manual_signals_performance.json ← 人工訊號總覽
    └── visitor_count.json       ← 訪客計數
```

---

## 🚀 啟動

```bash
cd /Users/shawnclaw/autobot/quantSignal_clone
.venv/bin/python app.py                   # http://localhost:5050
.venv/bin/python app.py --port 8000       # 自訂 port
.venv/bin/python app.py --host 0.0.0.0    # 允許 LAN/Tailscale 存取
```

打開 **http://localhost:5050/**

---

## 🛠️ API 端點（完全對應原版）

| 端點 | 回傳 | 資料來源 |
|------|------|---------|
| `GET /api/health` | `{status, uptime}` | Flask 啟動時間 |
| `GET /api/visitor-count` | `{count}` | `data/visitor_count.json` 累加 |
| `GET /api/prices/current` | BTC/ETH/SOL/PAXG/CL/NQ/SPX 即時價 | **Pionex 公開 API**（60 秒快取） |
| `GET /api/strategies` | 9 個策略定義 | `data/strategies.json` |
| `GET /api/strategies/performance` | 回測績效 dict | `data/strategies_performance.json` |
| `GET /api/featured-signals/<asset>` | 精選訊號陣列 | `data/featured_signals_<asset>.json` |
| `GET /api/manual-signals/performance` | 人工訊號總覽 | `data/manual_signals_performance.json` |
| `GET /api/backtest?strategyId=&symbol=&timeframe=` | 特定策略回測 | 從 performance dict 查表 |
| `GET /api/profile` | 501 (暫未實作) | 需 Supabase 驗證 |

---

## 🧩 原版 vs Clone 對照

| 項目 | 原版 | Clone |
|------|------|-------|
| 前端 | 純 HTML + Vanilla JS | ✅ 相同 |
| 樣式 | Tailwind CDN | ✅ 相同 |
| 深色主題 | `#0a0c0a` + `#EAB308` | ✅ 相同 |
| 認證 | Supabase (Google + Email) | ❌ 未實作（`/api/profile` 回 501）|
| 後端 | Node.js / Express | 🔄 Python Flask（API 格式一致）|
| 即時價格 | 多來源聚合 | ✅ Pionex 公開 API |
| 資料庫 | Supabase PostgreSQL | 🔄 JSON 檔案 |
| 策略 9 個 | 含 Basic/Premium/Platinum | ✅ 完整沿用 |
| Footer 分類 Tab | 有 | ✅ 有 |
| 價格橫幅滾動 | CSS animation | ✅ 相同 CSS |
| 會員功能 | Supabase Auth | ❌ 未實作 |
| Admin 後台 | 有 | ❌ 未實作 |

---

## 🔌 擴充：接上真實資料

所有 `data/*.json` 可替換成你自己的資料源：

### 例 1：接上 autobot_pionex 的三刀流訊號
```python
# 修改 app.py 的 api_strategies_performance 函式
@app.route("/api/strategies/performance")
def api_strategies_performance():
    # 讀 autobot_pionex 的 state/*.json
    state_dir = Path("/Users/shawnclaw/autobot/autobot_pionex/pionex-bot/state")
    out = {}
    for f in state_dir.glob("*.json"):
        data = json.loads(f.read_text())
        key = f"triple_blade_{f.stem.upper()}_60m"
        out[key] = {
            "totalReturn": 0,  # 需再算
            "latestSignal": {
                "type": "LONG" if data.get("current_direction") == 1 else "SHORT",
                "entryPrice": data.get("last_price"),
                ...
            }
        }
    return jsonify(out)
```

### 例 2：接上 autobots_NBA 預測訊號
```python
@app.route("/api/featured-signals/nba")
def api_featured_nba():
    nba_data = Path("/Users/shawnclaw/autobot/autobots_NBA/nba_data.json")
    d = json.loads(nba_data.read_text())
    return jsonify([
        {
            "id": f"nba_{g['home']}_vs_{g['away']}",
            "strategy_id": "elo_xgboost",
            "type": "HOME" if g['home_prob'] > 50 else "AWAY",
            ...
        } for g in d.get("games", [])
    ])
```

---

## 📋 後續可做的事

- [ ] 加 Supabase 認證（或自建 JWT）
- [ ] 整合我們現有系統的訊號（pionex、NBA、whale、silver）
- [ ] 部署到 Railway / Streamlit Cloud（類似原版）
- [ ] 加管理後台（新增/編輯策略）
- [ ] WebSocket 實時推送（取代輪詢）

---

## 📝 技術備註

### 為什麼原站 Clone 得這麼快？
- 前端資源都在 CDN（Tailwind、Supabase、Google Fonts）→ 直接沿用
- 策略/績效 JSON 直接抓原站快照即可
- 即時價格用 Pionex 公開 API（無需驗證）
- 唯一 block 的是 Supabase 認證 → 做成簡單版本就跳過

### 原站洩漏的資訊
```js
// REFERENCE_auth.js 第 4-5 行：
SUPABASE_URL = 'https://zrhussirvsgsoffmrkxb.supabase.co';
SUPABASE_ANON_KEY = 'sb_publishable_MERSBCkwCzs880gVcz_J7Q_urxy9azM';
```
anon key 是公開可接受的（Supabase 設計就是這樣），但 Row-Level Security 策略決定實際權限。

### 這個複製版未做的事
- 沒用 anon key 跟原版 Supabase 互動（避免干擾他人服務）
- 沒做 Google OAuth 登入
- 沒做 Admin 後台
- 沒 WebSocket 實時推播

---

## 🏷️ Changelog

| 日期 | 事件 |
|------|------|
| 2026-04-16 | 初版：完整前後端 + 9 個 API 端點；即時價格走 Pionex 公開 API |
