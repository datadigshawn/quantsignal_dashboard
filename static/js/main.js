// ────────────────────────────────────────────────────────────
// QuantSignal Clone — 前端邏輯
// 負責載入所有 API 資料並渲染 UI
// ────────────────────────────────────────────────────────────

// 工具
const fmt = {
  price: (n, dp = 2) => (n == null ? "--" : Number(n).toLocaleString("en-US", { maximumFractionDigits: dp, minimumFractionDigits: dp })),
  pct:   (n) => (n == null ? "--" : (n >= 0 ? "+" : "") + Number(n).toFixed(2) + "%"),
  time:  (ms) => new Date(ms).toLocaleString("zh-TW", { timeZone: "Asia/Taipei" }),
};

const $ = (sel) => document.querySelector(sel);

// ────────────────────────────────────────────────────────────
// Health & Visitor
// ────────────────────────────────────────────────────────────
async function loadHealth() {
  try {
    const r = await fetch("/api/health");
    const d = await r.json();
    if (d.status === "ok") {
      $("#dbStatusDot").className = "w-2 h-2 rounded-full bg-green-500";
      $("#dbStatusText").textContent = `正常 · ${(d.uptime / 60).toFixed(0)} 分鐘`;
      $("#dbStatusText").className = "text-green-400";
    }
  } catch (e) {
    $("#dbStatusText").textContent = "離線";
    $("#dbStatusText").className = "text-red-400";
  }
}

async function loadVisitor() {
  try {
    const r = await fetch("/api/visitor-count");
    const d = await r.json();
    $("#visitorCount").textContent = `訪客 ${d.count.toLocaleString()}`;
  } catch (e) {}
}

// ────────────────────────────────────────────────────────────
// Price ticker
// ────────────────────────────────────────────────────────────
async function loadPrices() {
  try {
    const r = await fetch("/api/prices/current");
    const d = await r.json();
    const entries = Object.entries(d);
    if (entries.length === 0) return;

    // 雙份以實現無縫滾動
    const itemsHTML = entries.concat(entries).map(([sym, info]) => {
      const up = (info.change24h || 0) >= 0;
      const color = up ? "text-green-400" : "text-red-400";
      const arrow = up ? "▲" : "▼";
      return `
        <div class="flex items-center gap-2 text-sm">
          <span class="font-semibold">${sym.replace("USDT", "")}</span>
          <span>$${fmt.price(info.price, info.price < 10 ? 4 : 2)}</span>
          <span class="${color} text-xs">${arrow}${fmt.pct(info.change24h)}</span>
        </div>`;
    }).join("");
    $("#priceItems").innerHTML = itemsHTML;

    // 特別處理 CL 油價到主頁
    if (d.CLUSDT) {
      const up = d.CLUSDT.change24h >= 0;
      $("#oilPriceMain").textContent = `$${fmt.price(d.CLUSDT.price)}`;
      const chgEl = $("#oilChangeMain");
      chgEl.textContent = fmt.pct(d.CLUSDT.change24h);
      chgEl.className = `text-sm font-semibold ${up ? "text-green-400" : "text-red-400"}`;
    }
  } catch (e) {
    console.error("loadPrices:", e);
  }
}

// ────────────────────────────────────────────────────────────
// Manual Signals 人工精選總覽
// ────────────────────────────────────────────────────────────
async function loadManualSignals() {
  try {
    const r = await fetch("/api/manual-signals/performance");
    const d = await r.json();
    const roi = d.totalRoi || 0;
    const el = $("#manual-total-roi");
    el.textContent = (roi >= 0 ? "+" : "") + roi.toFixed(2) + "%";
    el.className = `text-2xl font-bold ${roi >= 0 ? "text-green-400" : "text-red-400"}`;
    $("#manual-closed-count").textContent = `${d.closedCount || 0} 筆已平倉`;
  } catch (e) {}
}

