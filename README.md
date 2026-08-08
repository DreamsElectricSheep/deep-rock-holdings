# Deep Rock Holdings — Algorithmic Hedge Fund Infrastructure

> **This is a public overview repo.** The trading system itself — signal logic, position sizing, risk parameters, the 100+ Python scripts that actually run lives in a private repository. What's here documents the architecture and approach; it is not the code. See *Repository Note* at the bottom for why.

An autonomous, multi-agent trading system running 24/7 on a home server. LLMs drive signal scoring, trade decisions, and natural-language reporting. Real capital is deployed across three exchanges — with human oversight mechanisms at every layer and no unattended exposure beyond defined risk limits.

Strategy, architecture, and every decision are the owner's; Claude Code wrote and iterated the code across ~150 sessions (more on the Opus/Sonnet split below). This public repo was created May 15, 2026 to share that architecture — the project itself has been running privately since mid-2025.

---

## Repository Snapshot

*Pulled directly from the private repo's git history — a dated snapshot, not a live counter, so treat the date as the freshness bound.*

| | |
|---|---|
| Snapshot taken | 2026-08-08 |
| Commits (git-tracked) | 214 |
| Commits, last 30 days | 32 |
| Development history | ongoing since mid-2025; detailed git tracking began in 2026 |
| Active bot/agent/scanner scripts | 104 |
| Tracked files (incl. timestamped `.bak` snapshots kept for audit trail) | 138 |

This project doesn't get "finished" and left alone — it gets audited. The Development Log below is the real change history, not a highlight reel; it includes the bugs found in the system's own governance layer, not just the wins.

---

---

## Development Log

*Recent sessions — vague by design; proprietary parameters and thresholds remain private.*

