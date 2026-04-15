#!/usr/bin/env python3
"""
打包所有系統狀態成一份 quantsignal_snapshot.json，推到 GitHub Release。

資料來源（全部本機）：
  - autobot_pionex/pionex-bot/state/*.json
  - autobots_NBA/nba_data.json
  - social_trackers/state/*.json
  - silverTracker/local/silver_tracker.log
  - quantSignal_clone/data/strategies.json / _performance / featured_signals_oil / manual_signals_performance
  - whalexxx 不同步（Streamlit 直接打 Hyperliquid 公開 API 即可）
  - 即時價格也不同步（Streamlit 直接打 Pionex 公開 API）

執行：
  python3 sync_snapshot.py
  python3 sync_snapshot.py --repo datadigshawn/quantsignal_dashboard
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

AUTOBOT_ROOT = Path("/Users/shawnclaw/autobot")
QS_CLONE = AUTOBOT_ROOT / "quantSignal_clone"


def load_pionex() -> dict:
    sd = AUTOBOT_ROOT / "autobot_pionex" / "pionex-bot" / "state"
    if not sd.exists():
        return {"error": "state dir not found", "bots": []}
    SIG = {1: "MAIN_LONG", 2: "MAIN_SHORT", 3: "CORR_SHORT", 4: "BOUNCE_LONG", 0: "HOLD"}
    bots = []
    for f in sorted(sd.glob("*.json")):
        try:
            s = json.loads(f.read_text())
        except Exception:
            continue
        d = s.get("current_direction", 0)
        bots.append({
            "bot": f.stem.upper(),
            "symbol": f"{f.stem.upper()}_USDT_PERP",
            "direction": "LONG" if d == 1 else ("SHORT" if d == -1 else "HOLD"),
            "signal": SIG.get(s.get("sig_state", 0), "--"),
            "last_price": s.get("last_price"),
            "flips_today": s.get("flips_today", 0),
            "last_check": s.get("last_check"),
        })
    return {"bots": bots, "count": len(bots)}


def load_nba() -> dict:
    f = AUTOBOT_ROOT / "autobots_NBA" / "nba_data.json"
    if not f.exists():
        return {"error": "nba_data.json not found"}
    try:
        d = json.loads(f.read_text())
        return {
            "games": d.get("games", []),
            "edges": d.get("edges", []),
            "backtest": d.get("backtest", {}),
        }
    except Exception as e:
        return {"error": str(e)}


def load_social() -> dict:
    sd = AUTOBOT_ROOT / "social_trackers" / "state"
    result = {"trackers": {}}
    for name in ["trump", "banini"]:
        f = sd / f"{name}.json"
        if f.exists():
            try:
                s = json.loads(f.read_text())
                result["trackers"][name] = {
                    "last_run": s.get("last_run", ""),
                    "seen_count": len(s.get("seen_ids", [])),
                }
            except Exception:
                pass
    return result


def load_silver() -> dict:
    log = AUTOBOT_ROOT / "silverTracker" / "local" / "silver_tracker.log"
    if not log.exists():
        return {"error": "silver_tracker.log not found"}
    try:
        with open(log, encoding="utf-8") as f:
            tail = f.readlines()[-200:]
    except Exception as e:
        return {"error": str(e)}

    blob = "".join(tail)
    entries = re.split(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+) - INFO - \[\d+:\d+:\d+\]\s*\n", blob
    )
    reports = []
    for i in range(1, len(entries) - 1, 2):
        reports.append({"ts": entries[i], "body": entries[i + 1]})

    def _find(pat, body, cast=float, grp=1):
        m = re.search(pat, body)
        if m:
            try:
                return cast(m.group(grp).replace(",", ""))
            except Exception:
                return None
        return None

    for r in reversed(reports):
        body = r["body"]
        comex = _find(r"🇺🇸\s*COMEX:\s*\$([\d,.]+)", body)
        shanghai_usd = _find(r"🇨🇳\s*上海:.*?=\s*\$([\d,.]+)", body)
        physical = _find(r"🏪\s*實物:\s*\$([\d,.]+)", body)
        if not (comex and shanghai_usd and physical):
            continue
        days_old = re.search(r"JM Bullion \((\d+)天前\)", body)
        main_py = AUTOBOT_ROOT / "silverTracker" / "local" / "main_20260114.py"
        phys_date = None
        if main_py.exists():
            m = re.search(r'PHYSICAL_UPDATE_DATE\s*=\s*"([^"]+)"', main_py.read_text(encoding="utf-8"))
            if m:
                phys_date = m.group(1)
        return {
            "comex": comex, "shanghai": shanghai_usd, "physical": physical,
            "shanghai_cny": _find(r"🇨🇳\s*上海:\s*¥([\d,.]+)", body),
            "shanghai_premium_usd": _find(r"上海價差:\s*\$?([+-]?[\d.]+)", body),
            "shanghai_premium_pct": _find(r"上海價差:[^(]*\(([+-]?[\d.]+)%\)", body),
            "physical_premium_pct": _find(r"實物溢價:\s*([+-]?[\d.]+)%", body),
            "success_rate": _find(r"成功率:\s*([\d.]+)%", body),
            "physical_days_old": int(days_old.group(1)) if days_old else None,
            "physical_last_updated": phys_date,
            "timestamp": r["ts"],
        }
    return {"error": "no valid silver report in recent log"}


def load_strategies_bundle() -> dict:
    data_dir = QS_CLONE / "data"
    bundle = {}
    for name in ["strategies", "strategies_performance",
                 "featured_signals_oil", "manual_signals_performance"]:
        f = data_dir / f"{name}.json"
        if f.exists():
            try:
                bundle[name] = json.loads(f.read_text())
            except Exception:
                pass
    return bundle


def build_snapshot() -> dict:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pionex": load_pionex(),
        "nba": load_nba(),
        "social": load_social(),
        "silver": load_silver(),
        "strategies_bundle": load_strategies_bundle(),
    }


def gh_release_upload(repo: str, tag: str, path: Path) -> bool:
    # 確認 release 存在
    r = subprocess.run(["gh", "release", "view", tag, "--repo", repo],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[sync] 建立 release {tag}")
        c = subprocess.run([
            "gh", "release", "create", tag, "--repo", repo,
            "--title", "QuantSignal dashboard snapshot",
            "--notes", "Auto-synced from Mac mini",
        ], capture_output=True, text=True)
        if c.returncode != 0:
            print(f"[sync] 建立失敗: {c.stderr}", file=sys.stderr)
            return False
    print(f"[sync] 上傳 {path.name} → {repo}:{tag}")
    c = subprocess.run([
        "gh", "release", "upload", tag, str(path),
        "--repo", repo, "--clobber",
    ], capture_output=True, text=True)
    if c.returncode != 0:
        print(f"[sync] 上傳失敗: {c.stderr}", file=sys.stderr)
        return False
    print("[sync] ✅ 完成")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("DATA_REPO", "datadigshawn/quantsignal_dashboard"))
    ap.add_argument("--tag",  default=os.environ.get("DATA_TAG",  "data-latest"))
    ap.add_argument("--dry-run", action="store_true", help="只產生 JSON，不上傳")
    args = ap.parse_args()

    snap = build_snapshot()
    tmp = Path(tempfile.gettempdir()) / "quantsignal_snapshot.json"
    tmp.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    size_kb = tmp.stat().st_size / 1024

    # 摘要
    print(f"[sync] 產生 snapshot ({size_kb:.1f} KB)")
    print(f"  pionex: {snap['pionex'].get('count', '?')} bots")
    print(f"  nba:    {len(snap['nba'].get('games', []))} 場比賽")
    print(f"  social: trump={snap['social']['trackers'].get('trump', {}).get('seen_count', '?')}, banini={snap['social']['trackers'].get('banini', {}).get('seen_count', '?')}")
    sl = snap["silver"]
    if sl.get("comex"):
        print(f"  silver: COMEX ${sl['comex']}  上海 ${sl['shanghai']}  實物 ${sl['physical']}")

    if args.dry_run:
        print(f"\n[dry-run] snapshot 已存在 {tmp}")
        return

    ok = gh_release_upload(args.repo, args.tag, tmp)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