// ────────────────────────────────────────────────────────────
// 精選油價訊號
// ────────────────────────────────────────────────────────────
async function loadOilSignals() {
  try {
    const r = await fetch("/api/featured-signals/oil");
    const list = await r.json();
    if (!Array.isArray(list) || !list.length) {
      $("#oilFeaturedSignals").innerHTML = '<p class="text-gray-500 text-sm">目前無精選訊號</p>';
      return;
    }
    $("#oilFeaturedSignals").innerHTML = list.map(s => {
      const isLong = s.type === "LONG" || s.type === "BUY";
      const color = isLong ? "green" : "red";
      return `
        <div class="bg-background-dark rounded-lg p-3 border border-${color}-500/30">
          <div class="flex justify-between items-center mb-2">
            <span class="px-2 py-0.5 rounded text-xs font-bold bg-${color}-500/20 text-${color}-400">
              ${s.type}
            </span>
            <span class="text-xs text-gray-500">${s.strategy_id} · ${s.timeframe}</span>
          </div>
          <div class="grid grid-cols-3 gap-2 text-xs">
            <div><span class="text-gray-500">進場</span> $${fmt.price(s.entry_price)}</div>
            <div><span class="text-gray-500">ROI</span> <span class="text-${color}-400 font-semibold">${fmt.pct(s.roi)}</span></div>
            <div><span class="text-gray-500">總報酬</span> <span class="text-${color}-400 font-semibold">${fmt.pct(s.total_return)}</span></div>
          </div>
          <div class="text-xs text-gray-400 mt-2">勝率 ${s.win_rate?.toFixed(1) || "--"}% · ${s.comment || ""}</div>
        </div>`;
    }).join("");
  } catch (e) {
    console.error("loadOilSignals:", e);
  }
}

// ────────────────────────────────────────────────────────────
// 策略清單
// ────────────────────────────────────────────────────────────
let allStrategies = [];
let perfData = {};
let currentCat = "all";

async function loadStrategies() {
  try {
    const [r1, r2] = await Promise.all([
      fetch("/api/strategies").then(r => r.json()),
      fetch("/api/strategies/performance").then(r => r.json()),
    ]);
    allStrategies = r1.strategies || [];
    perfData = r2 || {};

    // 分類計數
    const counts = { all: allStrategies.length, Basic: 0, Premium: 0, Platinum: 0, Trend: 0 };
    allStrategies.forEach(s => {
      if (counts[s.category] !== undefined) counts[s.category]++;
    });
    Object.entries(counts).forEach(([k, v]) => {
      const el = document.getElementById(`count-${k}`);
      if (el) el.textContent = v;
    });

    renderStrategies();
  } catch (e) {
    console.error("loadStrategies:", e);
  }
}

function renderStrategies() {
  const q = ($("#strategySearch").value || "").toLowerCase();
  const list = allStrategies.filter(s => {
    const catOk = currentCat === "all" || s.category === currentCat;
    const searchOk = !q || s.name.toLowerCase().includes(q) || s.id.toLowerCase().includes(q);
    return catOk && searchOk && s.isVisible !== false;
  });

  const container = $("#strategyList");
  const noResult = $("#noSearchResults");

  if (!list.length) {
    container.innerHTML = "";
    noResult.classList.remove("hidden");
    return;
  }
  noResult.classList.add("hidden");

  container.innerHTML = list.map(s => {
    // 找這策略的最佳績效
    const keys = Object.keys(perfData).filter(k => k.startsWith(s.id + "_"));
    const best = keys.map(k => perfData[k])
                     .sort((a, b) => (b.totalReturn || 0) - (a.totalReturn || 0))[0];

    const catBadge = {
      Basic:    "bg-blue-500/20 text-blue-300 border-blue-500/40",
      Premium:  "bg-primary/20 text-primary border-primary/40",
      Platinum: "bg-purple-500/20 text-purple-300 border-purple-500/40",
      Trend:    "bg-green-500/20 text-green-300 border-green-500/40",
    }[s.category] || "bg-gray-500/20 text-gray-300 border-gray-500/40";

    let perfHTML = '<p class="text-xs text-gray-500 mt-2">無回測資料</p>';
    if (best) {
      const ret = best.totalReturn || 0;
      const color = ret >= 0 ? "text-green-400" : "text-red-400";
      perfHTML = `
        <div class="grid grid-cols-3 gap-2 mt-3 text-xs">
          <div>
            <div class="text-gray-500">總報酬</div>
            <div class="${color} font-bold">${fmt.pct(ret)}</div>
          </div>
          <div>
            <div class="text-gray-500">勝率</div>
            <div class="font-semibold">${(best.winRate || 0).toFixed(1)}%</div>
          </div>
          <div>
            <div class="text-gray-500">交易數</div>
            <div class="font-semibold">${best.totalTrades || 0}</div>
          </div>
        </div>`;
    }

    return `
      <div class="bg-card-dark rounded-xl border border-border-dark p-4 hover:border-primary/50 transition">
        <div class="flex justify-between items-start mb-2 gap-2">
          <h4 class="font-bold">${s.name}</h4>
          <span class="text-xs px-2 py-0.5 rounded border ${catBadge} whitespace-nowrap">${s.category}</span>
        </div>
        <p class="text-xs text-gray-400 line-clamp-2">${s.description || ""}</p>
        ${perfHTML}
      </div>`;
  }).join("");
}

// ══════════════════════════════════════════════════════
// MY SYSTEMS 整合區
// ══════════════════════════════════════════════════════

