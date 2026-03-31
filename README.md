# CryptoGuardian

**Autonomous 24/7 cryptocurrency trading bot operating on Hyperliquid DEX with dual strategy engines.**

[![CI](https://github.com/Jotanune/CryptoGuardian/actions/workflows/ci.yml/badge.svg)](https://github.com/Jotanune/CryptoGuardian/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue)](https://www.python.org/)
[![Hyperliquid](https://img.shields.io/badge/Exchange-Hyperliquid%20DEX-purple)](https://hyperliquid.xyz/)
[![Tests](https://img.shields.io/badge/Tests-119%20passed-brightgreen)]()
[![Docker](https://img.shields.io/badge/Deploy-Docker-blue)](https://www.docker.com/)
[![Code Style](https://img.shields.io/badge/Code%20Style-Ruff-black)](https://github.com/astral-sh/ruff)
[![Type Check](https://img.shields.io/badge/Type%20Check-Mypy%20Strict-blue)](https://mypy-lang.org/)
[![Status](https://img.shields.io/badge/Status-Live%20(Paper)-yellow)]()

<!-- 
🎥 TODO: Record a 10-second GIF of the Rich dashboard running live.
   Run: python dashboard_demo.py
   Record with: asciinema rec demo.cast && agg demo.cast assets/dashboard.gif --theme monokai
   Then uncomment:
   ![Dashboard](assets/dashboard.gif)
-->

---

## Overview

CryptoGuardian is a fully autonomous crypto trading bot built from scratch in **Python 3.12+**. It runs two independent strategy engines simultaneously on **Hyperliquid DEX** (L1 perpetuals), with Kraken CEX used exclusively as a EUR liquidity bridge for profit extraction.

The entire system — from WebSocket data ingestion to EIP-712 order signing — is custom-built with zero reliance on trading frameworks.

### Key Numbers

| Metric | Value |
|--------|-------|
| **Python modules** | 52 |
| **Unit tests** | 119 (all passing) |
| **Strategy engines** | 2 (independent) |
| **Assets monitored** | 14 cryptocurrencies |
| **WebSocket subscriptions** | 29 real-time feeds |
| **Exchange integration** | Hyperliquid DEX + Kraken CEX + Arbitrum L2 |

---

## Strategy Engines

### Engine A — SMC Liquidity Sweeps

Detects institutional liquidity sweeps at Previous Day/Week High-Low levels on crypto perpetuals. Enters counter-direction on confirmed rejection with multi-timeframe trend filtering.

- **Assets**: BTC, ETH, SOL
- **Timeframe**: 4H primary (SOL uses multi-timeframe 15m signals + 4H trend)
- **Validation**: Walk-Forward tested across 2 years with out-of-sample confirmation

### Engine B — Statistical Pairs Trading

Cointegration-based pairs trading using Engle-Granger methodology. Entries/exits driven by z-score of the spread with dynamic hedge ratio recalculation.

- **Pairs**: 12 cointegrated pairs discovered from scanning 2,400+ combinations
- **Kill switch**: Automatic position closure if cointegration breaks (p-value threshold)
- **Selection**: Automated scanner with ADF test + Hurst exponent + half-life filtering

> Strategy parameters, thresholds, and exact entry/exit logic are proprietary and not included in this repository.

---

## Architecture

```
CryptoGuardian
│
├── Data Layer ───────────── Real-Time Market Data
│   ├── WebSocket Client        Hyperliquid WS with auto-reconnect (exponential backoff)
│   ├── Order Book Processor    L2 depth: bid/ask/spread/imbalance/VWAP
│   ├── Candle Builder          OHLCV from raw trades, multi-timeframe, outlier rejection
│   ├── Data Cache              Mid prices, candle history, REST backfill, garbage collection
│   └── RPC Client              Arbitrum on-chain balance verification (USDC/ETH)
│
├── Strategy Layer ───────── Dual Engine Signal Generation
│   ├── SMC Engine              Liquidity sweeps + rejection + regime filter
│   ├── Pairs Engine            Cointegration + z-score + funding tie-breaker
│   ├── Indicators              10 vectorized indicators (ATR, EMA, RSI, Bollinger, etc.)
│   └── Microstructure          OBI, TFI, trade velocity, spread dynamics, ML features
│
├── Execution Layer ──────── Smart Order Routing
│   ├── Hyperliquid Client      Full DEX client (EIP-712 signing, REST + WS, CRUD)
│   ├── Fee Optimizer           ML-based maker/taker decision (XGBoost fill predictor)
│   ├── Algo Router             Size-based routing to execution algorithms
│   ├── Iceberg Algorithm       Hidden large orders in randomized chunks (maker)
│   ├── TWAP Algorithm          Time-weighted slicing with jitter
│   ├── Order Manager           Lifecycle management + pairs atomic execution
│   └── Kraken Bridge           EUR extraction pipeline (HMAC-SHA512, Spot only)
│
├── Risk Layer ───────────── Capital Preservation
│   ├── Risk Manager            Daily limits, drawdown tracking, position sizing
│   ├── Circuit Breaker         Auto-pause after consecutive losses
│   ├── DD Scaling              Dynamic risk reduction approaching limits
│   └── Kill Switch             Emergency shutdown with retry + Telegram alert
│
├── Position Layer ───────── Active Trade Management
│   ├── Position Tracker        Full lifecycle state tracking per position
│   └── Position Manager        Break-even, trailing stop, partial TP, edge decay
│
├── Portfolio Layer ──────── Capital Management
│   ├── Auto-Compounder         Balance-based sizing with anti-DD freeze
│   ├── Dynamic Allocation      Rolling Sharpe → 5-tier risk multipliers + heat cap
│   └── EUR Bridge              Automated monthly profit extraction pipeline
│
├── Monitor Layer ────────── Observability
│   ├── Rich Dashboard          Terminal UI (positions, equity, P/L, status)
│   ├── Telegram Bot            Alerts + 6 interactive commands
│   └── Health Checker          NTP drift detection, HTTP /health endpoint
│
├── Persistence Layer ────── State & Analytics
│   ├── Database                SQLAlchemy async (trades, snapshots, state, alerts)
│   ├── Trade Journal           Daily/monthly stats, CSV export
│   └── State Manager           Periodic save/restore with checksum integrity
│
└── Infrastructure ───────── Deployment
    ├── Docker                  python:3.12-slim, non-root, healthcheck
    ├── systemd                 Auto-restart service
    └── VPS                     Ubuntu 24.04 LTS
```

---

## Backtest Results

### Engine A — SMC Liquidity Sweeps (2 years, 4H, 3 assets)

| Metric | Portfolio |
|--------|-----------|
| **Avg Return** | **+74.3%** |
| **Profit Factor** | 1.36 |
| **Win Rate** | 47.9% |
| **Total Trades** | 140 |

**Walk-Forward Validation** (Out-of-Sample):

| Split | Result |
|-------|--------|
| 60/40 | ✅ All 3 assets positive OOS |
| 70/30 | ✅ All 3 assets positive OOS |

**Temporal Consistency**: All 3 assets profitable in both 2024 and 2025 independently.

### Engine B — Pairs Trading (12 cointegrated pairs)

| Metric | Best Pairs |
|--------|-----------|
| **Returns** | +120% to +380% (top pairs, full sample) |
| **Win Rate** | 59% – 94% |
| **Profit Factor** | 2.0 – 33.5 |

> All results include 0.035% taker fees + 1 bps slippage simulation. Past performance does not guarantee future results.

---

## Execution Intelligence

The execution layer goes beyond simple market orders:

1. **ML Fill Predictor** — XGBoost model predicts maker fill probability based on microstructure features (order book imbalance, spread, trade velocity, book depth ratio)
2. **Smart Fee Optimization** — Maker orders preferred (0.00% fee) vs taker (0.035%), with ML-driven decision
3. **Algorithmic Execution** — Large orders routed through Iceberg (hidden chunks) or TWAP (time-weighted slicing)
4. **Anti-legging Protection** — Pairs trades executed atomically; if one leg fails, the other is immediately unwound

---

## Risk Management

| Protection | Description |
|-----------|-------------|
| **Daily Soft Stop** | Blocks new trades, manages existing positions |
| **Daily Hard Stop** | Emergency close of all positions |
| **Total DD Kill Switch** | Full shutdown with manual-only reset |
| **DD Scaling** | Automatic risk reduction approaching limits |
| **Circuit Breaker** | Auto-pause after consecutive losses |
| **Max Portfolio Heat** | Total open risk limit across all positions |
| **Correlation Limit** | Max positions per underlying asset |
| **Anti-DD Freeze** | Compounding paused during drawdown |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Language** | Python 3.12+ |
| **Async Runtime** | asyncio + uvloop |
| **DEX Integration** | Hyperliquid SDK + custom EIP-712 signing |
| **CEX Bridge** | Kraken REST (HMAC-SHA512) |
| **Blockchain** | web3.py (Arbitrum L2 balance verification) |
| **ML** | XGBoost + scikit-learn (fill prediction) |
| **Data** | pandas + numpy + numba (JIT-compiled backtests) |
| **Statistics** | scipy + statsmodels (cointegration, ADF tests) |
| **Database** | SQLAlchemy async (trades, state, snapshots) |
| **Config** | Pydantic Settings + TOML |
| **Monitoring** | Rich (terminal dashboard) + python-telegram-bot |
| **Logging** | Loguru (structured JSON, secret redaction, rotation) |
| **Deployment** | Docker + systemd + Ubuntu 24.04 VPS |
| **Testing** | pytest + pytest-asyncio + hypothesis |
| **Linting** | ruff + mypy |

---

## Pair Discovery Pipeline

The pairs trading engine includes an automated cointegration scanner:

1. **Download** OHLCV data for 70+ Hyperliquid-listed perpetuals
2. **Scan** all 2,400+ pair combinations for cointegration (ADF test)
3. **Filter** by half-life (mean reversion speed) and Hurst exponent
4. **Optimize** entry/exit parameters via grid search
5. **Validate** with Walk-Forward (60/40 + 70/30 splits)
6. **Rank** by out-of-sample Sharpe ratio and profit factor

From 2,400+ combinations → 612 viable → **12 selected for live trading**.

---

## Deployment

```
Ubuntu 24.04 VPS (OVH)
├── Docker container     python:3.12-slim, non-root user
├── systemd service      Auto-restart with health checks
├── SQLite database      Trade journal + state persistence
├── Loguru logs          JSON structured, rotated, secrets redacted
├── Telegram bot         Real-time alerts + interactive commands
└── HTTP /health         Endpoint for external monitoring
```

---

## Testing

- **119 unit tests** covering all core modules
- **Position sizing**: 30 tests (sizing, drawdown limits, compounding)
- **SMC sweeps**: 20 tests (detection, rejection, trend filtering)
- **Trailing stop**: 13 tests (trailing, break-even, partial TP)
- **Dynamic allocation**: 22 tests (DPA bands, Sharpe, heat cap)
- **Async execution**: Algorithm routing, atomic pairs execution

```
$ pytest --tb=short
========================= 119 passed in 4.2s =========================
```

See full breakdown: [`tests/test_output.md`](tests/test_output.md)

---

## Code Samples

This repository includes **sanitized excerpts** from the production codebase. No strategy logic or parameters are exposed.

### [`showcase/`](showcase/) — Core Infrastructure

| File | What it demonstrates |
|------|---------------------|
| [`websocket_client.py`](showcase/websocket_client.py) | Async WebSocket with exponential backoff, channel dispatch, auto-reconnect |
| [`risk_manager.py`](showcase/risk_manager.py) | 8 pre-trade risk gates, drawdown monitoring, circuit breaker, position sizing |
| [`kill_switch.py`](showcase/kill_switch.py) | Emergency shutdown with retry logic, position closure, Telegram alerts |
| [`async_utils.py`](showcase/async_utils.py) | Generic retry with backoff, async component lifecycle management |
| [`dashboard.py`](showcase/dashboard.py) | Rich terminal UI with live-refreshing positions, P/L, system status |

### [`examples/`](examples/) — Data Engineering

| File | What it demonstrates |
|------|---------------------|
| [`download_data.py`](examples/download_data.py) | Paginated OHLCV download from Hyperliquid/Binance → Parquet (handles API limits) |

### [`research/`](research/) — Statistical Analysis

| File | What it demonstrates |
|------|---------------------|
| [`cointegration_analysis.ipynb`](research/cointegration_analysis.ipynb) | ADF test, Hurst exponent, Engle-Granger cointegration, z-score visualization |

### [`logs/`](logs/) — Production Evidence

| File | What it shows |
|------|--------------|
| [`sample_production.log`](logs/sample_production.log) | 5-minute extract of the live bot: bootstrap → WS connect → tick processing → signal evaluation → order execution |

### DevOps

| File | Description |
|------|-------------|
| [`Dockerfile`](Dockerfile) | Multi-stage build, non-root user, healthcheck |
| [`docker-compose.yml`](docker-compose.yml) | Production deployment with memory limits, .env secrets |
| [`.env.example`](.env.example) | All required environment variables (no real values) |
| [`.github/workflows/ci.yml`](.github/workflows/ci.yml) | Ruff lint + Mypy strict + 119 tests + security scan + Docker build |

---

## Dashboard Demo

The bot includes a [Rich](https://github.com/Textualize/rich)-powered terminal dashboard that displays real-time positions, P/L, and system status.

```bash
# Run the demo with mock data (no API keys needed):
pip install rich
python dashboard_demo.py
```

---

## Disclaimer

This repository is a **showcase of the architecture and engineering** behind CryptoGuardian. Source code, strategy parameters, and proprietary configurations are not included.

The bot is a real, actively-running trading system. Backtest results shown use real market data with conservative fee/slippage assumptions. Live results may differ.

**This is not financial advice.** Cryptocurrency trading involves significant risk of loss.

---

## Author

Built by **[@Jotanune](https://github.com/Jotanune)** — a solo developer building automated trading systems.

- 🔗 [PropGuardian](https://github.com/Jotanune/PropGuardian) — Forex prop firm trading bot (MQL5)