| Date | Work |
|------|------|
| 2026-08-07 | Fixed a partial-fill leak and orphan-position attribution bug in the execution/reporting path; hardened the autonomous board's retry behavior after a transient failure mode; closed a blind spot in the bot-liveness monitor itself. |
| 2026-08-01 (wk) | Repaired a long/short bot that had been silently dead on every scheduled run for weeks — every existing health check passed, because none of them verified the bot had actually traded, only that the process had run. |
| 2026-07-30 | Built a forward-return measurement layer that scores every research signal the fund has ever logged against real subsequent market data, with hard controls for signal clustering, directional sign, and benchmark choice — an uncontrolled first pass overstated statistical significance by roughly 6x before those controls were added. The controlled result overturned an internal assumption: the analytic long treated as the fund's sharpest edge tested as its *worst*-performing signal source; a quieter, less-discussed one tested best, though still short of the confidence bar the fund holds itself to. Separately, a flagship backtest's apparent edge turned out to be partly a survivorship-bias artifact — the historical stock universe used was missing a large share of the real index's constituents from the start of the test window. |
| 2026-07-29 | Full-fleet audit. One live-capital strategy had closed a string of trades without a single win, underperforming its own benchmark by a wide margin — its capital-arming trigger was paused rather than let it deploy further into that record. Root cause traced to policy, not stock-picking: a fixed-percentage stop-loss on a high-beta strategy mechanically manufactures its own stop-outs on ordinary sector-wide moves, and the same strategy's *unstopped*, still-open positions were meaningfully ahead of the same benchmark. Also shipped a bot-liveness monitor that, on its first run, immediately found two unrelated bots silently dead — one for nine days, one for six weeks — both invisible to every check that existed before it. |
| 2026-07-27 | Governance-layer audit: fixed a ghost position inflating the live-sizing denominator, added stricter reconciliation guards, and tightened the autonomous board's auto-apply path after tracing two earlier incidents where a board-authored change had silently deleted a live bot's entrypoint. |
| 2026-07-10 | Retired two strategies with no measurable edge after review; closed several stale broker positions left over from earlier bugs; hardened the self-healing layer again after it was found quietly reverting a deliberately-tuned parameter every morning. |
| 2026-07-04 | Post-change verification layer for the autonomous board; cohort-based performance review for the smart-money sleeve; community-evidence ingestion for the biotech scorer; scaffold triage; reporting accuracy fixes |
| 2026-07-03 | Built a benchmark-adjusted attribution layer so every strategy is now judged on excess return over its natural benchmark, not raw P&L — immediately separating genuine edge from market beta across the book. Stood up an on-demand regulatory-catalyst scoring tool for a capacity-constrained research niche, with the language model confined to evidence extraction and all scoring done deterministically. Ran a full system audit; reconciled account state after a funding transfer and hardened the self-healing layer against reverting deliberate decisions. |
| 2026-07-02 | Fund went live: first real equity capital deployed under the validated strategy via a deterministic live-mirror layer — the paper system continues unchanged as a control group. Live execution runs behind hard guardrails (account-sanity checks, order caps, kill switch, per-order alerting) with capital parked in T-bills until the next quarterly signal wave. |
| 2026-07-01 | Cost-optimized the autonomous board (weekly cadence; retired the advisory shadow panel after a statistically tied scoreboard); executed the board's capital-preservation order, moving all live crypto exposure to stablecoin; manually repaired two modules the automated auditor had damaged and added a post-audit import-verification rule; began live brokerage onboarding for the fund's validated strategy. |
| 2026-06-26 | Infrastructure hardening: weekly backup to OneDrive, dead scripts pruned, folder structure unified, autonomous board review running daily with git-committed auto-fixes. **Broker-truth reconciliation + position audit.** End-to-end read-only structural audit surfaced untracked broker positions accumulating outside the bot state layer (an in-memory-only tracking defect). Fixed at the source: a startup reconciliation pass now treats the broker as ground truth and re-hydrates any position the local state missed, and the entry gate deduplicates every new signal against both the in-memory book and the live broker book before sizing an order. Also diagnosed a portfolio-accounting artifact inflating a drawdown halt, and a recurring over-sell exit failure (selling a recorded quantity larger than the actual free balance). |
| Jun 2026 | **Institutional volatility-targeted position sizing.** Per-slot allocation replaced with a statistically rigorous realized-volatility method: 20-period log-return standard deviation annualized against a fixed volatility target, with hard dollar floors and ceilings to protect total deployed capital. Low-vol environments receive a larger allocation; high-vol environments are scaled back. Calculation reuses in-memory price data already fetched for signal generation — no additional API calls. |
| Jun 2026 | **Execution-layer fee optimization.** Crypto momentum execution rewritten from market orders to maker-side post-only limit orders with pending-order lifecycle tracking, fill resolution across scheduler cycles, and an automatic market-order override when protective stops breach while a passive exit is resting. Static slippage ceiling replaced with a volatility-adaptive bound; fixed per-slot allocation replaced with volatility-targeted position sizing within clamped bounds. Net effect: structural reduction in round-trip exchange fees with no added directional risk. |
| Jun 2026 | **Three-pillar governance audit + remediations + directional guard.** Read-only profitability/functionality/security audit of the live fleet; trading capital configuration aligned to actual exchange custody and unmanaged residue swept; retired strategies excluded from all reporting surfaces; a silent week-old syntax failure in the daily reporting layer found and repaired; the new relative-volume tracker validated against its first live market session, with an opening-auction guard added; a scheduler timezone assumption corrected across the cron layer. Direction-agnostic volume anomalies identified as an architectural risk class (elevated relative volume on a declining tape is distribution, not accumulation) — dual-metric directional confirmation guard added to the whale tracker and all downstream trade allocation paths. |
| Jun 2026 | **Intelligence Triad Migration.** Social layer rebuilt as resilient three-vector system after unauthenticated Reddit feed went permanently dark: X/Twitter cashtag scanning with rolling statistical velocity baselines; institutional RVOL anomaly tracking feeding deterministic position-sizing multipliers; StockTwits velocity scoring replacing binary platform checks. Each vector degrades gracefully. |
| Jun 2026 | **Board of Rivals adversarial audit.** 7 production mandates implemented and verified: LLMs demoted from voters to feature extractors, no-silent-fallback rule, Pydantic v2 validation firewall, fee-floor guardrails, blind self-healing prohibited, position reconciliation + orphan detection. |
| May 2026 | **X/Twitter authentication layer.** Full re-architecture of cookie management; HttpOnly constraint identified as architectural root cause of prior auth failures; paste-form workflow deployed for manual refresh. |
| May 2026 | **Whale Watcher + supervisor integration.** Pro-rated real-time RVOL tracking added; whale_confidence multiplier wired into Kelly sizing. Scan universe bug (always-empty dict) identified and fixed. |
| Apr 2026 | **Morning maintenance overhaul.** Daily self-healing scripts audited; parameter-override regression root-caused to cron conflict; tuned live trading values now protected from automatic resets. |
| Apr 2026 | **Multi-agent pipeline hardening.** Capital accounting bug fixed in supervisor (Kelly sizing was cosmetic — hardcoded value was actually executing). Trade sizes now correctly Kelly-derived end-to-end. |
| Mar 2026 | **13F Follower + earnings radar deployed.** 13F position copying with Kelly weighting; earnings proximity boost added to equity scoring pipeline. |