const fmtM = (n) => {
  if (n == null) return "--";
  const abs = Math.abs(n);
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `$${(n / 1e3).toFixed(1)}K`;
  return `$${n.toFixed(2)}`;
};

async function loadMySummary() {
  try {
    const d = await fetch("/api/my/summary").then(r => r.json());
    $("#sum-pionex-total").textContent = d.pionex?.total || "--";
    $("#sum-pionex-long").textContent = d.pionex?.longs || 0;
    $("#sum-pionex-short").textContent = d.pionex?.shorts || 0;
    $("#sum-nba-games").textContent = d.nba?.games_today || "--";
    $("#sum-nba-wr").textContent = (d.nba?.win_rate || 0).toFixed(1) + "%";
    const trumpCount = d.social?.trump_seen || 0;
    const baniniCount = d.social?.banini_seen || 0;
    $("#sum-social-total").textContent = trumpCount + baniniCount;
    $("#sum-social-trump").textContent = trumpCount;
    $("#sum-social-banini").textContent = baniniCount;
    // Silver
    if (d.silver && !d.silver.error) {
      $("#sum-silver-comex").textContent = "$" + fmt.price(d.silver.comex);
      const pct = d.silver.shanghai_premium_pct || 0;
      const el = $("#sum-silver-premium");
      el.textContent = (pct > 0 ? "+" : "") + pct.toFixed(1) + "%";
      el.className = pct > 10 ? "text-red-400 font-semibold" :
                     pct > 5  ? "text-orange-400 font-semibold" : "text-green-400 font-semibold";
    }
    $("#my-summary-time").textContent = "更新 " + new Date(d.generated_at).toLocaleTimeString("zh-TW");
  } catch (e) { console.error(e); }
}

async function loadWhaleSummary() {
  try {
    const d = await fetch("/api/my/whale").then(r => r.json());
    $("#sum-whale-value").textContent = fmtM(d.total_value);
    const pnlEl = $("#sum-whale-pnl");
    const pnl = d.total_pnl || 0;
    pnlEl.textContent = (pnl >= 0 ? "+" : "-") + fmtM(Math.abs(pnl));
    pnlEl.className = pnl >= 0 ? "text-green-400 ml-1" : "text-red-400 ml-1";
  } catch (e) { console.error(e); }
}

async function renderTabPionex() {
  const c = $("#my-tab-content");
  c.innerHTML = '<p class="text-gray-500 text-sm">載入中...</p>';
  try {
    const d = await fetch("/api/my/pionex").then(r => r.json());
    c.innerHTML = `
      <div class="grid grid-cols-1 md:grid-cols-3 gap-2">
        ${(d.bots || []).map(b => {
          const color = b.direction === "LONG" ? "green" : (b.direction === "SHORT" ? "red" : "gray");
          const flips = b.flips_today > 0 ? `<span class="text-orange-400 text-xs">↻ ${b.flips_today}</span>` : "";
          return `
            <div class="bg-card-dark rounded-lg border border-border-dark p-3">
              <div class="flex justify-between items-center mb-1">
                <span class="font-bold">${b.bot}</span>
                <span class="px-2 py-0.5 rounded text-xs bg-${color}-500/20 text-${color}-400 font-semibold">${b.direction}</span>
              </div>
              <div class="text-xs text-gray-400">$${fmt.price(b.last_price, 4)}</div>
              <div class="flex justify-between items-center mt-1">
                <span class="text-xs text-gray-500">${b.signal}</span>${flips}
              </div>
            </div>`;
        }).join("")}
      </div>`;
  } catch (e) { c.innerHTML = `<p class="text-red-400 text-sm">失敗: ${e}</p>`; }
}

function _bkBadgeCls(s) {
  const k = (s || "").toLowerCase();
  if (k === "healthy" || k === "active" || !k) return "bg-green-500/15 text-green-400";
  if (k === "out" || k.includes("season") || k.includes("reserve")) return "bg-red-500/15 text-red-400";
  return "bg-yellow-500/15 text-yellow-400";
}

