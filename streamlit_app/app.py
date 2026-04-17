"""
⚡ QuantSignal — Streamlit Cloud 版

Mac mini 的所有系統整合（Pionex / NBA / 鯨魚 / 社群 / 白銀）聚合儀表板。

資料流：
  Mac mini sync_snapshot.py → GitHub Release data-latest/quantsignal_snapshot.json
                            ↓ (讀取)
  Streamlit Cloud（本 app）+ Pionex/Hyperliquid 公開 API 直連
"""
import io
import json
import os
import traceback
import urllib.request
from datetime import datetime, timedelta, timezone

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ─────────────────────────────────────────────
st.set_page_config(
    page_title="QuantSignal 我的系統",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

TZ_TW = timezone(timedelta(hours=8))


# ─── 樣式 ────────────────────────────────────
st.markdown("""
<style>
  .stApp { background: #0a0c0a; color: #e8f1ff; }
  h1 { color: #EAB308 !important; font-size: 32px !important; font-weight: 900 !important; letter-spacing: 1px; margin-bottom: 0 !important; }
  h2, h3 { color: #EAB308 !important; font-size: 22px !important; }

  .bigcard {
    background: linear-gradient(135deg, #161d16 0%, #0a1a0a 100%);
    border: 2px solid #243324;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
  }

  .chip {
    display: inline-block; padding: 4px 10px; border-radius: 20px;
    font-family: monospace; font-size: 12px; font-weight: 800;
  }
  .chip-long  { background: rgba(16,185,129,.2); border: 1px solid #10B981; color: #10B981; }
  .chip-short { background: rgba(239,68,68,.2); border: 1px solid #EF4444; color: #ff6688; }
  .chip-hold  { background: rgba(100,120,140,.2); border: 1px solid #788aa0; color: #aac0d6; }
  .chip-gold  { background: rgba(234,179,8,.2); border: 1px solid #EAB308; color: #EAB308; }

  [data-testid="stMetricValue"] { font-family: monospace !important; font-size: 28px !important; font-weight: 900 !important; color: #ffffff !important; }
  [data-testid="stMetricLabel"] { font-size: 13px !important; color: #EAB308 !important; font-weight: 700 !important; }

  [data-testid="stMetric"] {
    background: #161d16;
    border: 1px solid #243324;
    border-radius: 10px;
    padding: 12px;
  }
</style>
""", unsafe_allow_html=True)


# ─── 設定 ────────────────────────────────────
def _secret(k, default=""):
    try:
        v = st.secrets.get(k)
        if v: return v
    except Exception: pass
    return os.environ.get(k, default)

DATA_REPO  = _secret("DATA_REPO",  "datadigshawn/quantsignal_dashboard")
DATA_TAG   = _secret("DATA_TAG",   "data-latest")
DATA_ASSET = "quantsignal_snapshot.json"
WHALE_WALLET = _secret("WHALE_WALLET", "0x9d32884370875f2960d5cc4b95be26687d69aff5")


# ─── 資料載入 ────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_snapshot() -> dict:
    """從 GitHub Release 直接下載（不走 api.github.com，無 rate limit）。"""
    url = f"https://github.com/{DATA_REPO}/releases/download/{DATA_TAG}/{DATA_ASSET}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Streamlit QuantSignal)",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"_error": str(e)}


@st.cache_data(ttl=60, show_spinner=False)
def load_live_prices() -> dict:
    """直接打 Pionex 公開 API。"""
    symbols = [("BTCUSDT","BTC_USDT"),("ETHUSDT","ETH_USDT"),("SOLUSDT","SOL_USDT"),
               ("PAXGUSDT","PAXG_USDT"),("CLUSDT","CL_USDT_PERP"),
               ("NQUSDT","NQ_USDT_PERP"),("SPXUSDT","SPX_USDT_PERP")]
    out = {}
    for display, sym in symbols:
        try:
            r = httpx.get(f"https://api.pionex.com/api/v1/market/tickers?symbol={sym}", timeout=8)
            tickers = (r.json().get("data") or {}).get("tickers") or []
            if tickers:
                t = tickers[0]
                close = float(t.get("close", 0))
                open_ = float(t.get("open", close))
                out[display] = {
                    "price": close,
                    "change24h": ((close - open_) / open_ * 100) if open_ else 0,
                }
        except Exception: pass
    return out