## Built with Claude Code

100+ scripts in this project were written by Claude Code across ~150+ iterative sessions. The owner directed the work — defining strategies, setting risk parameters, identifying what wasn't working, and making every capital allocation decision. Claude Code handled the implementation: Opus on the architecture and strategy design (the multi-agent pipeline, risk framework, Kelly sizing, the convergence gate), Sonnet on most of the day-to-day work — individual bots, signals, crontab, systemd services, the Postgres schema, Telegram reporting, the dashboard.

A key part of the owner's contribution was continuously identifying where manual processes could be automated and where existing workflows had gaps:

- Recognised that running bots across three exchanges with no unified risk layer was fragile — led to the multi-agent pipeline with a central risk manager and execution agent
- Identified that overnight Windows/Linux updates could disrupt live trading — designed the full overnight maintenance system (active hours, auto-login, startup notifications)
- Spotted that ad-hoc Telegram noise from 15+ scripts was making the signal-to-noise ratio unusable — systematically silenced non-critical alerts and redesigned morning/evening reports
- Noticed that idle capital sitting in SOL between trades was a missed opportunity — introduced Marinade liquid staking to put it to work
- Recognised that a single bad API response (Jupiter price feed) could corrupt displayed PnL — rerouted balance reads to the bot's own DB-written state
- Identified that paper bots graduating to live needed a formal gate — introduced the profitable-sessions canary system before full capital deployment
- Recognised that "the audit found N issues and fixed them" isn't trustworthy on its own — introduced a forward-return measurement layer so every research signal is scored against what the market actually did next, not against the story told about it afterward

The approach throughout was empirical — strategies were validated in paper mode before any real capital was committed, bots were iterated based on observed behaviour rather than assumptions, and each session started with live system evidence before any changes were made.

---

---

## AI & Agent Architecture

This is the core of the project — a five-agent pipeline where each agent has a distinct role, communicates through shared state (PostgreSQL + JSON), and the whole system runs without human intervention.

```
┌─────────────────────────────────────────────────────────────────┐
│              MULTI-AGENT DECISION PIPELINE (runs 2× daily)      │
└─────────────────────────────────────────────────────────────────┘

  Raw Signal Sources                  Processed Intelligence
  ──────────────────                  ──────────────────────
  X/Twitter cashtags                  ┌──────────────────────────────┐
  StockTwits · SEC EDGAR              │  data_ingestion_agent.py     │
  Firecrawl · Google Trends  ──────►  │  Aggregates all sources      │
  BTC order book · VIX                │  Deduplicates, normalises    │
                                      └──────────────┬───────────────┘
                                                     │
                                      ┌──────────────▼───────────────┐
                                      │  strategy_analyst.py         │
                                      │  Deterministic composite:    │
                                      │  trend template + validated  │
                                      │  LLM feature vectors +       │
                                      │  social + stream velocity    │
                                      │  (FOMO-penalised, gated)     │
                                      │  Crypto: confidence-weighted │
                                      └──────────────┬───────────────┘
                                                     │
                                      ┌──────────────▼───────────────┐
                                      │  risk_manager.py             │
                                      │  ATR position sizing         │
                                      │  Drawdown halt at −20%       │
                                      │  VIX regime gate             │
                                      └──────────────┬───────────────┘
                                                     │
                                      ┌──────────────▼───────────────┐
                                      │  supervisor.py               │
                                      │  Final execution gate        │
                                      │  Minervini 8/8 required      │
                                      │  Kelly position sizing       │
                                      │  Sector ETF rotation         │
                                      └──────────────┬───────────────┘
                                                     │
                                      ┌──────────────▼───────────────┐
                                      │  execution_agent.py          │
                                      │  Unified order router        │
                                      │  Coinbase · Jupiter · Alpaca │
                                      └──────────────────────────────┘
```

