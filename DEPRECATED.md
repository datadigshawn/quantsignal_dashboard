# DEPRECATED — Q-Signals 整合進 autobot_pionex 後封存

**狀態**：已封存（2026-05-06）

這個 repo 是 [q-signals-production.up.railway.app](https://q-signals-production.up.railway.app/) 的逆向重建版本（Flask + Streamlit Cloud 雙站）。已於 2026-05-01 整合進 [`autobot_pionex`](https://github.com/datadigshawn/autobot_pionex)、本 repo 不再維護。

## 替代位置

- **資料源**：`autobot_pionex/pionex-bot/qsignals/data/*.json`（strategies / strategies_performance / featured_signals_oil 等）
- **戰情室 QSignalsAgent** 已直接讀 autobot_pionex 路徑、不再讀本 repo
- **新公網站**（取代 Streamlit Cloud 版）：`qsignals.shawny-project42.com`（Mac mini + Cloudflare Tunnel、規劃中）

## 退役檢查清單

- [x] launchd `com.quantsignal.sync` bootout 2026-05-06
- [x] Streamlit Cloud 站點 `quantsignal-clone.streamlit.app` 停用（user 手動 2026-05-06）
- [x] 本機 `~/autobot/quantSignal_clone/` 移除
- [x] tarball 保留：`~/autobot/_archive/quantSignal_clone_2026-05-06.tar.gz`（110M、sha256 `fba7ed99395bc551ac9e591d5ee138b4cc11452c1ef111db800294e3898085c3`）
- [x] GitHub 仍保留（含此 commit）、不刪 remote
- ℹ️ Railway `q-signals-production.up.railway.app` 是**原版**（被 clone 對象），不是 user 部署的，無需下架

## 為什麼整合

`q-signals-production` 原站逆向重建後資料源不穩定（4/16 起 sync 開始失敗）。autobot_pionex 自己跑三刀流訊號、可作為更穩定的本機真資料源。重複維護兩個 repo 沒意義。

整合決策見 Obsidian `30_Investment/Projects/投資戰情室/_devlog/2026-05-01 autobot_pionex Q-Signals 整合.md`。
