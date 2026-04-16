"""
QuantSignal Clone — Flask 後端
================================
複製 q-signals-production.up.railway.app 的 API 結構。

啟動：
    python app.py                    # http://localhost:5050
    python app.py --port 8000

所有 /api/* 端點都回傳與原站相同的 JSON 格式。
前端走 /templates/index.html，靜態資源在 /static/。
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from flask import Flask, jsonify, request, send_file

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    template_folder=str(TEMPLATE_DIR),
    static_url_path="/static",
)

START_TIME = time.time()
VISITOR_COUNT_FILE = DATA_DIR / "visitor_count.json"


# ──────────────────────────────────────────────────────────────
# 資料層：從 JSON 檔讀（可隨時換成真實 API / 資料庫）
# ──────────────────────────────────────────────────────────────
def _load_json(name: str, default):
    f = DATA_DIR / name
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _save_json(name: str, data):
    (DATA_DIR / name).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ──────────────────────────────────────────────────────────────
# Routes：頁面
# ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_file(str(TEMPLATE_DIR / "index.html"))


# ──────────────────────────────────────────────────────────────
# API：系統狀態
# ──────────────────────────────────────────────────────────────
@app.route("/api/health")
def api_health():
    return jsonify({"status": "ok", "uptime": time.time() - START_TIME})


@app.route("/api/visitor-count")
def api_visitor_count():
    data = _load_json("visitor_count.json", {"count": 0})
    data["count"] = data.get("count", 0) + 1
    _save_json("visitor_count.json", data)
    return jsonify({"count": data["count"]})


# ──────────────────────────────────────────────────────────────
# API：即時價格（走真實公開 API，不需驗證）
# ──────────────────────────────────────────────────────────────
_PRICE_CACHE = {"data": None, "ts": 0}
_PRICE_TTL = 60  # 秒


def _fetch_crypto_prices() -> dict:
    """Pionex 公開 API（無需 key）— 抓 BTC/ETH/SOL/PAXG/CL/SPX/NQ etc."""
    symbols = [
        ("BTCUSDT", "BTC_USDT"),
        ("ETHUSDT", "ETH_USDT"),
        ("SOLUSDT", "SOL_USDT"),
        ("PAXGUSDT", "PAXG_USDT"),
        ("CLUSDT", "CL_USDT_PERP"),
        ("NQUSDT", "NQ_USDT_PERP"),
        ("SPXUSDT", "SPX_USDT_PERP"),
    ]
    out = {}
    try:
        for display, pionex_sym in symbols:
            url = f"https://api.pionex.com/api/v1/market/tickers?symbol={pionex_sym}"
            r = httpx.get(url, timeout=8)
            if r.status_code != 200:
                continue
            tickers = (r.json().get("data") or {}).get("tickers") or []
            if not tickers:
                continue
            t = tickers[0]
            close = float(t.get("close", 0))
            open_ = float(t.get("open", close))
            change = ((close - open_) / open_ * 100) if open_ else 0
            out[display] = {
                "price": close,
                "change24h": change,
                "high24h": float(t.get("high", 0)),
                "low24h": float(t.get("low", 0)),
                "volume24h": float(t.get("volume", 0)),
                "timestamp": int(time.time() * 1000),
                "source": "pionex",
            }
    except Exception as e:
        print(f"[prices] {e}")
    return out


@app.route("/api/prices/current")
def api_prices_current():
    now = time.time()
    if not _PRICE_CACHE["data"] or now - _PRICE_CACHE["ts"] > _PRICE_TTL:
        _PRICE_CACHE["data"] = _fetch_crypto_prices()
        _PRICE_CACHE["ts"] = now
    return jsonify(_PRICE_CACHE["data"])


# ──────────────────────────────────────────────────────────────
# API：策略
# ──────────────────────────────────────────────────────────────
@app.route("/api/strategies")
def api_strategies():
    data = _load_json("strategies.json", {"strategies": []})
    return jsonify(data)


@app.route("/api/strategies/performance")
def api_strategies_performance():
    data = _load_json("strategies_performance.json", {})
    return jsonify(data)


# ──────────────────────────────────────────────────────────────
# API：訊號
# ──────────────────────────────────────────────────────────────
@app.route("/api/featured-signals/<asset>")
def api_featured_signals(asset: str):
    data = _load_json(f"featured_signals_{asset}.json", [])
    return jsonify(data)


@app.route("/api/manual-signals/performance")
def api_manual_signals_performance():
    data = _load_json("manual_signals_performance.json",
                      {"totalRoi": 0.0, "closedCount": 0})
    return jsonify(data)


# ──────────────────────────────────────────────────────────────
# API：回測（簡化示範）
# ──────────────────────────────────────────────────────────────
@app.route("/api/backtest")
def api_backtest():
    sid = request.args.get("strategyId", "")
    sym = request.args.get("symbol", "")
    tf = request.args.get("timeframe", "")
    if not (sid and sym and tf):
        return jsonify({"error": "missing params: strategyId, symbol, timeframe"}), 400

    # 從 performance 資料取出對應 key
    perf = _load_json("strategies_performance.json", {})
    key = f"{sid}_{sym}_{tf}"
    if key in perf:
        return jsonify({"key": key, "performance": perf[key]})
    return jsonify({"error": f"no backtest data for {key}"}), 404


# ──────────────────────────────────────────────────────────────
# API：使用者 profile（示範 — 無真實 Supabase 驗證）
# ──────────────────────────────────────────────────────────────
@app.route("/api/profile")
def api_profile():
    # 這裡需要 Supabase JWT 驗證才行；clone 版暫無登入功能
    return jsonify({"error": "auth not implemented in clone"}), 501


# ══════════════════════════════════════════════════════════════
# MY SYSTEMS — 整合 /autobot/ 下其他專案的資料
# ══════════════════════════════════════════════════════════════
AUTOBOT_ROOT = Path("/Users/shawnclaw/autobot")


# ── Pionex 三刀流 9 個 bot ──────────────────────────────────────
@app.route("/api/my/pionex")
def api_my_pionex():
    """從 autobot_pionex/state/*.json 讀 9 個 bot 當前狀態。"""
    state_dir = AUTOBOT_ROOT / "autobot_pionex" / "pionex-bot" / "state"
    if not state_dir.exists():
        return jsonify({"error": "pionex state dir not found", "bots": []})

    SIG_MAP = {1: "MAIN_LONG", 2: "MAIN_SHORT", 3: "CORR_SHORT", 4: "BOUNCE_LONG", 0: "HOLD"}
    bots = []
    for f in sorted(state_dir.glob("*.json")):
        try:
            s = json.loads(f.read_text())
        except Exception:
            continue
        direction = s.get("current_direction", 0)
        bots.append({
            "bot": f.stem.upper(),
            "symbol": f"{f.stem.upper()}_USDT_PERP",
            "direction": "LONG" if direction == 1 else ("SHORT" if direction == -1 else "HOLD"),
            "signal": SIG_MAP.get(s.get("sig_state", 0), "--"),
            "last_price": s.get("last_price"),
            "flips_today": s.get("flips_today", 0),
            "last_check": s.get("last_check"),
            "initialized": s.get("initialized", False),
        })
    return jsonify({"bots": bots, "count": len(bots)})


# ── NBA 預測 ──────────────────────────────────────────────────
@app.route("/api/my/nba")
def api_my_nba():
    nba_file = AUTOBOT_ROOT / "autobots_NBA" / "nba_data.json"
    if not nba_file.exists():
        return jsonify({"error": "nba_data.json not found"})
    try:
        d = json.loads(nba_file.read_text())
    except Exception as e:
        return jsonify({"error": f"parse error: {e}"})
    return jsonify({
        "games": d.get("games", []),
        "edges": d.get("edges", []),
        "backtest": d.get("backtest", {}),
        "updated": datetime.fromtimestamp(nba_file.stat().st_mtime).isoformat(),
    })


# ── Hyperliquid 鯨魚（live API）───────────────────────────────
_WHALE_CACHE = {"data": None, "ts": 0}


@app.route("/api/my/whale")
def api_my_whale():
    """直接打 Hyperliquid API 取鯨魚當前持倉。"""
    # 讀 whalexxx/.env 拿 TARGET_WALLET
    env_file = AUTOBOT_ROOT / "whalexxx" / ".env"
    wallet = "0x9d32884370875f2960d5cc4b95be26687d69aff5"  # 預設
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("TARGET_WALLET="):
                wallet = line.split("=", 1)[1].strip().strip('"')

    # 60 秒快取
    if _WHALE_CACHE["data"] and time.time() - _WHALE_CACHE["ts"] < 60:
        return jsonify(_WHALE_CACHE["data"])

    positions = []
    for dex in ["", "xyz"]:
        try:
            body = {"type": "clearinghouseState", "user": wallet}
            if dex:
                body["dex"] = dex
            r = httpx.post("https://api.hyperliquid.xyz/info", json=body, timeout=10)
            r.raise_for_status()
            d = r.json()
            for ap in d.get("assetPositions", []):
                p = ap.get("position", {})
                if float(p.get("szi", 0) or 0) == 0:
                    continue
                szi = float(p.get("szi", 0))
                positions.append({
                    "dex": dex or "main",
                    "coin": p.get("coin"),
                    "side": "LONG" if szi > 0 else "SHORT",
                    "size": abs(szi),
                    "entry": float(p.get("entryPx", 0)),
                    "value": float(p.get("positionValue", 0)),
                    "pnl": float(p.get("unrealizedPnl", 0)),
                    "leverage": p.get("leverage", {}).get("value", 1),
                    "leverage_type": p.get("leverage", {}).get("type", "cross"),
                })
        except Exception as e:
            print(f"[whale {dex}] {e}")

    total_value = sum(p["value"] for p in positions)
    total_pnl = sum(p["pnl"] for p in positions)
    result = {
        "wallet": wallet,
        "positions": positions,
        "count": len(positions),
        "total_value": total_value,
        "total_pnl": total_pnl,
        "updated_at": datetime.now().isoformat(),
    }
    _WHALE_CACHE["data"] = result
    _WHALE_CACHE["ts"] = time.time()
    return jsonify(result)


# ── 白銀追蹤（解析 silverTracker log）────────────────────────
@app.route("/api/my/silver")
def api_my_silver():
    """從 silverTracker/local/silver_tracker.log 取最新一筆三市場價格。"""
    import re
    log_file = AUTOBOT_ROOT / "silverTracker" / "local" / "silver_tracker.log"
    if not log_file.exists():
        return jsonify({"error": "silver_tracker.log not found"}), 404

    # 讀最後 200 行（~20 筆報告）
    try:
        with open(log_file, encoding="utf-8") as f:
            tail = f.readlines()[-200:]
    except Exception as e:
        return jsonify({"error": f"read log: {e}"}), 500

    # 從底部往上找最近一筆完整報告（含 COMEX / 上海 / 實物）
    blob = "".join(tail)
    # 切分每筆報告（以時間戳 `- INFO - [HH:MM:SS]` 開頭）
    entries = re.split(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) - INFO - \[\d+:\d+:\d+\]\s*\n", blob)
    # entries 格式：[前言, 時間1, 內容1, 時間2, 內容2, ...]
    reports = []
    for i in range(1, len(entries) - 1, 2):
        reports.append({"ts": entries[i], "body": entries[i + 1]})

    result = {
        "comex": None, "shanghai": None, "physical": None,
        "shanghai_premium_usd": None, "shanghai_premium_pct": None,
        "physical_premium_pct": None, "success_rate": None,
        "timestamp": None, "physical_days_old": None,
    }

    # 從最新的一筆開始找
    for r in reversed(reports):
        body = r["body"]

        def _find(pattern, group=1, cast=float):
            m = re.search(pattern, body)
            if m:
                try:
                    return cast(m.group(group).replace(",", ""))
                except Exception:
                    return None
            return None

        comex = _find(r"🇺🇸\s*COMEX:\s*\$([\d,.]+)")
        shanghai_usd = _find(r"🇨🇳\s*上海:.*?=\s*\$([\d,.]+)")
        shanghai_cny = _find(r"🇨🇳\s*上海:\s*¥([\d,.]+)")
        physical = _find(r"🏪\s*實物:\s*\$([\d,.]+)")
        sh_diff = _find(r"上海價差:\s*\$?([+-]?[\d.]+)")
        sh_diff_pct = _find(r"上海價差:[^(]*\(([+-]?[\d.]+)%\)")
        phys_prem = _find(r"實物溢價:\s*([+-]?[\d.]+)%")
        success_rate = _find(r"成功率:\s*([\d.]+)%")
        days_old_m = re.search(r"JM Bullion \((\d+)天前\)", body)

        if comex and shanghai_usd and physical:
            result["comex"] = comex
            result["shanghai"] = shanghai_usd
            result["shanghai_cny"] = shanghai_cny
            result["physical"] = physical
            result["shanghai_premium_usd"] = sh_diff
            result["shanghai_premium_pct"] = sh_diff_pct
            result["physical_premium_pct"] = phys_prem
            result["success_rate"] = success_rate
            result["timestamp"] = r["ts"]
            result["physical_days_old"] = int(days_old_m.group(1)) if days_old_m else None
            break

    # 讀 PHYSICAL_UPDATE_DATE 從程式裡（精確日期）
    main_py = AUTOBOT_ROOT / "silverTracker" / "local" / "main_20260114.py"
    if main_py.exists():
        try:
            code = main_py.read_text(encoding="utf-8")
            m = re.search(r'PHYSICAL_UPDATE_DATE\s*=\s*"([^"]+)"', code)
            if m:
                result["physical_last_updated"] = m.group(1)
        except Exception:
            pass

    return jsonify(result)


# ── 社群追蹤（川普 + 巴逆逆）────────────────────────────────
@app.route("/api/my/social")
def api_my_social():
    state_dir = AUTOBOT_ROOT / "social_trackers" / "state"
    result = {"trackers": {}}
    for name in ["trump", "banini"]:
        f = state_dir / f"{name}.json"
        if not f.exists():
            continue
        try:
            s = json.loads(f.read_text())
            result["trackers"][name] = {
                "last_run": s.get("last_run", ""),
                "seen_count": len(s.get("seen_ids", [])),
            }
        except Exception:
            pass
    result["updated_at"] = datetime.now().isoformat()
    return jsonify(result)


# ── 運彩 Edge（NBA）─────────────────────────────────────────
@app.route("/api/my/sport_edge")
def api_my_sport_edge():
    """讀 sportWeb 最新 odds + 跑 edge_detector，回傳 edge 清單。"""
    sportweb_dir = AUTOBOT_ROOT / "sportWeb"
    odds_file = sportweb_dir / "data" / "latest_odds.json"

    if not odds_file.exists():
        return jsonify({"error": "no odds data (sportWeb fetcher 未跑過)"}), 200

    # 讀最新 odds
    try:
        odds_data = json.loads(odds_file.read_text())
    except Exception as e:
        return jsonify({"error": f"parse odds: {e}"}), 200

    # 直接呼叫 edge_detector 取結果
    import subprocess
    python_bin = sportweb_dir / ".venv" / "bin" / "python"
    if not python_bin.exists():
        return jsonify({"error": "sportWeb venv not found"}), 200

    try:
        r = subprocess.run(
            [str(python_bin), str(sportweb_dir / "src" / "edge_detector.py"),
             "--json", "--min-edge", "0.0"],
            capture_output=True, text=True, timeout=10,
            cwd=str(sportweb_dir),
        )
        edges_result = json.loads(r.stdout) if r.returncode == 0 and r.stdout else {"edges": [], "count": 0}
    except Exception as e:
        edges_result = {"error": str(e), "edges": [], "count": 0}

    return jsonify({
        "fetched_at": odds_data.get("fetched_at"),
        "odds_games": odds_data.get("games", []),
        "edges": edges_result.get("edges", []),
        "edge_count": edges_result.get("count", 0),
        "updated_at": datetime.now().isoformat(),
    })


# ── 統一總覽 ──────────────────────────────────────────────────
@app.route("/api/my/summary")
def api_my_summary():
    """聚合所有系統的關鍵數字。"""
    summary = {}

    # Pionex
    try:
        state_dir = AUTOBOT_ROOT / "autobot_pionex" / "pionex-bot" / "state"
        longs = shorts = holds = 0
        for f in state_dir.glob("*.json"):
            s = json.loads(f.read_text())
            d = s.get("current_direction", 0)
            if d == 1: longs += 1
            elif d == -1: shorts += 1
            else: holds += 1
        summary["pionex"] = {"longs": longs, "shorts": shorts, "holds": holds,
                             "total": longs + shorts + holds}
    except Exception:
        summary["pionex"] = {"error": True}

    # NBA
    try:
        nba = json.loads((AUTOBOT_ROOT / "autobots_NBA" / "nba_data.json").read_text())
        summary["nba"] = {
            "games_today": len(nba.get("games", [])),
            "edges": len(nba.get("edges", [])),
            "win_rate": nba.get("backtest", {}).get("all_wr", 0),
        }
    except Exception:
        summary["nba"] = {"error": True}

    # Social
    try:
        sd = AUTOBOT_ROOT / "social_trackers" / "state"
        summary["social"] = {
            "trump_seen": len(json.loads((sd / "trump.json").read_text()).get("seen_ids", [])),
            "banini_seen": len(json.loads((sd / "banini.json").read_text()).get("seen_ids", [])),
        }
    except Exception:
        summary["social"] = {"error": True}

    # Silver（直接 call 內部 function）
    try:
        with app.test_client() as c:
            rv = c.get("/api/my/silver")
            if rv.status_code == 200:
                s = rv.get_json()
                summary["silver"] = {
                    "comex": s.get("comex"),
                    "shanghai": s.get("shanghai"),
                    "physical": s.get("physical"),
                    "shanghai_premium_pct": s.get("shanghai_premium_pct"),
                }
    except Exception:
        summary["silver"] = {"error": True}

    # Sport Edge（NBA 運彩）
    try:
        odds_file = AUTOBOT_ROOT / "sportWeb" / "data" / "latest_odds.json"
        if odds_file.exists():
            d = json.loads(odds_file.read_text())
            games = d.get("games", [])
            summary["sport_edge"] = {
                "games": len(games),
                "last_fetched": d.get("fetched_at", ""),
            }
    except Exception:
        summary["sport_edge"] = {"error": True}

    summary["generated_at"] = datetime.now().isoformat()
    return jsonify(summary)


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5050)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()

    print(f"🚀 QuantSignal Clone running on http://{args.host}:{args.port}")
    print(f"   static: {STATIC_DIR}")
    print(f"   data:   {DATA_DIR}")
    app.run(host=args.host, port=args.port, debug=False)