Sitting alongside this pipeline, not inside it, are three layers that don't touch execution directly but decide what's allowed to reach it: the **Guardian Layer** (kills or halts on hard triggers), the **Board** (a recurring automated audit that proposes and applies code-level changes, described below), and **Signal Measurement** (scores every research call against real forward returns so "this signal source is good" is a tested claim, not an assumption). All three exist because the pipeline above earning a trade decision is not the same thing as that decision being trustworthy.

### How LLMs Are Used

Gemini is embedded throughout the pipeline — not as a chatbot, but as a structured data-extraction engine. As of the June 2026 board mandate (see *The Board* below), no LLM output reaches execution math without passing a strict validation schema, and no LLM anywhere in the system holds trade-decision authority:

| Where | Model | What it does |
|-------|-------|-------------|
| `strategy_analyst.py` | — (no LLM call) | Consumes validated feature vectors from upstream extraction. Composite scoring is fully deterministic — no LLM votes exist in the execution path. |
| `SocialIntelligenceService.py` | Gemini 3.5 Flash Lite | Reads aggregated social data (X/Twitter + Trends + Firecrawl) and outputs BULLISH / BEARISH / NEUTRAL + impulse score for crypto sentiment. |
| `equity_screener.py` | Gemini 3.5 Flash Lite | Generates investment thesis for LONG_EXPLOSION and SHORT_COLLAPSE candidates from fundamental data. |
| `sec_watcher.py` | Gemini 3.5 Flash Lite | Reads SEC 8-K / 10-Q / 10-K filings and assigns an impact score (−10 to +10) with a plain-English summary. |
| `nwbo_tracker.py` / `fda_analyzer.py` | Gemini 3.5 Flash Lite | Reads catalyst-relevant filings and community evidence for a capacity-constrained biotech-catalyst niche; the LLM extracts evidence, a deterministic rubric scores it — the model never assigns the odds itself. |
| `data_ingestion_agent.py` | Gemini 3.5 Flash Lite | Extracts bounded, dimensionless feature vectors (narrative strength, priced-in probability, retail FOMO intensity, fundamental mention rate) from X/Twitter ticker discussion. |
| Oracle (OpenClaw) | Gemini 3.5 Flash | Interactive AI agent monitoring the entire fleet. Answers natural-language questions about portfolio state, bot health, and market regime via Telegram. |

### The Board — Adversarial Architecture Audit, Now a Recurring Process

In mid-2026 the owner convened an adversarial audit of the entire system: four AI personas with deliberately conflicting economic worldviews, operating under an **absolute unanimity constraint** — no mandate could issue unless all four agreed. The composition was chosen so that each member's blind spots are another member's specialty:

| Archetype | Analytical Lens | What It Hunts |
|-----------|----------------|---------------|
| **The Macro-Keynesian** | Central-bank liquidity regimes, regulatory compliance, systemic capital allocation | Compliance risk; threats to the capital-preservation sleeve |
| **The Austrian / Hard Money** | Counterparty vulnerability, asset custody, cash-drag, liquidity stress horizons | Hidden counterparty traps; idle capital decay |
| **The Quant / Complexity Theorist** | Mathematical validity, statistical overfitting boundaries, transactional friction, race-condition topology | Curve-fitted backtest illusions; protocol fragility |
| **The Behavioral Economist** | Market reflexivity, retail feedback loops, mania/panic cascades, operator fatigue | Automation bias; the system believing its own hype |

That one-time audit's core finding became the system's governing principle: **absolute containment of LLM autonomy**. What started as a single adversarial review is now a standing, weekly, automated process (`board_review.py`) — the board doesn't just recommend, it can author and auto-apply code changes directly, under the same unanimity constraint, with every change logged and git-committed.

That much authority on a recurring automated process has real failure modes, and this project doesn't hide them: on two separate occasions, a board-authored change silently deleted a live bot's entrypoint, taking it offline with no alert — caught weeks later, not immediately. The response wasn't to remove the board's authority, it was to make it accountable to the same evidence standard it applies to everything else: a post-change verification pass, an import-integrity check, and a retry/rollback path were added after the second incident, specifically so a change that breaks something is caught the same day, not weeks later.

