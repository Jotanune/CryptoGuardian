# CryptoGuardian — Example Scripts

Fully functional utilities from the CryptoGuardian data pipeline.

## download_data.py

Historical OHLCV data downloader supporting Hyperliquid and Binance Futures APIs.

### Features
- Paginated forward downloads (handles 5,000-candle API limits)
- Dual source support (Hyperliquid DEX + Binance Futures as proxy)
- 70+ cryptocurrency perpetuals mapped
- Parquet output (pyarrow) for efficient multi-year storage
- Smart gap detection and rate limiting

### Usage

```bash
# Download BTC, ETH, SOL at 15-minute resolution from Hyperliquid
python download_data.py BTC,ETH,SOL 15m

# Use Binance as data source (public API, no key required)
python download_data.py BTC,ETH,SOL 15m --source binance

# Download from a specific start date
python download_data.py BTC,ETH,SOL 15m --start 20240101

# Download ALL 70+ coins for cointegration scanning
python download_data.py --all-scan 1h --source binance
```

### Dependencies

```
pip install httpx pandas pyarrow loguru
```
