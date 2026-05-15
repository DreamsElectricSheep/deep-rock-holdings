# Deep Rock Holdings — Algorithmic Hedge Fund Infrastructure

An autonomous, multi-agent trading system running 24/7 on a home server. LLMs drive signal scoring, trade decisions, and natural-language reporting. Real capital is deployed across three exchanges — with human oversight mechanisms at every layer and no unattended exposure beyond defined risk limits.

> Built over ~150 sessions — strategies, architecture, and direction by the owner; all code written by Claude Code (Opus for big-picture design, Sonnet for implementation).

> **Note:** This public repository was created May 15, 2026. The project has been running privately since mid 2025 — this repo was put together to share a curated overview of the architecture and approach. The full codebase remains in a private repository.

---

## Built with Claude Code

All 60+ scripts in this project were written by Claude Code across ~150 iterative sessions. The owner directed the work — defining strategies, setting risk parameters, identifying what wasn't working, and making every capital allocation decision. Claude Code handled the implementation.

A key part of the owner's contribution was continuously identifying where manual processes could be automated and where existing workflows had gaps:

- Recognised that running bots across three exchanges with no unified risk layer was fragile — led to the multi-agent pipeline with a central risk manager and execution agent
- Identified that overnight Windows/Linux updates could disrupt live trading — designed the full overnight maintenance system (active hours, auto-login, startup notifications)
- Spotted that ad-hoc Telegram noise from 15+ scripts was making the signal-to-noise ratio unusable — systematically silenced non-critical alerts and redesigned morning/evening reports
- Noticed that idle capital sitting in SOL between trades was a missed opportunity — introduced Marinade liquid staking to put it to work
- Recognised that a single bad API response (Jupiter price feed) could corrupt displayed PnL — rerouted balance reads to the bot's own DB-written state
- Identified that paper bots graduating to live needed a formal gate — introduced the profitable-sessions canary system before full capital deployment

| Model | Role | Examples |
|-------|------|---------|
| **Claude Opus** | Architecture, strategy design | Multi-agent pipeline, risk framework, Marinade mSOL staking, Allora worker node, Kelly sizing, convergence gate |
| **Claude Sonnet** | Bots, signals, infrastructure | Individual scripts, crontab, systemd services, PostgreSQL schema, Telegram reporting, dashboard, auto-update system |

The approach throughout was empirical — strategies were validated in paper mode before any real capital was committed, bots were iterated based on observed behaviour rather than assumptions, and each session started with live system evidence before any changes were made. This is a working example of the human-AI collaboration model: process thinking and product direction from the owner, engineering execution from Claude.

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
  Reddit · X/Twitter                  ┌──────────────────────────────┐
  StockTwits · SEC EDGAR              │  data_ingestion_agent.py     │
  Firecrawl · Google Trends  ──────►  │  Aggregates all sources      │
  BTC order book · VIX                │  Deduplicates, normalises    │
                                      └──────────────┬───────────────┘
                                                     │
                                      ┌──────────────▼───────────────┐
                                      │  strategy_analyst.py         │
                                      │  Gemini scores each ticker   │
                                      │  Composite: Minervini 40%    │
                                      │  + Gemini confidence 35%     │
                                      │  + social velocity 15%       │
                                      │  + StockTwits 10%            │
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

### How LLMs Are Used

Gemini is embedded throughout the pipeline — not as a chatbot, but as a scoring and reasoning engine:

| Where | Model | What it does |
|-------|-------|-------------|
| `strategy_analyst.py` | Gemini 3.1 Flash Lite | Scores each equity ticker with a confidence rating and investment thesis. One of four inputs to the composite score. |
| `SocialIntelligenceService.py` | Gemini 3.1 Flash Lite | Reads aggregated social data (Reddit + Trends + Firecrawl) and outputs BULLISH / BEARISH / NEUTRAL + impulse score for crypto sentiment. |
| `equity_screener.py` | Gemini 3.1 Flash Lite | Generates investment thesis for LONG_EXPLOSION and SHORT_COLLAPSE candidates from fundamental data. |
| `sec_watcher.py` | Gemini 3.1 Flash Lite | Reads SEC 8-K / 10-Q / 10-K filings and assigns an impact score (−10 to +10) with a plain-English summary. |
| `nwbo_tracker.py` | Gemini 3.1 Flash Lite | On any significant price move or filing, explains why it's moving, rates it BULLISH / BEARISH / NEUTRAL, and assesses key risks. |
| `data_ingestion_agent.py` | Gemini 3.1 Flash Lite | Batch-scores Reddit ticker mentions for confidence, momentum thesis, and signal quality. |
| Oracle (OpenClaw) | Gemini 3.1 Flash | Interactive AI agent monitoring the entire fleet. Answers natural-language questions about portfolio state, bot health, and market regime via Telegram. |

### Autonomous Operation

The system is designed to run indefinitely without manual intervention — but autonomy is bounded, not unconditional. Hard limits exist at every layer: position sizing gates on VIX regime, drawdown halts block new entries at −20%, circuit breakers trigger on extreme sentiment, and a Telegram killswitch gives the owner immediate override at any time. The system reports on itself daily so a human always has a clear picture of what it's doing and why.

- **Market hours:** Bots execute, signals refresh, risk manager gates position sizing
- **3:00 AM:** Windows Update auto-installs patches; reboots only in the overnight window
- **3:30 AM:** `apt` updates Linux packages; Telegram summary sent
- **After any reboot:** Windows auto-logs in → WSL starts → systemd brings all services up → Telegram confirms fleet status within 45 seconds
- **Daily:** Morning brief at 8 AM UTC; PnL report at 8 PM UTC; all generated from live DB state

---

## Trading Bots

### Live (Real Capital)

| Bot | File | Strategy | Venue |
|-----|------|----------|-------|
| DeFi Scalper | `sol_scalper.py` | RSI-14 mean reversion on SOL/USDC. Buys RSI < 25, sells RSI > 75 or −3% stop. Idle SOL auto-staked as mSOL via Marinade Finance (~6.5% APY). | Jupiter DEX (Solana) |
| Crypto Momentum | `crypto_momentum_bot.py` | EMA-33 trend following on ETH + SOL. Reads strategy signals and risk state. 2× ATR stop, 3× ATR target. | Coinbase Advanced Trade |
| Equity Trader | `equity_trader.py` | Reddit momentum signals scored by Gemini. Min 60% confidence, $75–$150/position, max 5 open. +10% TP / −5% SL. | Alpaca |

### Research / Paper Mode

| Bot | File | Strategy |
|-----|------|----------|
| Whisper Trader | `whisper_trader.py` | RSI(2) + Z-score mean reversion on S&P 500 large-caps (MCap > $2B, ADV > $50M). Entry: RSI(2) < 10 + Z-score < −2.0 + price > 200d SMA. |
| ORB Imbalance | `orb_imbalance.py` | Opening Range Breakout with VWAP alignment, liquidity sweep detection, and dynamic ORB window sized from pre-market ATR. |
| Volatility Short | `volatility_short.py` | Short volatility when VIX ≥ 20 and term structure in backwardation (VIX > VIX3M). Skips CALM regime entirely. |
| Option Put Bot | `option_put_bot.py` | VRP harvesting: sell 2% OTM puts in CALM (VIX < 20); long puts in FEAR/PANIC. |
| Whale Watcher | `whale_watcher.py` | Unusual options flow + dark pool signals from Unusual Whales. |
| 13F Follower | `13f_follower.py` | Copies AI-infrastructure focused hedge fund positions from SEC 13F filings. Kelly-weighted sizing. |

---

## Signal Layer

Continuous intelligence feeds that all agents and bots read from:

| Module | Output | Cadence |
|--------|--------|---------|
| `SocialIntelligenceService.py` | Crypto sentiment: BULLISH / BEARISH / NEUTRAL + impulse score (Gemini-scored 3-way composite) | Daily |
| `OrderFlowIntelligence.py` | BTC order book bias — top-50 bids vs asks, normalised by circulating market cap | Every 15 min |
| `vix_regime.py` | CALM / CAUTION / FEAR / PANIC — gates position sizing across all bots | Every 30 min |
| `spread_monitor.py` | ETH/BTC z-score vs 30-day rolling mean | Every 4 hr |
| `whisperer_bot.py` | Reddit small-cap momentum: ticker mentions, Gemini-scored confidence + thesis | Daily |
| `equity_screener.py` | LONG_EXPLOSION / SHORT_COLLAPSE signals with Gemini thesis | Daily |
| `sec_watcher.py` | Material filing alerts with Gemini impact score (−10 to +10) | Daily + 4-hr |
| `earnings_radar.py` | +15% confidence boost for tickers with earnings within 5 days | Daily |

---

## Risk & Guardian Layer

The system's ability to operate autonomously with real capital depends on these controls being trustworthy. They aren't an afterthought — they were designed in from the start, and most of the iteration across 150 sessions has been in making them more reliable, not more permissive.

| Module | Trigger | Action |
|--------|---------|--------|
| `portfolio_circuit_breaker.py` | Social sentiment ≥ 85% BEARISH | Halts all bots for 12 hours |
| `risk_manager.py` | Portfolio drawdown ≥ −20% from peak | Sets `halt_active = True`, blocks all new entries |
| `PortfolioGuardian.py` | Individual position drawdown limits | Protective sells |
| `killswitch.py` | Telegram `/KILL` command | Emergency halt of entire fleet |

---

## Passive Income & Network Nodes

| Node | Details |
|------|---------|
| Marinade mSOL | Idle SOL auto-staked via Jupiter when DeFi Scalper holds no position. Liquid unstake before any sell signal. ~6.5% APY. |
| Avail Light Node | v1.13.3 — DA light-client on Avail mainnet. Contributes to data availability sampling. |
| Allora Worker | Testnet inference worker — submits ETH / BTC / SOL price predictions to Allora topics 1, 3, 5. Two Docker containers: Flask inference server + allora-offchain-node. |

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
| AI (scripts) | Gemini 3.1 Flash Lite |
| AI (Oracle) | Gemini 3.1 Flash — interactive agent via Telegram |
| Monitoring | Live web dashboard (Flask) + Telegram alerts |
| Secrets | `~/.config/deeprock/secrets.json` — zero credentials in repo |

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
├── Trading Bots
│   ├── sol_scalper.py
│   ├── crypto_momentum_bot.py
│   ├── equity_trader.py
│   ├── whisper_trader.py
│   ├── orb_imbalance.py
│   ├── volatility_short.py
│   ├── option_put_bot.py
│   ├── whale_watcher.py
│   └── 13f_follower.py
│
├── Signal Layer
│   ├── SocialIntelligenceService.py
│   ├── OrderFlowIntelligence.py
│   ├── vix_regime.py
│   ├── spread_monitor.py
│   ├── whisperer_bot.py
│   ├── equity_screener.py
│   ├── sec_watcher.py
│   ├── earnings_radar.py
│   └── nwbo_tracker.py
│
├── Guardian Layer
│   ├── portfolio_circuit_breaker.py
│   ├── PortfolioGuardian.py
│   └── killswitch.py
│
└── README.md
```

---

---

## Repository Note

This repository contains the README and a curated selection of representative scripts chosen to illustrate architecture and engineering approach.

The complete codebase — 60+ Python scripts covering signal generation, strategy logic, multi-agent coordination, risk management, and trade execution — is maintained in a private repository. Proprietary signal parameters, strategy thresholds, and alpha-generating logic are not publicly available.

---

*Deep Rock Holdings — Not investment advice.*