The original mandates, all implemented and verified in production:

- **LLMs demoted from voters to feature extractors.** Gemini no longer outputs buy/sell opinions or confidence votes anywhere in the execution path. It extracts bounded, dimensionless features — narrative strength, probability the news is already priced in, retail FOMO intensity, fundamental mention rate — which feed deterministic, reproducible scoring formulas. Every trade score can be manually re-derived from logs.
- **No silent fallbacks.** If structured features are missing or malformed, the signal scores zero and a loud alert fires. The legacy path that fell back to raw LLM confidence was deliberately killed: a signal fails, the process survives, and a human finds out.
- **A validation firewall in front of the math.** Every LLM extraction passes through strict Pydantic v2 schema validation before touching execution logic — financial strings sanitised to numbers, categorical fields restricted to exact literals, all scores range-bounded. A hallucinated value raises a validation error and the signal is dropped, never traded.
- **Micro-timeframe strategies decommissioned.** Sub-15-minute bots were retired as friction-dominated noise with no institutional edge.
- **Fee-floor guardrails on live execution.** Entries are refused when the volatility-derived profit target cannot clear round-trip exchange fees with margin — paper environments with zero commissions had been flattering strategies that would lose money live.
- **"Blind self-healing" prohibited.** A daily maintenance script was discovered silently resetting a hand-tuned live trading parameter back to its old default every morning — masquerading for weeks as a mystery regression. Healer scripts may now repair corrupted state but never override tuned parameters.
- **Position reconciliation at every layer.** Bots reconcile their database state against actual exchange positions on startup, and a daily detector surfaces any exchange position no bot is tracking. Orphaned positions are escalated to a human — never auto-managed away.
- **Multi-vector intelligence migration.** When the system's unauthenticated Reddit feed went permanently dark (HTTP 403 across all subreddits), the social layer was rebuilt as a resilient triad: X/Twitter cashtag scanning with rolling statistical velocity baselines, institutional relative-volume (RVOL) anomaly tracking feeding deterministic position-sizing multipliers, and continuous social-stream velocity replacing binary platform checks. Each vector degrades gracefully — a dropped interface fails its signal, never the process.

A note on process: several of the board's own premises were **rejected on evidence** during implementation — proposed deletions that would have broken live components, capital figures that conflated bookkeeping with custody. Every mandate was verified against live system state before execution, which is itself the operating model: the adversarial layer proposes, the evidence disposes.

### Signal Measurement — Does This Source Actually Work?

The fleet runs a dozen-plus alt-data scanners and strategies, each one a plausible-sounding thesis on its own. The part that isn't obvious from a bot list is that every signal any of them produces gets logged and, months later, scored against what the market actually did afterward — with three controls applied on principle, not as an afterthought, because an uncontrolled first pass on the fund's own real signal history overstated its significance by roughly 6x:

- **Clustering** — the same idea re-flagged five times in three weeks is one observation, not five.
- **Direction** — a short call is scored on whether price *fell*; conflating long and short signals into one pooled statistic silently inverts half the evidence.
- **Benchmark choice** — small/mid-cap, high-beta signals need a high-beta benchmark, or a rising market alone manufactures the appearance of edge.

Run honestly, this kind of measurement doesn't just confirm what a system already believes about itself — it has already overturned one internal assumption about which strategy is actually the fund's best, in the *opposite* direction than expected. That result is the point: a fleet this size is only as trustworthy as its willingness to find out it's wrong.

### Autonomous Operation

The system is designed to run indefinitely without manual intervention — but autonomy is bounded, not unconditional. Hard limits exist at every layer: position sizing gates on VIX regime, drawdown halts block new entries at −20%, circuit breakers trigger on extreme sentiment, and a Telegram killswitch gives the owner immediate override at any time. The system reports on itself daily so a human always has a clear picture of what it's doing and why.

- **Market hours:** Bots execute, signals refresh, risk manager gates position sizing
- **3:00 AM:** Windows Update auto-installs patches; reboots only in the overnight window
- **3:30 AM:** `apt` updates Linux packages; Telegram summary sent
- **After any reboot:** Windows auto-logs in → WSL starts → systemd brings all services up → Telegram confirms fleet status within 45 seconds
- **Daily:** Morning brief at 8 AM UTC; PnL report at 8 PM UTC; all generated from live DB state