@st.cache_data(ttl=90, show_spinner=False)
def load_whale_positions() -> dict:
    """直接打 Hyperliquid 公開 API。"""
    positions = []
    for dex in ["", "xyz"]:
        try:
            body = {"type": "clearinghouseState", "user": WHALE_WALLET}
            if dex: body["dex"] = dex
            r = httpx.post("https://api.hyperliquid.xyz/info", json=body, timeout=10)
            d = r.json()
            for ap in d.get("assetPositions", []):
                p = ap.get("position", {})
                szi = float(p.get("szi", 0) or 0)
                if szi == 0: continue
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
            print(f"whale {dex}: {e}")
    return {
        "positions": positions,
        "count": len(positions),
        "total_value": sum(p["value"] for p in positions),
        "total_pnl": sum(p["pnl"] for p in positions),
    }


# ─── 工具 ────────────────────────────────────
def fmt_money(n, dp=2):
    if n is None: return "--"
    abs_n = abs(n)
    if abs_n >= 1e6: return f"${n/1e6:.2f}M"
    if abs_n >= 1e3: return f"${n/1e3:.1f}K"
    return f"${n:,.{dp}f}"


def chip(text, kind):
    return f'<span class="chip chip-{kind}">{text}</span>'


# ═══════════════════════════════════════════════
# 主畫面
# ═══════════════════════════════════════════════
try:
    st.title("⚡ QuantSignal")
    st.caption(f"我的系統整合儀表板 · {datetime.now(TZ_TW).strftime('%Y-%m-%d %H:%M')} 台北 · Mac mini + Cloud")

    snap = load_snapshot()

    if "_error" in snap:
        st.error(f"⚠️ 無法取得 Mac mini snapshot: {snap['_error']}")
        st.info(f"需要 Mac mini 端執行：`python streamlit_app/sync_snapshot.py`")
        st.stop()

    synced = snap.get("generated_at", "?")
    st.success(f"✅ 資料已同步 · Mac mini snapshot @ {synced}")

    # ───── 即時價格橫幅 ─────
    live = load_live_prices()
    if live:
        cols = st.columns(len(live))
        for i, (sym, info) in enumerate(live.items()):
            up = info["change24h"] >= 0
            cols[i].metric(
                label=sym.replace("USDT", ""),
                value=fmt_money(info["price"], 4 if info["price"] < 10 else 2),
                delta=f"{info['change24h']:+.2f}%",
            )
    st.markdown("---")

    # ───── 頂部總覽 4 欄 ─────
    pionex = snap.get("pionex", {})
    nba    = snap.get("nba", {})
    social = snap.get("social", {}).get("trackers", {})
    silver = snap.get("silver", {})

    sport = snap.get("sport_edge", {})

    c1, c2, c3, c4, c5 = st.columns(5)
    # Pionex
    longs  = sum(1 for b in pionex.get("bots", []) if b["direction"] == "LONG")
    shorts = sum(1 for b in pionex.get("bots", []) if b["direction"] == "SHORT")
    c1.metric("💎 Pionex", f"{pionex.get('count', 0)} bots", f"{longs}多 / {shorts}空")
    # NBA
    c2.metric("🏀 NBA", f"{len(nba.get('games', []))} 場", f"{nba.get('backtest', {}).get('all_wr', 0):.1f}% 勝率")
    # Social
    t_cnt = social.get("trump", {}).get("seen_count", 0)
    b_cnt = social.get("banini", {}).get("seen_count", 0)
    c3.metric("📰 社群", t_cnt + b_cnt, f"T{t_cnt} / B{b_cnt}")
    # Silver
    sh_prem = silver.get("shanghai_premium_pct")
    if silver.get("comex"):
        c4.metric("🥈 白銀 COMEX",
                  fmt_money(silver["comex"]),
                  f"上海溢價 {sh_prem:+.1f}%" if sh_prem is not None else None)
    else:
        c4.metric("🥈 白銀", "--", None)
    # Sport Edge
    sport_edges = sport.get("edges", [])
    positive_edges = [e for e in sport_edges if e.get("edge", 0) > 0]
    strong_edges = [e for e in sport_edges if e.get("edge", 0) >= 0.05]
    c5.metric(
        "🎯 運彩 Edge",
        f"{len(positive_edges)} 個",
        f"{len(strong_edges)} 個 >5%" if strong_edges else f"{len(sport.get('odds_games', []))} 場賠率",
    )

    # ───── Tabs ─────
    tab_py, tab_nba, tab_whale, tab_social, tab_silver, tab_sport, tab_strat = st.tabs([
        "💎 Pionex bots", "🏀 NBA 預測", "🐋 鯨魚持倉", "📰 社群追蹤",
        "🥈 白銀三市場", "🎯 運彩 Edge", "📊 策略績效"
    ])

    # === Pionex ===
    with tab_py:
        st.subheader("三刀流 9 Bots 即時狀態")
        cols = st.columns(3)
        for i, b in enumerate(pionex.get("bots", [])):
            with cols[i % 3]:
                kind = "long" if b["direction"] == "LONG" else ("short" if b["direction"] == "SHORT" else "hold")
                flips = f"↻{b['flips_today']}" if b.get("flips_today", 0) > 0 else ""
                price_dp = 4 if (b.get("last_price") or 0) < 10 else 2
                st.markdown(f"""
                <div class="bigcard">
                  <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="font-size:18px;font-weight:900">{b['bot']}</span>
                    {chip(b['direction'], kind)}
                  </div>
                  <div style="font-family:monospace;font-size:20px;color:#fff;margin-top:6px">
                    ${b.get('last_price', 0):,.{price_dp}f}
                  </div>
                  <div style="color:#88a8c8;font-size:11px;margin-top:4px">
                    {b.get('signal','')} <span style="color:#EAB308">{flips}</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)

    # === NBA ===
    with tab_nba:
        games = nba.get("games", [])
        bt = nba.get("backtest", {})
        st.markdown(f"**回測：** {bt.get('games_tested', 0)} 場 · 整體勝率 **{bt.get('all_wr', 0):.1f}%** · 強信號 **{bt.get('strong_wr', 0):.1f}%**")
        if not games:
            st.info("今日無比賽")
        else:
            for g in games:
                home_win = g.get("home_prob", 0) > g.get("away_prob", 0)
                spread = g.get("pred_spread", 0)
                total = g.get("pred_total", 0)

                col_a, col_vs, col_h, col_info = st.columns([2.5, 0.8, 2.5, 2])
                col_a.markdown(f"""
                <div style='text-align:right; {'color:#10B981;font-weight:700' if not home_win else 'color:#88a8c8'}'>
                  <div style='font-size:16px'>{g['away']}</div>
                  <div style='font-size:12px;color:#88a8c8'>{g.get('away_record','')}</div>
                  <div style='font-family:monospace;font-size:22px;font-weight:900'>{g.get('away_prob', 0):.0f}%</div>
                </div>""", unsafe_allow_html=True)
                col_vs.markdown("<div style='text-align:center;padding-top:24px;color:#EAB308;font-size:20px'>@</div>", unsafe_allow_html=True)
                col_h.markdown(f"""
                <div style='{'color:#10B981;font-weight:700' if home_win else 'color:#88a8c8'}'>
                  <div style='font-size:16px'>{g['home']}</div>
                  <div style='font-size:12px;color:#88a8c8'>{g.get('home_record','')}</div>
                  <div style='font-family:monospace;font-size:22px;font-weight:900'>{g.get('home_prob', 0):.0f}%</div>
                </div>""", unsafe_allow_html=True)
                col_info.markdown(f"""
                <div style='padding-top:12px;font-size:12px'>
                  <div>Spread <span style='color:#f59e0b;font-weight:700'>{spread:+.1f}</span></div>
                  <div>O/U <span style='color:#64b4ff;font-weight:700'>{total:.0f}</span></div>
                  <div style='color:#88a8c8;margin-top:4px'>{g.get('status','')}</div>
                </div>""", unsafe_allow_html=True)
                st.markdown("---")

        # Bracket compact
        bk = nba.get("playoff_bracket", {})
        if bk and not bk.get("error") and bk.get("west"):
            st.markdown("---")
            st.markdown("#### 🏆 季後賽版面")
            st.caption(f"Monte Carlo n={bk.get('n_sims', 0):,} · {(bk.get('generated_at','') or '').replace('T',' ')}")
            f = bk.get("finals", {})
            if f:
                fw, fe = f.get("west", {}), f.get("east", {})
                w_wins = (fw.get("advance_prob", 0) >= fe.get("advance_prob", 0))
                st.markdown(f"""
                <div style="text-align:center;border:2px solid #EAB308;border-radius:12px;padding:16px;
                     background:linear-gradient(135deg,rgba(234,179,8,.08),transparent);margin:8px 0;">
                  <div style="color:#EAB308;font-size:11px;letter-spacing:3px;font-weight:700;margin-bottom:10px;">★ TOTAL FINALS ★</div>
                  <div style="display:flex;justify-content:center;gap:40px;">
                    <div style="{'color:#10B981;font-weight:900' if w_wins else 'color:#88a8c8'}">
                      <div style="font-size:14px">🏆 WEST #{fw.get('seed','?')}</div>
                      <div style="font-size:28px;font-family:monospace;font-weight:900">{fw.get('abbrev','?')}</div>
                      <div style="font-size:18px;font-family:monospace">{fw.get('advance_prob',0):.1f}%</div>
                    </div>
                    <div style="color:#EAB308;font-size:20px;padding-top:22px">VS</div>
                    <div style="{'color:#10B981;font-weight:900' if not w_wins else 'color:#88a8c8'}">
                      <div style="font-size:14px">🏆 EAST #{fe.get('seed','?')}</div>
                      <div style="font-size:28px;font-family:monospace;font-weight:900">{fe.get('abbrev','?')}</div>
                      <div style="font-size:18px;font-family:monospace">{fe.get('advance_prob',0):.1f}%</div>
                    </div>
                  </div>
                  <div style="color:#88a8c8;font-size:11px;margin-top:8px;font-family:monospace">
                    Elo {fw.get('elo','?')} vs {fe.get('elo','?')} · 預期 {f.get('expected_games','?')} 場
                  </div>
                </div>""", unsafe_allow_html=True)

            # Conference Finals
            wcol, ecol = st.columns(2)
            for col, conf, label in [(wcol, bk["west"], "◤ 西區冠軍賽"), (ecol, bk["east"], "◢ 東區冠軍賽")]:
                with col:
                    for m in conf.get("conf_finals", []):
                        top, bot = m["top"], m["bot"]
                        tw = top["advance_prob"] >= bot["advance_prob"]
                        st.markdown(f"""
                        <div style="background:#121826;border:1px solid #1e293b;border-radius:8px;padding:10px;margin:4px 0;">
                          <div style="font-size:10px;color:#EAB308;font-weight:700;letter-spacing:2px;margin-bottom:6px">{label}</div>
                          <div style="{'color:#10B981;font-weight:700' if tw else 'color:#88a8c8'};font-size:13px">#{top['seed']} {top['abbrev']} <span style="font-family:monospace;float:right">{top['advance_prob']:.1f}%</span></div>
                          <div style="{'color:#10B981;font-weight:700' if not tw else 'color:#88a8c8'};font-size:13px">#{bot['seed']} {bot['abbrev']} <span style="font-family:monospace;float:right">{bot['advance_prob']:.1f}%</span></div>
                          <div style="font-size:9px;color:#64748b;margin-top:6px;font-family:monospace">Elo {top['elo']} vs {bot['elo']} · {m.get('expected_games','?')} 場</div>
                        </div>""", unsafe_allow_html=True)

            # R1 matchups as a compact grid
            with st.expander(f"展開首輪 & 準決賽（{len(bk['west']['r1'])+len(bk['east']['r1'])+len(bk['west']['r2'])+len(bk['east']['r2'])} 場）"):
                for round_label, round_key in [("R2 準決賽", "r2"), ("R1 首輪", "r1")]:
                    st.markdown(f"**{round_label}**")
                    wc, ec = st.columns(2)
                    for col, conf_data, conf_label in [(wc, bk["west"], "西"), (ec, bk["east"], "東")]:
                        with col:
                            for m in conf_data.get(round_key, []):
                                top, bot = m["top"], m["bot"]
                                tw = top["advance_prob"] >= bot["advance_prob"]
                                star_top = m["top"].get("star", {})
                                star_bot = m["bot"].get("star", {})
                                st_top = f'★ {star_top["name"]} ({star_top.get("status","Healthy")})' if star_top.get("name") else ""
                                st_bot = f'★ {star_bot["name"]} ({star_bot.get("status","Healthy")})' if star_bot.get("name") else ""
                                st.markdown(f"""
                                <div style="background:#121826;border:1px solid #1e293b;border-radius:6px;padding:8px;margin:3px 0;font-size:12px;">
                                  <div style="{'color:#10B981;font-weight:700' if tw else 'color:#88a8c8'}">#{top['seed']} {top['abbrev']} <span style="font-family:monospace;float:right">{top['advance_prob']:.1f}%</span></div>
                                  <div style="{'color:#10B981;font-weight:700' if not tw else 'color:#88a8c8'}">#{bot['seed']} {bot['abbrev']} <span style="font-family:monospace;float:right">{bot['advance_prob']:.1f}%</span></div>
                                  <div style="font-size:9px;color:#64748b;margin-top:4px;font-family:monospace">{m.get('expected_games','?')}場 · Elo {top['elo']} vs {bot['elo']}</div>
                                  <div style="font-size:9px;color:#94a3b8;margin-top:2px">{st_top}</div>
                                  <div style="font-size:9px;color:#94a3b8">{st_bot}</div>
                                </div>""", unsafe_allow_html=True)

    # === Whale ===
    with tab_whale:
        st.caption(f"錢包 `{WHALE_WALLET[:10]}...{WHALE_WALLET[-8:]}` · 即時 Hyperliquid API")
        whale = load_whale_positions()
        if not whale["positions"]:
            st.info("目前無持倉")
        else:
            wc1, wc2 = st.columns(2)
            wc1.metric("倉位總值", fmt_money(whale["total_value"]))
            pnl = whale["total_pnl"]
            wc2.metric("未實現盈虧", fmt_money(pnl), delta=f"{(pnl / whale['total_value'] * 100 if whale['total_value'] else 0):+.2f}%")
            st.markdown("---")
            for p in whale["positions"]:
                kind = "long" if p["side"] == "LONG" else "short"
                pnl_color = "#10B981" if p["pnl"] >= 0 else "#EF4444"
                dex_tag = f"<span style='background:#333;padding:2px 6px;border-radius:3px;font-size:10px;margin-left:6px'>{p['dex']}</span>" if p["dex"] != "main" else ""
                st.markdown(f"""
                <div class="bigcard">
                  <div style="display:flex;justify-content:space-between">
                    <div>
                      <span style="font-size:18px;font-weight:900">{p['coin']}</span>
                      {dex_tag}
                      {chip(f"{p['side']} {p['leverage']}x", kind)}
                    </div>
                    <div style="text-align:right">
                      <div style="font-family:monospace;font-size:18px;font-weight:900;color:{pnl_color}">
                        {'+' if p['pnl']>=0 else '-'}{fmt_money(abs(p['pnl']))}
                      </div>
                      <div style="font-size:12px;color:#88a8c8">{fmt_money(p['value'])}</div>
                    </div>
                  </div>
                  <div style="margin-top:8px;font-size:12px;color:#88a8c8">
                    數量 <b>{p['size']:,.0f}</b> · 入場 <b>${p['entry']:.4f}</b> · {p['leverage_type']}
                  </div>
                </div>
                """, unsafe_allow_html=True)

    # === Social ===
    with tab_social:
        c1, c2 = st.columns(2)
        for col, key, title, desc in [
            (c1, "trump", "🇺🇸 Trump Truth Social", "trumpstruth.org"),
            (c2, "banini", "🔮 巴逆逆 Threads", "@banini31"),
        ]:
            t = social.get(key, {})
            col.markdown(f"""
            <div class="bigcard">
              <div style="display:flex;justify-content:space-between">
                <b>{title}</b>
                <span style="color:#88a8c8;font-size:11px">{desc}</span>
              </div>
              <div style="font-size:36px;font-weight:900;color:#EAB308;margin-top:8px">{t.get('seen_count', 0)}</div>
              <div style="color:#88a8c8;font-size:12px">累計追蹤貼文數</div>
              <div style="color:#788;font-size:11px;margin-top:6px">最後: {t.get('last_run', '--')[:19]}</div>
            </div>
            """, unsafe_allow_html=True)
        st.caption("📬 推播到 JoSocialTracker Telegram 群組（每小時 :05 自動）")

    # === Silver ===
    with tab_silver:
        if silver.get("error") or not silver.get("comex"):
            st.warning(f"⚠️ 白銀資料：{silver.get('error', '無資料')}")
        else:
            s1, s2, s3 = st.columns(3)
            s1.metric("🇺🇸 COMEX 期貨", fmt_money(silver["comex"]))
            s2.metric("🇨🇳 上海期貨", fmt_money(silver["shanghai"]), f"¥{silver.get('shanghai_cny', 0):,.0f}")
            phys_warn = (silver.get("physical_days_old") or 0) >= 7
            s3.metric("🏪 實物 JM Bullion", fmt_money(silver["physical"]),
                      f"{silver.get('physical_days_old', 0)} 天前 ⚠️" if phys_warn else f"{silver.get('physical_days_old', 0)} 天前")

            st.markdown("---")
            a1, a2, a3 = st.columns(3)
            sh_p = silver.get("shanghai_premium_pct") or 0
            ph_p = silver.get("physical_premium_pct") or 0
            a1.metric("上海 vs COMEX", f"{sh_p:+.2f}%",
                      f"${silver.get('shanghai_premium_usd', 0):+.2f}/盎司")
            a2.metric("實物 vs COMEX", f"{ph_p:+.2f}%",
                      "實物低於期貨" if ph_p < 0 else "實物高於期貨")
            a3.metric("API 成功率", f"{silver.get('success_rate', 0):.1f}%")

            # 解讀
            st.markdown("### 💡 套利解讀")
            insights = []
            if sh_p > 10:
                insights.append(f"🔥 上海溢價 {sh_p:.1f}% 過高（>10%），短期可能修正")
            elif sh_p > 5:
                insights.append(f"⚠️ 上海溢價偏高（{sh_p:.1f}%）")
            else:
                insights.append(f"✅ 上海價差正常（{sh_p:.1f}%）")
            if ph_p < -3:
                insights.append(f"💰 實物折價 {abs(ph_p):.1f}%，實物交易者偏空")
            elif ph_p > 5:
                insights.append(f"🔥 實物溢價 {ph_p:.1f}%，囤積需求強")
            if phys_warn:
                insights.append(f"⚠️ 實物價格 {silver['physical_days_old']} 天沒更新")
            for ins in insights:
                st.markdown(f"- {ins}")

            st.caption(f"最後更新: {silver.get('timestamp', '--')} · silverTracker log")

    # === 運彩 Edge（sportWeb + autobots_NBA 比對）===
    with tab_sport:
        sport = snap.get("sport_edge", {})
        if sport.get("error") and not sport.get("odds_games"):
            st.warning(f"⚠️ 尚無資料：{sport['error']}")
            st.caption("sportWeb fetcher 每小時 :20 自動執行。可用：`launchctl start com.sportweb.fetcher`")
        else:
            edges = sport.get("edges", [])
            games = sport.get("odds_games", [])

            # 分類統計
            ml_edges = [e for e in edges if e.get("edge_type", "moneyline") == "moneyline" and e.get("edge", 0) > 0]
            sp_edges = [e for e in edges if e.get("edge_type") == "spread" and e.get("edge", 0) > 0]
            tt_edges = [e for e in edges if e.get("edge_type") == "total" and e.get("edge", 0) > 0]
            sc1, sc2, sc3, sc4 = st.columns(4)
            sc1.metric("可投注場次", len(games))
            sc2.metric("🎰 獨贏 Edge", len(ml_edges))
            sc3.metric("📐 讓分 Edge", len(sp_edges))
            sc4.metric("📊 大小 Edge", len(tt_edges))

            st.markdown("---")

            # Edge type icons / colors
            _type_icons = {"moneyline": "🎰", "spread": "📐", "total": "📊"}
            _type_labels = {"moneyline": "獨贏", "spread": "讓分", "total": "大小"}
            _side_colors = {"home": "#10B981", "away": "#EF4444", "over": "#60A5FA", "under": "#A78BFA"}

            # Edge 清單
            positive_edges = sorted(
                [e for e in edges if e.get("edge", 0) > 0],
                key=lambda x: x.get("edge", 0), reverse=True,
            )
            if not positive_edges:
                st.info("目前無邊際機會（模型跟市場看法一致）")
            else:
                st.subheader(f"🎯 偵測到 {len(positive_edges)} 個邊際機會")
                for i, e in enumerate(positive_edges[:12], 1):
                    edge_pct = e.get("edge", 0) * 100
                    roi_pct = e.get("expected_roi", 0) * 100
                    kelly_pct = e.get("kelly", 0) * 100
                    model_pct = e.get("model_prob", 0) * 100
                    market_pct = e.get("market_prob", 0) * 100
                    extreme = kelly_pct > 50
                    etype = e.get("edge_type", "moneyline")
                    eicon = _type_icons.get(etype, "🎰")
                    elabel = _type_labels.get(etype, "獨贏")

                    side = e.get("side", "")
                    side_color = _side_colors.get(side, "#10B981")
                    side_tag = side.upper()

                    line_info = ""
                    if etype == "spread":
                        line_val = e.get("line", 0)
                        line_info = f'<span style="color:#f59e0b;font-size:12px;margin-left:6px">線: {line_val}</span>'
                    elif etype == "total":
                        line_val = e.get("line", 0)
                        line_info = f'<span style="color:#60a5fa;font-size:12px;margin-left:6px">線: {line_val}</span>'

                    model_label = "模型覆蓋率" if etype == "spread" else ("模型 Over 率" if side == "over" else ("模型 Under 率" if side == "under" else "模型勝率"))

                    warn = '<span style="background:rgba(239,68,68,.3);color:#ff88aa;border:1px solid #EF4444;padding:2px 8px;border-radius:10px;font-size:11px;margin-left:6px">⚠ 極端</span>' if extreme else ''

                    type_badge = f'<span style="background:rgba(251,191,36,.15);color:#fbbf24;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:800;margin-left:6px">{eicon} {elabel}</span>'

                    st.markdown(f"""
                    <div class="bigcard" style="margin-bottom:10px">
                      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                        <div>
                          <span style="color:#88a8c8;font-size:12px">#{i}</span>
                          <span style="font-size:17px;font-weight:900;color:#fff;margin-left:8px">{e.get('picked_team', '')}</span>
                          <span style="background:{side_color}33;border:1px solid {side_color};color:{side_color};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:800;margin-left:6px">{side_tag}</span>
                          {type_badge}{line_info}{warn}
                        </div>
                        <div style="text-align:right">
                          <div style="font-family:monospace;font-size:20px;font-weight:900;color:#EAB308">+{edge_pct:.1f}%</div>
                          <div style="font-size:11px;color:#88a8c8">ROI {roi_pct:+.1f}%</div>
                        </div>
                      </div>
                      <div style="color:#aac0d6;font-size:13px;margin-bottom:8px">
                        {e.get('away', '')} @ {e.get('home', '')}
                      </div>
                      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;font-size:12px">
                        <div>
                          <div style="color:#88a8c8">{model_label}</div>
                          <div style="font-family:monospace;font-size:15px;font-weight:800;color:#10B981">{model_pct:.1f}%</div>
                        </div>
                        <div>
                          <div style="color:#88a8c8">市場隱含</div>
                          <div style="font-family:monospace;font-size:15px;font-weight:800;color:#EAB308">{market_pct:.1f}%</div>
                        </div>
                        <div>
                          <div style="color:#88a8c8">賠率 / Kelly</div>
                          <div style="font-family:monospace;font-size:15px;font-weight:800;color:#fff">{e.get('odds', 0):.2f} <span style="color:#88a8c8;font-size:11px">/ {kelly_pct:.1f}%</span></div>
                        </div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

            # 原始 odds (含讓分/大小)
            if games:
                st.markdown("---")
                st.subheader(f"📊 當前 odds ({len(games)} 場)")
                rows = []
                for g in games:
                    ml = g.get("moneyline") or {}
                    spreads = g.get("spreads") or []
                    totals = g.get("totals") or []
                    sp_str = " / ".join(f'{s.get("line","")}' for s in spreads) if spreads else "--"
                    tt_str = " / ".join(f'{t.get("line","")}' for t in totals) if totals else "--"
                    rows.append({
                        "比賽": f"{g.get('away', '')} @ {g.get('home', '')}",
                        "客勝": ml.get("away", "--"),
                        "主勝": ml.get("home", "--"),
                        "讓分線": sp_str,
                        "大小線": tt_str,
                    })
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            # 歷史回測績效
            bt = sport.get("backtest") or {}
            if bt.get("resolved", 0) > 0:
                st.markdown("---")
                st.subheader("📈 Edge 歷史回測")
                bc1, bc2, bc3, bc4 = st.columns(4)
                bc1.metric("已驗證", f"{bt['resolved']} 筆",
                           delta=f"共 {bt['total']} 筆")
                wr = bt.get("win_rate", 0)
                wr_color = "normal" if wr >= 50 else "inverse"
                bc2.metric("勝率", f"{wr:.1f}%",
                           delta=f"{bt.get('won',0)}W {bt.get('lost',0)}L",
                           delta_color=wr_color)
                tp = bt.get("total_profit", 0)
                bc3.metric("累計損益", f"${tp:+.2f}",
                           delta=f"每注 ROI {bt.get('avg_roi',0)*100:+.1f}%",
                           delta_color="normal" if tp >= 0 else "inverse")
                bc4.metric("待驗證", f"{bt['total'] - bt['resolved']} 筆")

                # 按類型
                by_type = bt.get("by_type", {})
                if by_type:
                    st.markdown("**按類型**")
                    type_icons = {"moneyline": "🎰 獨贏", "spread": "📐 讓分", "total": "📊 大小"}
                    type_cols = st.columns(len(by_type))
                    for col, (etype, stats) in zip(type_cols, by_type.items()):
                        with col:
                            lbl = type_icons.get(etype, etype)
                            w = stats.get("wins", 0)
                            n = stats.get("count", 0)
                            wr_val = stats.get("win_rate", 0)
                            pft = stats.get("total_profit", 0)
                            st.markdown(f"""
                            <div style="background:#121826;border:1px solid #1e293b;border-radius:8px;padding:12px;text-align:center">
                              <div style="font-size:11px;color:#88a8c8">{lbl}</div>
                              <div style="font-family:monospace;font-size:20px;font-weight:900;color:{'#10B981' if wr_val>=50 else '#EF4444'}">{wr_val:.0f}%</div>
                              <div style="font-size:11px;color:#88a8c8">{w}W/{n-w}L · ${pft:+.1f}</div>
                            </div>""", unsafe_allow_html=True)

                # Edge 大小分層
                by_bucket = bt.get("by_bucket", [])
                if by_bucket and any(b.get("count", 0) > 0 for b in by_bucket):
                    st.markdown("**Edge 大小 vs 實際勝率（模型校準）**")
                    bk_rows = []
                    for b in by_bucket:
                        if b["count"] == 0:
                            continue
                        bk_rows.append({
                            "Edge 區間": b["label"],
                            "筆數": b["count"],
                            "勝率": f"{b['win_rate']:.0f}%",
                            "損益": f"${b['profit']:+.1f}",
                        })
                    if bk_rows:
                        st.dataframe(pd.DataFrame(bk_rows), use_container_width=True, hide_index=True)

                # 校準曲線
                cal = bt.get("calibration", [])
                if cal and any(c.get("count", 0) > 0 for c in cal):
                    st.markdown("**模型信心 vs 實際勝率（校準檢驗）**")
                    cal_rows = []
                    for c in cal:
                        if c["count"] == 0:
                            continue
                        cal_rows.append({
                            "模型機率區間": c["label"],
                            "筆數": c["count"],
                            "平均模型機率": f"{c['avg_model_prob']:.0f}%",
                            "實際勝率": f"{c['actual_wr']:.0f}%",
                            "差距": f"{c['actual_wr'] - c['avg_model_prob']:+.0f}%",
                        })
                    if cal_rows:
                        st.dataframe(pd.DataFrame(cal_rows), use_container_width=True, hide_index=True)
                    st.caption("💡 差距接近 0% = 模型校準良好；正值 = 模型低估（保守）；負值 = 模型高估（過度自信）")

                # 最近已解析
                recent = bt.get("recent", [])
                if recent:
                    st.markdown("**最近已驗證 Edge**")
                    recent_rows = []
                    for r in recent[:10]:
                        symbol = "✅" if r["bet_won"] else "❌"
                        recent_rows.append({
                            "結果": symbol,
                            "類型": {"moneyline": "🎰", "spread": "📐", "total": "📊"}.get(r["edge_type"], "?"),
                            "推薦": r["picked_team"],
                            "Edge": f"+{r['edge_pct']:.1f}%",
                            "模型": f"{r['model_prob']:.0f}%",
                            "市場": f"{r['market_prob']:.0f}%",
                            "損益": f"${r['actual_profit']:+.2f}",
                        })
                    st.dataframe(pd.DataFrame(recent_rows), use_container_width=True, hide_index=True)
            elif bt.get("total", 0) > 0:
                st.markdown("---")
                st.info(f"📈 已累積 {bt['total']} 筆 edge 訊號，待比賽結束後自動驗證。")

            st.caption(f"🕐 fetched: {sport.get('fetched_at', '--')} · 來源：台灣運彩 /services/content/get (event-level)")
            st.caption("💡 Kelly > 50% 標記「極端」— 讓分σ=12pts · 大小σ=18pts · 實盤建議人工複查")

    # === 策略績效 ===
    with tab_strat:
        bundle = snap.get("strategies_bundle", {})
        strategies = (bundle.get("strategies") or {}).get("strategies", [])
        perf = bundle.get("strategies_performance", {})

        if not strategies:
            st.info("無策略資料")
        else:
            # 把 perf 攤平成 DataFrame
            rows = []
            for s in strategies:
                keys = [k for k in perf if k.startswith(s["id"] + "_")]
                for k in keys:
                    p = perf[k]
                    rows.append({
                        "策略": s["name"][:25],
                        "類別": s["category"],
                        "標的": k.replace(s["id"] + "_", ""),
                        "總報酬 %": p.get("totalReturn", 0),
                        "勝率 %": p.get("winRate", 0),
                        "獲利因子": p.get("profitFactor", 0),
                        "交易數": p.get("totalTrades", 0),
                    })
            if rows:
                df = pd.DataFrame(rows).sort_values("總報酬 %", ascending=False)
                st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.caption(f"資料來源：GitHub Release `{DATA_REPO}:{DATA_TAG}` + Pionex 公開 API + Hyperliquid 公開 API")
    st.caption("⏰ Snapshot 每小時由 Mac mini launchd 自動推送。頁面快取：價格 60s · 鯨魚 90s · snapshot 5 分鐘")

except Exception as e:
    st.error(f"App 錯誤：{e}")
    st.code(traceback.format_exc())