function _bkMini(m, label) {
  const topWins = m.top.advance_prob >= m.bot.advance_prob;
  const topCls = topWins ? "text-green-400 font-bold" : "text-gray-500";
  const botCls = !topWins ? "text-green-400 font-bold" : "text-gray-500";
  const games = m.expected_games ? `${m.expected_games.toFixed(1)}場` : "";
  const playerRow = (t) => {
    if (!t.star?.name) return "";
    return `<div class="flex justify-between items-center text-[10px]"><span class="text-gray-400 truncate">★ ${t.star.name}</span><span class="${_bkBadgeCls(t.star.status)} px-1.5 rounded text-[9px] font-mono">${t.star.status||'Healthy'}</span></div>`;
  };
  return `
    <div class="bg-card-dark rounded border border-border-dark p-2">
      <div class="flex justify-between text-[10px] text-gray-500 mb-1 font-mono"><span>${label}</span><span>${games}</span></div>
      <div class="flex justify-between items-center text-xs ${topCls}"><span>#${m.top.seed||''} ${m.top.abbrev}</span><span class="font-mono">${m.top.advance_prob.toFixed(1)}%</span></div>
      <div class="flex justify-between items-center text-xs ${botCls} mt-0.5"><span>#${m.bot.seed||''} ${m.bot.abbrev}</span><span class="font-mono">${m.bot.advance_prob.toFixed(1)}%</span></div>
      <div class="mt-1 pt-1 border-t border-border-dark text-[10px] text-gray-500 font-mono">Elo ${m.top.elo} vs ${m.bot.elo}</div>
      ${playerRow(m.top)}${playerRow(m.bot)}
    </div>`;
}

function _bkFinalsMini(f) {
  const westWins = f.west.advance_prob >= f.east.advance_prob;
  const wCls = westWins ? "text-primary font-bold" : "text-gray-500";
  const eCls = !westWins ? "text-primary font-bold" : "text-gray-500";
  return `
    <div class="bg-gradient-to-br from-primary/10 to-transparent rounded border-2 border-primary/40 p-3 shadow-lg shadow-primary/10">
      <div class="text-center text-xs text-primary font-bold tracking-widest mb-2">★ TOTAL FINALS ★</div>
      <div class="flex justify-between items-center text-sm ${wCls}"><span>#${f.west.seed||''} ${f.west.abbrev} (W)</span><span class="font-mono">${f.west.advance_prob.toFixed(1)}%</span></div>
      <div class="flex justify-between items-center text-sm ${eCls} mt-0.5"><span>#${f.east.seed||''} ${f.east.abbrev} (E)</span><span class="font-mono">${f.east.advance_prob.toFixed(1)}%</span></div>
      <div class="mt-2 pt-2 border-t border-border-dark text-[10px] text-gray-500 font-mono text-center">Elo ${f.west.elo} vs ${f.east.elo} · ${f.expected_games?.toFixed(1)||'?'}場</div>
    </div>`;
}