---

## Trading Bots

Organized by what they trade, not by how well they're doing — the fleet includes strategies that were tested and retired as much as ones still running. That's intentional; a strategy list with no retirements in it would mean nothing had ever really been checked.

### Live (Real Capital) or Recently Live

| Bot | File | Strategy | Venue |
|-----|------|----------|-------|
| DeFi Scalper | `sol_scalper.py` | RSI-14 mean reversion on SOL/USDC. Buys RSI < 25, sells RSI > 75 or −3% stop. Idle SOL auto-staked as mSOL via Marinade Finance. | Jupiter DEX (Solana) |
| Crypto Momentum | `crypto_momentum_bot.py` | EMA-33 trend following on ETH + SOL. Reads strategy signals and risk state. 2× ATR stop, 3× ATR target. | Coinbase Advanced Trade |
| Crypto Short Manager | `crypto_short_manager.py` | Manages short-side crypto exposure separately from the long-only momentum bot, under the same risk gates. | Coinbase Advanced Trade |
| Equity Trader | `equity_trader.py` | Reddit momentum signals scored by Gemini. Min 60% confidence, max 5 open positions. +10% TP / −5% SL. Guards against wash-trade rejections by checking for an opposing open order before entry. | Alpaca |
| 13F Follower / Live Mirror | `13f_follower.py`, `13f_live_mirror.py`, `13f_cohort_report.py` | Copies AI-infrastructure-focused hedge fund positions from SEC 13F filings, Kelly-weighted. A deterministic live-mirror layer gates whether the paper track record is strong enough to arm real capital — currently gated closed on its own evidence, with the paper system continuing as the control group regardless. | Alpaca (mirror) |
| Freedom family | `freedom_bot.py`, `freedom_equity_bot.py`, `freedom_fiat_bot.py` | A related family of momentum/breakout strategies (crypto, equity, and fiat-denominated variants) evaluated under the same promotion gate as everything else — not all of them clear it. | Mixed (crypto + equity) |

### Research / Paper Mode

| Bot | File | Strategy |
|-----|------|----------|
| Whisper Trader | `whisper_trader.py` | RSI(2) + Z-score mean reversion on S&P 500 large-caps (MCap > $2B, ADV > $50M). Entry: RSI(2) < 10 + Z-score < −2.0 + price > 200d SMA. Retired from live cron after review found no edge; kept as a measured historical data point, not deleted. |
| Sentiment Trader | `sentiment_trader.py` | X/Twitter-derived directional sentiment, sized small and logged to the signal-measurement layer from trade #1 — built specifically so this one doesn't run for months unmeasured the way its predecessor did. |
| ORB Imbalance | `orb_imbalance.py` | Opening Range Breakout with VWAP alignment, liquidity sweep detection, and dynamic ORB window sized from pre-market ATR. |
| Volatility Short | `volatility_short.py` | Short volatility when VIX ≥ 20 and term structure in backwardation (VIX > VIX3M). Skips CALM regime entirely. |
| Option Put Bot | `option_put_bot.py` | VRP harvesting: sell 2% OTM puts in CALM (VIX < 20); long puts in FEAR/PANIC. |
| Whale Watcher | `whale_watcher.py` | Unusual options flow + dark pool signals, with a directional-confirmation guard so a volume spike on a falling tape reads as distribution, not accumulation. |
| Path Signature Entries | `path_signature_entries.py` | Entry timing derived from path-signature (rough-path) feature transforms of recent price action. |
| Convex Hedge | `convex_hedge.py` | Convexity-seeking hedge overlay evaluated against the rest of the book. |
| Trend Rider / Bear Trap | `trend_rider.py`, `bear_trap.py` | Trend-continuation and false-breakdown-reversal strategies, currently paper-only pending owner authorization. |
| Ising Criticality Monitor | `ising_criticality_monitor.py`, `criticality_index.py` | Borrows a physics phase-transition model (Ising criticality) to flag when a market's internal correlation structure looks like it's approaching a regime change, independent of price level. |
| Pump.fun Recon | `pumpfun_recon.py` | Paper-only reconnaissance on new Solana memecoin launches, gated behind a strict promotion bar (minimum sample size + positive expectancy) before it's allowed anywhere near live capital. |
| Bottleneck Scanner | `bottleneck_scanner.py` | Screens AI-infrastructure supply-chain names for revenue/valuation bottleneck characteristics, anchored against a primary index name. |

