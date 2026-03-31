# CryptoGuardian — Showcase Code Snippets

This directory contains **sanitized excerpts** from the production CryptoGuardian trading bot.

These files demonstrate the engineering quality and architecture of the system without exposing proprietary strategy logic, parameters, or configurations.

## Files

| File | Description | What it demonstrates |
|------|-------------|---------------------|
| `websocket_client.py` | Hyperliquid WebSocket with auto-reconnect | Async Python, exponential backoff, channel dispatch |
| `risk_manager.py` | Multi-layered capital protection | 8 pre-trade risk gates, drawdown monitoring, circuit breaker |
| `kill_switch.py` | Emergency shutdown system | Retry logic, position closure, alerting |
| `async_utils.py` | Retry + lifecycle utilities | Generic async patterns, component management |

## What's NOT included

- Strategy logic (SMC engine, Pairs engine)
- Exact risk parameters and thresholds
- Exchange API credentials or signing logic
- ML model weights and training pipeline
- Per-pair configurations and optimized parameters