function renderBracketCompact(bk) {
  if (!bk || bk.error || !bk.west) return "";
  const w = bk.west, e = bk.east, f = bk.finals;
  return `
    <div class="mt-4 pt-3 border-t border-border-dark">
      <div class="flex justify-between items-center mb-2">
        <h4 class="text-sm font-bold text-primary">🏆 季後賽版面 (Monte Carlo)</h4>
        <span class="text-[10px] text-gray-500 font-mono">n=${(bk.n_sims||0).toLocaleString()}</span>
      </div>
      <div class="grid grid-cols-3 gap-2 mb-3 text-xs">
        <div class="text-center text-yellow-400 font-bold tracking-wider">◤ 西區</div>
        <div class="text-center text-primary font-bold tracking-wider">FINALS</div>
        <div class="text-center text-blue-400 font-bold tracking-wider">東區 ◢</div>
      </div>
      <div class="grid grid-cols-3 gap-2 mb-3">
        <div>${w.conf_finals.map(m => _bkMini(m, '西區冠軍')).join("")}</div>
        <div>${_bkFinalsMini(f)}</div>
        <div>${e.conf_finals.map(m => _bkMini(m, '東區冠軍')).join("")}</div>
      </div>
      <details class="text-xs">
        <summary class="cursor-pointer text-gray-400 hover:text-primary">展開準決賽 & 首輪 (${w.r1.length + e.r1.length + w.r2.length + e.r2.length} 場對戰)</summary>
        <div class="mt-3 space-y-3">
          <div>
            <div class="text-[10px] text-gray-500 font-mono mb-1">R2 · 準決賽</div>
            <div class="grid grid-cols-2 gap-2">
              ${w.r2.map(m => _bkMini(m, '西區準決賽')).join("")}
              ${e.r2.map(m => _bkMini(m, '東區準決賽')).join("")}
            </div>
          </div>
          <div>
            <div class="text-[10px] text-gray-500 font-mono mb-1">R1 · 首輪</div>
            <div class="grid grid-cols-2 gap-2">
              ${w.r1.map(m => _bkMini(m, `#${m.top.seed} vs #${m.bot.seed}`)).join("")}
              ${e.r1.map(m => _bkMini(m, `#${m.top.seed} vs #${m.bot.seed}`)).join("")}
            </div>
          </div>
        </div>
      </details>
    </div>`;
}

async function renderTabNBA() {
  const c = $("#my-tab-content");
  c.innerHTML = '<p class="text-gray-500 text-sm">載入中...</p>';
  try {
    const d = await fetch("/api/my/nba").then(r => r.json());
    const games = d.games || [];
    const gamesHtml = !games.length
      ? '<p class="text-gray-500 text-sm">今日無比賽</p>'
      : `<div class="space-y-2">
        ${games.map(g => {
          const homeWin = g.home_prob > g.away_prob;
          return `
            <div class="bg-card-dark rounded-lg border border-border-dark p-3">
              <div class="grid grid-cols-7 items-center text-sm">
                <div class="col-span-3 text-right ${homeWin ? 'text-gray-500' : 'text-white font-bold'}">
                  ${g.away}<div class="text-xs text-gray-500">${g.away_record}</div>
                </div>
                <div class="text-center">
                  <div class="text-xs text-gray-400">${g.status || 'VS'}</div>
                  <div class="text-xs font-mono mt-1">${g.away_prob.toFixed(0)}% - ${g.home_prob.toFixed(0)}%</div>
                </div>
                <div class="col-span-3 text-left ${homeWin ? 'text-white font-bold' : 'text-gray-500'}">
                  ${g.home}<div class="text-xs text-gray-500">${g.home_record}</div>
                </div>
              </div>
              <div class="mt-2 flex gap-3 text-xs text-gray-400">
                <span>Spread: <span class="text-orange-400">${g.pred_spread?.toFixed(1)}</span></span>
                <span>O/U: <span class="text-blue-400">${g.pred_total?.toFixed(0)}</span></span>
              </div>
            </div>`;
        }).join("")}
      </div>
      <p class="text-xs text-gray-500 mt-3">回測勝率 ${d.backtest?.all_wr?.toFixed(1) || '--'}% (${d.backtest?.games_tested || 0} 場)</p>`;
    c.innerHTML = gamesHtml + renderBracketCompact(d.playoff_bracket);
  } catch (e) { c.innerHTML = `<p class="text-red-400 text-sm">失敗: ${e}</p>`; }
}

async function renderTabWhale() {
  const c = $("#my-tab-content");
  c.innerHTML = '<p class="text-gray-500 text-sm">載入 Hyperliquid 即時資料...</p>';
  try {
    const d = await fetch("/api/my/whale").then(r => r.json());
    if (!d.positions?.length) { c.innerHTML = '<p class="text-gray-500 text-sm">目前無持倉</p>'; return; }
    c.innerHTML = `
      <div class="text-xs text-gray-500 mb-2">錢包: <code class="text-gray-300">${d.wallet.slice(0,10)}...${d.wallet.slice(-8)}</code></div>
      <div class="space-y-2">
        ${d.positions.map(p => {
          const side = p.side === "LONG" ? "green" : "red";
          const pnlColor = p.pnl >= 0 ? "text-green-400" : "text-red-400";
          return `
            <div class="bg-card-dark rounded-lg border border-border-dark p-3">
              <div class="flex justify-between items-start mb-2">
                <div>
                  <span class="font-bold">${p.coin}</span>
                  ${p.dex !== "main" ? `<span class="ml-1 px-1.5 rounded bg-gray-700 text-xs">${p.dex}</span>` : ""}
                  <span class="ml-2 px-2 py-0.5 rounded text-xs bg-${side}-500/20 text-${side}-400 font-semibold">${p.side} ${p.leverage}x</span>
                </div>
                <div class="text-right">
                  <div class="${pnlColor} font-bold">${p.pnl >= 0 ? '+' : '-'}${fmtM(Math.abs(p.pnl))}</div>
                  <div class="text-xs text-gray-500">${fmtM(p.value)}</div>
                </div>
              </div>
              <div class="grid grid-cols-3 gap-2 text-xs">
                <div><span class="text-gray-500">數量</span> ${p.size.toLocaleString()}</div>
                <div><span class="text-gray-500">入場</span> $${p.entry.toFixed(4)}</div>
                <div><span class="text-gray-500">類型</span> ${p.leverage_type}</div>
              </div>
            </div>`;
        }).join("")}
      </div>`;
  } catch (e) { c.innerHTML = `<p class="text-red-400 text-sm">失敗: ${e}</p>`; }
}

async function renderTabSocial() {
  const c = $("#my-tab-content");
  c.innerHTML = '<p class="text-gray-500 text-sm">載入中...</p>';
  try {
    const d = await fetch("/api/my/social").then(r => r.json());
    const t = d.trackers || {};
    c.innerHTML = `
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div class="bg-card-dark rounded-lg border border-border-dark p-4">
          <div class="flex items-center justify-between mb-2">
            <h4 class="font-bold">🇺🇸 Trump Truth Social</h4>
            <span class="text-xs text-gray-500">trumpstruth.org</span>
          </div>
          <div class="text-3xl font-bold text-primary">${t.trump?.seen_count || 0}</div>
          <div class="text-xs text-gray-400 mt-1">累計追蹤貼文</div>
          <div class="text-xs text-gray-500 mt-2">最後: ${t.trump?.last_run ? new Date(t.trump.last_run).toLocaleString('zh-TW') : '--'}</div>
        </div>
        <div class="bg-card-dark rounded-lg border border-border-dark p-4">
          <div class="flex items-center justify-between mb-2">
            <h4 class="font-bold">🔮 巴逆逆 Threads</h4>
            <span class="text-xs text-gray-500">@banini31</span>
          </div>
          <div class="text-3xl font-bold text-primary">${t.banini?.seen_count || 0}</div>
          <div class="text-xs text-gray-400 mt-1">累計追蹤貼文</div>
          <div class="text-xs text-gray-500 mt-2">最後: ${t.banini?.last_run ? new Date(t.banini.last_run).toLocaleString('zh-TW') : '--'}</div>
        </div>
      </div>
      <p class="text-xs text-gray-500 mt-3">📬 推播到 JoSocialTracker Telegram 群組</p>`;
  } catch (e) { c.innerHTML = `<p class="text-red-400 text-sm">失敗: ${e}</p>`; }
}

async function renderTabSilver() {
  const c = $("#my-tab-content");
  c.innerHTML = '<p class="text-gray-500 text-sm">載入中 silverTracker log...</p>';
  try {
    const d = await fetch("/api/my/silver").then(r => r.json());
    if (d.error) { c.innerHTML = `<p class="text-red-400 text-sm">${d.error}</p>`; return; }

    const shPremPct = d.shanghai_premium_pct || 0;
    const physPremPct = d.physical_premium_pct || 0;
    const shUsd = d.shanghai_premium_usd || 0;
    const physWarn = d.physical_days_old >= 7;

    c.innerHTML = `
      <!-- 三大市場並排 -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <!-- COMEX -->
        <div class="bg-card-dark rounded-lg border border-border-dark p-4">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-2xl">🇺🇸</span>
            <div>
              <div class="font-bold">COMEX 期貨</div>
              <div class="text-xs text-gray-500">Yahoo Finance SIK26.CMX</div>
            </div>
          </div>
          <div class="text-3xl font-bold font-mono text-white">$${fmt.price(d.comex)}</div>
          <div class="text-xs text-gray-500 mt-1">美國期貨市場</div>
        </div>

        <!-- 上海 -->
        <div class="bg-card-dark rounded-lg border border-border-dark p-4">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-2xl">🇨🇳</span>
            <div>
              <div class="font-bold">上海期貨 (AGM)</div>
              <div class="text-xs text-gray-500">東方財富網</div>
            </div>
          </div>
          <div class="text-3xl font-bold font-mono text-white">$${fmt.price(d.shanghai)}</div>
          <div class="text-xs text-gray-500 mt-1">¥${fmt.price(d.shanghai_cny, 0)}</div>
        </div>

        <!-- 實物 -->
        <div class="bg-card-dark rounded-lg border ${physWarn ? 'border-orange-500/40' : 'border-border-dark'} p-4">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-2xl">🏪</span>
            <div>
              <div class="font-bold">實物白銀</div>
              <div class="text-xs text-gray-500">JM Bullion 1oz</div>
            </div>
          </div>
          <div class="text-3xl font-bold font-mono text-white">$${fmt.price(d.physical)}</div>
          <div class="text-xs mt-1 ${physWarn ? 'text-orange-400' : 'text-gray-500'}">
            ${d.physical_days_old != null ? `${d.physical_days_old} 天前更新` : ''}
            ${d.physical_last_updated ? `· ${d.physical_last_updated}` : ''}
          </div>
        </div>
      </div>

      <!-- 套利資訊 -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <div class="bg-gradient-to-br from-orange-500/10 to-transparent rounded-lg border border-orange-500/30 p-4">
          <div class="text-xs text-gray-400 mb-1">上海 vs COMEX 價差</div>
          <div class="text-2xl font-bold font-mono ${shPremPct > 0 ? 'text-orange-400' : 'text-green-400'}">
            ${shPremPct > 0 ? '+' : ''}${shPremPct.toFixed(2)}%
          </div>
          <div class="text-xs text-gray-500 mt-1">$${shUsd > 0 ? '+' : ''}${fmt.price(shUsd)}/盎司</div>
        </div>
        <div class="bg-gradient-to-br from-blue-500/10 to-transparent rounded-lg border border-blue-500/30 p-4">
          <div class="text-xs text-gray-400 mb-1">實物 vs COMEX 溢價</div>
          <div class="text-2xl font-bold font-mono ${physPremPct >= 0 ? 'text-blue-400' : 'text-gray-400'}">
            ${physPremPct >= 0 ? '+' : ''}${physPremPct.toFixed(2)}%
          </div>
          <div class="text-xs text-gray-500 mt-1">${physPremPct < 0 ? '實物低於期貨' : '實物高於期貨'}</div>
        </div>
        <div class="bg-gradient-to-br from-green-500/10 to-transparent rounded-lg border border-green-500/30 p-4">
          <div class="text-xs text-gray-400 mb-1">API 成功率</div>
          <div class="text-2xl font-bold font-mono text-green-400">${d.success_rate?.toFixed(1) || '--'}%</div>
          <div class="text-xs text-gray-500 mt-1">資料抓取穩定度</div>
        </div>
      </div>

      <!-- 套利解讀 -->
      <div class="bg-card-dark rounded-lg border border-border-dark p-4 mb-2 text-sm">
        <div class="flex items-center gap-2 mb-2 text-primary font-semibold">
          <span class="material-symbols-outlined text-base">lightbulb</span>
          套利解讀
        </div>
        <ul class="space-y-1 text-gray-300 text-xs">
          ${shPremPct > 10 ? `<li>🔥 上海溢價 ${shPremPct.toFixed(1)}% 過高（>10%），短期可能修正</li>` :
            shPremPct > 5 ? `<li>⚠️ 上海溢價偏高（${shPremPct.toFixed(1)}%），觀察持續性</li>` :
                           `<li>✅ 上海價差正常範圍（${shPremPct.toFixed(1)}%）</li>`}
          ${physPremPct < -3 ? `<li>💰 實物折價 ${Math.abs(physPremPct).toFixed(1)}%，實物交易者偏看空</li>` :
            physPremPct > 5 ? `<li>🔥 實物溢價 ${physPremPct.toFixed(1)}%，囤積需求強</li>` :
                              `<li>✅ 實物溢價正常（${physPremPct.toFixed(1)}%）</li>`}
          ${physWarn ? `<li class="text-orange-400">⚠️ 實物價格 ${d.physical_days_old} 天未手動更新（JM Bullion 需定期更新）</li>` : ''}
        </ul>
      </div>

      <p class="text-xs text-gray-500">最後更新: ${d.timestamp || '--'} · silverTracker 每 2 分鐘自動抓</p>`;
  } catch (e) { c.innerHTML = `<p class="text-red-400 text-sm">失敗: ${e}</p>`; }
}

async function renderTabSportEdge() {
  const c = $("#my-tab-content");
  c.innerHTML = '<p class="text-gray-500 text-sm">載入中 sportWeb + edge_detector...</p>';
  try {
    const d = await fetch("/api/my/sport_edge").then(r => r.json());
    if (d.error && !d.odds_games) {
      c.innerHTML = `
        <div class="bigcard" style="border-color:#EF4444">
          <b style="color:#EF4444">⚠️ 尚無資料</b>
          <p style="margin-top:8px;color:#88a8c8">${d.error}</p>
          <p style="margin-top:8px;color:#88a8c8;font-size:12px">
            sportWeb fetcher 排程每小時 :20 自動執行。<br>
            手動觸發：<code>launchctl start com.sportweb.fetcher</code>
          </p>
        </div>`;
      return;
    }

    const edges = d.edges || [];
    const games = d.odds_games || [];
    const ts = d.fetched_at || '';

    // Edges 區塊
    let edgesHtml = '';
    if (edges.length === 0) {
      edgesHtml = `<p class="text-gray-500 text-sm">目前無邊際機會（模型跟市場看法一致）</p>`;
    } else {
      edgesHtml = edges.slice(0, 5).map((e, i) => {
        const edgePct = (e.edge * 100).toFixed(1);
        const roiPct = (e.expected_roi * 100).toFixed(1);
        const kellyPct = (e.kelly * 100).toFixed(1);
        const modelPct = (e.model_prob * 100).toFixed(1);
        const marketPct = (e.market_prob * 100).toFixed(1);
        // 超高 Kelly (>50%) 算危險信號
        const extreme = e.kelly > 0.5;
        const warn = extreme ? '<span class="chip" style="background:rgba(239,68,68,.3);color:#ff88aa;border:1px solid #EF4444;margin-left:6px">⚠ 極端</span>' : '';
        return `
        <div class="bigcard" style="margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
            <div>
              <span style="font-size:13px;color:#88a8c8">#${i+1}</span>
              <span style="font-size:16px;font-weight:900;color:#fff;margin-left:8px">${e.picked_team}</span>
              <span class="px-2 py-0.5 rounded text-xs font-bold bg-${e.side === "home" ? "green" : "red"}-500/20 text-${e.side === "home" ? "green" : "red"}-400 ml-2">${e.side.toUpperCase()}</span>
              ${warn}
            </div>
            <div style="text-align:right">
              <div style="font-family:monospace;font-size:20px;font-weight:900;color:#EAB308">
                Edge +${edgePct}%
              </div>
              <div style="font-size:11px;color:#88a8c8">ROI ${roiPct}%</div>
            </div>
          </div>
          <div style="color:#aac0d6;font-size:13px;margin-bottom:8px">
            ${e.away} @ ${e.home}
          </div>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;font-size:12px">
            <div>
              <div style="color:#88a8c8">模型勝率</div>
              <div style="font-family:monospace;font-size:16px;font-weight:800;color:#10B981">${modelPct}%</div>
            </div>
            <div>
              <div style="color:#88a8c8">市場隱含</div>
              <div style="font-family:monospace;font-size:16px;font-weight:800;color:#EAB308">${marketPct}%</div>
            </div>
            <div>
              <div style="color:#88a8c8">賠率 / Kelly</div>
              <div style="font-family:monospace;font-size:16px;font-weight:800;color:#fff">
                ${e.odds} <span style="color:#88a8c8;font-size:12px">/ ${kellyPct}%</span>
              </div>
            </div>
          </div>
        </div>`;
      }).join("");
    }

    // Odds 原始資料
    let oddsHtml = games.map(g => {
      const ml = g.moneyline || {};
      return `
        <div style="display:flex;justify-content:space-between;padding:8px;border-bottom:1px solid #243324">
          <span style="color:#aac0d6">${g.away} @ ${g.home}</span>
          <span style="font-family:monospace;color:#fff">
            ${(ml.away || '--').toFixed ? ml.away.toFixed(2) : ml.away} / ${(ml.home || '--').toFixed ? ml.home.toFixed(2) : ml.home}
          </span>
        </div>`;
    }).join("");

    c.innerHTML = `
      <div style="color:#88a8c8;font-size:12px;margin-bottom:12px">
        🕐 fetched: ${ts} · 來源：台灣運彩 /services/content/get · fetcher launchd :20 / edge :35
      </div>

      <h4 style="color:#EAB308;font-size:16px;font-weight:800;margin-bottom:8px">
        🎯 偵測到 ${edges.length} 個邊際機會
      </h4>
      ${edgesHtml}

      <h4 style="color:#EAB308;font-size:16px;font-weight:800;margin-top:20px;margin-bottom:8px">
        📊 當前 odds (${games.length} 場比賽)
      </h4>
      <div class="bigcard" style="padding:8px">${oddsHtml || '<p style="color:#88a8c8;padding:8px">尚無資料</p>'}</div>

      <p style="color:#788;font-size:11px;margin-top:12px">
        💡 Kelly > 50% 標記「極端」— 實盤建議人工複查模型預測，避免過度下注
      </p>
    `;
  } catch (e) {
    c.innerHTML = `<p class="text-red-400 text-sm">載入失敗: ${e}</p>`;
  }
}

const MY_TAB_RENDERERS = {
  pionex: renderTabPionex, nba: renderTabNBA, whale: renderTabWhale,
  social: renderTabSocial, silver: renderTabSilver,
  sport_edge: renderTabSportEdge,
};

function bindMyTabs() {
  document.querySelectorAll(".my-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".my-tab").forEach(b => {
        b.classList.remove("bg-primary", "text-black", "font-semibold");
        b.classList.add("bg-card-dark", "border", "border-border-dark");
      });
      btn.classList.remove("bg-card-dark", "border", "border-border-dark");
      btn.classList.add("bg-primary", "text-black", "font-semibold");
      MY_TAB_RENDERERS[btn.dataset.tab]?.();
    });
  });
  renderTabPionex();
}

// 搜尋事件
document.addEventListener("DOMContentLoaded", () => {
  $("#strategySearch")?.addEventListener("input", renderStrategies);
  document.querySelectorAll(".cat-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      currentCat = btn.dataset.cat;
      document.querySelectorAll(".cat-btn").forEach(b => {
        b.classList.remove("bg-primary", "text-black", "font-semibold");
        b.classList.add("bg-card-dark", "border", "border-border-dark");
      });
      btn.classList.remove("bg-card-dark", "border", "border-border-dark");
      btn.classList.add("bg-primary", "text-black", "font-semibold");
      renderStrategies();
    });
  });

  // 啟動載入
  loadHealth();
  loadVisitor();
  loadPrices();
  loadOilSignals();
  loadManualSignals();
  loadStrategies();
  // MY SYSTEMS
  loadMySummary();
  loadWhaleSummary();
  bindMyTabs();

  // 自動刷新
  setInterval(loadPrices, 60000);
  setInterval(loadHealth, 30000);
  setInterval(loadMySummary, 60000);
  setInterval(loadWhaleSummary, 120000);
});