---

## Signal Layer

Continuous intelligence feeds that all agents and bots read from:

| Module | Output | Cadence |
|--------|--------|---------|
| `SocialIntelligenceService.py` | Crypto sentiment: BULLISH / BEARISH / NEUTRAL + impulse score (Gemini-scored composite) | Daily |
| `x_scanner.py` | Cleaned X/Twitter directional sentiment — validates tickers against real equities, splits multi-ticker posts into per-ticker votes, dedupes by author before scoring | Daily |
| `OrderFlowIntelligence.py` | BTC order book bias — top-50 bids vs asks, normalised by circulating market cap | Every 15 min |
| `vix_regime.py` | CALM / CAUTION / FEAR / PANIC — gates position sizing across all bots, with hysteresis so it doesn't flap alerts at the regime boundary | Every 30 min |
| `spread_monitor.py` | ETH/BTC z-score vs 30-day rolling mean | Every 4 hr |
| `whisperer_bot.py` | Small-cap momentum: ticker mentions, Gemini-scored confidence + thesis | Daily |
| `equity_screener.py` | LONG_EXPLOSION / SHORT_COLLAPSE signals with Gemini thesis | Daily |
| `sec_watcher.py` | Material filing alerts with Gemini impact score (−10 to +10) | Daily + 4-hr |
| `earnings_radar.py` | +15% confidence boost for tickers with earnings within 5 days | Daily |
| `fda_analyzer.py` / `loa_model.py` | Deterministic-rubric approval-odds scoring for binary biotech catalysts; LLM extracts evidence, never assigns the odds | Event-driven |
| `biotech_catalyst_scanner.py`, `nwbo_tracker.py`, `sec_watcher.py` (biotech mode) | Community and filing evidence for a small set of individually-tracked biotech catalysts | Daily |
| `signal_ledger.py` | Not a live signal — the measurement layer that scores every signal above against real forward returns | Continuous |

---

## Risk & Guardian Layer

The system's ability to operate autonomously with real capital depends on these controls being trustworthy. They aren't an afterthought — they were designed in from the start, and most of the iteration across 150+ sessions has been in making them more reliable, not more permissive.

| Module | Trigger | Action |
|--------|---------|--------|
| `portfolio_circuit_breaker.py` | Social sentiment ≥ 85% BEARISH | Halts all bots for 12 hours |
| `risk_manager.py` | Portfolio drawdown ≥ −20% from peak | Sets `halt_active = True`, blocks all new entries |
| `PortfolioGuardian.py` | Individual position drawdown limits | Protective sells |
| `killswitch.py` | Telegram `/KILL` command | Emergency halt of entire fleet |
| `bot_heartbeat.py` | Content-hash comparison of each bot's evidence of work, not just process uptime or file mtime | Flags a bot as dead even if it's rewriting a file with fresh timestamps but identical, stale content |

---

## Passive Income & Network Nodes

Included for completeness, not as a highlight reel — this section is kept honest about which of these are actually earning anything right now.

| Node | Details |
|------|---------|
| Marinade mSOL | Idle SOL auto-staked via Jupiter when DeFi Scalper holds no position. Liquid unstake before any sell signal. Currently unfunded in practice — DeFi Scalper has been holding a position, so there's been no idle SOL to stake. |
| Avail Light Node | v1.13.3 — DA light-client on Avail mainnet, still running and healthy. Its incentive program appears to have been a time-limited campaign rather than an ongoing one, which likely explains the lack of rewards despite uptime — kept running for the data-availability contribution itself. |
| Allora Worker | Testnet inference worker — submits ETH / BTC / SOL price predictions to Allora topics 1, 3, 5. Went silently dead for 5 days after a testnet schema change broke the cached container image; fixed, and the restart policy corrected so a fatal exit no longer gets treated as a clean stop. |

---

## Reporting

All reports auto-generated from live database state and delivered via Telegram:

| Report | When | Content |
|--------|------|---------|
| Morning Brief | 8:00 AM UTC daily | PnL per bot + mid/micro-cap equity opportunities from overnight screening |
| Daily PnL | 8:00 PM UTC daily | Clean PnL numbers, live fleet totals |
| Hourly Snapshot | On new live trade | Fires only when a live bot executes — not on every cron cycle |
| Weekly PnL | Sundays 8:00 PM UTC | Week-over-week comparison, lifetime PnL per bot |
| Startup Alert | ~45s after any reboot | Boot time, uptime, ✅/❌ per service (dashboard / OpenClaw / Avail) |
| apt Update | After 3:30 AM cron | List of upgraded packages, reboot-required flag |

---

## Infrastructure

| Component | Details |
|-----------|---------|
| Host | Beelink SER5 Max — AMD Ryzen 7 6800U, 24 GB DDR5, 500 GB NVMe |
| OS | Windows 11 + WSL2 Ubuntu 22.04 (systemd enabled) |
| Scheduler | Linux cron in WSL2 |
| Database | PostgreSQL — bot state, trade history, signals, research |
| AI (scripts) | Gemini 3.5 Flash Lite (board audit pass runs Gemini 3.6 Flash) |
| AI (Oracle) | Gemini 3.5 Flash — interactive agent via Telegram |
| Monitoring | Live web dashboard (Flask) + Telegram alerts |
| Secrets | `~/.config/deeprock/secrets.json` — zero credentials in repo, and as of this update, zero hardcoded fallback credentials in this repo either (see *Repository Note*) |

---

## Directory Structure

```
scripts/
├── Pipeline Agents
│   ├── data_ingestion_agent.py
│   ├── strategy_analyst.py
│   ├── risk_manager.py
│   ├── supervisor.py
│   └── execution_agent.py
│
├── Trading Bots (live + paper, ~25 strategies)
│   ├── sol_scalper.py
│   ├── crypto_momentum_bot.py
│   ├── crypto_short_manager.py
│   ├── equity_trader.py
│   ├── freedom_bot.py / freedom_equity_bot.py / freedom_fiat_bot.py
│   ├── whisper_trader.py / sentiment_trader.py
│   ├── orb_imbalance.py
│   ├── volatility_short.py
│   ├── option_put_bot.py
│   ├── whale_watcher.py
│   └── 13f_follower.py / 13f_live_mirror.py
│
├── Signal Layer
│   ├── SocialIntelligenceService.py / x_scanner.py
│   ├── OrderFlowIntelligence.py
│   ├── vix_regime.py
│   ├── spread_monitor.py
│   ├── whisperer_bot.py
│   ├── equity_screener.py
│   ├── sec_watcher.py
│   ├── earnings_radar.py
│   └── nwbo_tracker.py / fda_analyzer.py / biotech_catalyst_scanner.py
│
├── Governance & Measurement
│   ├── board_review.py          # recurring adversarial audit, auto-applies findings
│   ├── bot_heartbeat.py         # content-hash liveness monitoring
│   ├── signal_ledger.py         # forward-return scoring of every signal
│   └── morning_healer.py / self_healer.py
│
├── Guardian Layer
│   ├── portfolio_circuit_breaker.py
│   ├── PortfolioGuardian.py
│   └── killswitch.py
│
└── README.md
```

*(This tree groups by function and omits per-file detail below the module level — see Repository Note.)*

---

---

## Repository Note

This repository contains the README and a curated selection of representative scripts chosen to illustrate architecture and engineering approach — deliberately, not as an oversight. The tables above name and describe every active module in the private fleet by function, cadence, and role in the pipeline; what they don't include is the code itself.

That line is drawn on purpose: the signal thresholds, position-sizing formulas, and the specific combination of features that make any one strategy profitable (or not) are the actual product of ~150+ sessions of iteration, and publishing them would let anyone reproduce or front-run the parts of this that took the longest to get right. Everything else — the failures, the incident write-ups, the governance mistakes, the measurement methodology — is public, because that's the part worth sharing and the part that doesn't cost anything to give away.

The complete codebase — 100+ Python scripts covering signal generation, strategy logic, multi-agent coordination, risk management, and trade execution — is maintained in a private repository. Proprietary signal parameters, strategy thresholds, and alpha-generating logic are not publicly available, and won't be.

---

*Deep Rock Holdings — Not investment advice.*
