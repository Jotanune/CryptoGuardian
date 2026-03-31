"""Download historical OHLCV data from Hyperliquid or Binance Futures → Parquet.

This is a fully functional data engineering script from the CryptoGuardian
pipeline. It handles paginated API calls, rate limiting, and efficient
Parquet storage for multi-year backtesting datasets.

Supports two data sources:
  - hyperliquid (default): paginated forward to maximise coverage
  - binance: Binance Futures (USDT-M) public API, no API key needed

Usage:
  python download_data.py BTC,ETH,SOL 15m                    # Hyperliquid
  python download_data.py BTC,ETH,SOL 15m --source binance   # Binance proxy
  python download_data.py BTC,ETH,SOL 15m --start 20240101   # From Jan 2024
  python download_data.py --all-scan 1h --source binance      # All 70+ coins
"""

from __future__ import annotations

import asyncio
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd
from loguru import logger

# ── API Endpoints ─────────────────────────────────────────────────────
HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"
BINANCE_FAPI_URL = "https://fapi.binance.com/fapi/v1/klines"

# ── Binance symbol mapping (70+ perpetuals) ──────────────────────────
_BINANCE_SYMBOL_MAP = {
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "BNB": "BNBUSDT",
    "XRP": "XRPUSDT",
    "ADA": "ADAUSDT",
    "DOGE": "DOGEUSDT",
    "AVAX": "AVAXUSDT",
    "DOT": "DOTUSDT",
    "LINK": "LINKUSDT",
    "NEAR": "NEARUSDT",
    "APT": "APTUSDT",
    "SUI": "SUIUSDT",
    "SEI": "SEIUSDT",
    "TIA": "TIAUSDT",
    "ARB": "ARBUSDT",
    "OP": "OPUSDT",
    "MATIC": "MATICUSDT",
    "ATOM": "ATOMUSDT",
    "FTM": "FTMUSDT",
    "INJ": "INJUSDT",
    "STX": "STXUSDT",
    "ALGO": "ALGOUSDT",
    "HBAR": "HBARUSDT",
    "ICP": "ICPUSDT",
    "FET": "FETUSDT",
    "RNDR": "RNDRUSDT",
    "TAO": "TAOUSDT",
    "AR": "ARUSDT",
    "AAVE": "AAVEUSDT",
    "UNI": "UNIUSDT",
    "SNX": "SNXUSDT",
    "MKR": "MKRUSDT",
    "CRV": "CRVUSDT",
    "DYDX": "DYDXUSDT",
    "PENDLE": "PENDLEUSDT",
    "JUP": "JUPUSDT",
    "IMX": "IMXUSDT",
    "GALA": "GALAUSDT",
    "PEPE": "PEPEUSDT",
    "SHIB": "SHIBUSDT",
    "BONK": "BONKUSDT",
    "WIF": "WIFUSDT",
    "FLOKI": "FLOKIUSDT",
    "GRT": "GRTUSDT",
    "FIL": "FILUSDT",
    "PYTH": "PYTHUSDT",
    "LTC": "LTCUSDT",
    "BCH": "BCHUSDT",
    "ETC": "ETCUSDT",
    "XLM": "XLMUSDT",
    "EOS": "EOSUSDT",
    "ENS": "ENSUSDT",
}

ALL_SCAN_COINS = sorted(_BINANCE_SYMBOL_MAP.keys())


# ======================================================================
# Hyperliquid — Paginated Forward Download
# ======================================================================


async def download_candles_hyperliquid(
    symbol: str,
    interval: str = "1h",
    start_ts: int | None = None,
    end_ts: int | None = None,
) -> pd.DataFrame:
    """Download OHLCV from Hyperliquid with forward pagination.

    The API returns up to ~5000 candles per request. We advance startTime
    after each batch until we reach endTime. Handles gaps in data by
    jumping forward after 3 consecutive empty responses.
    """
    if start_ts is None:
        start_ts = int((time.time() - 2 * 365 * 86400) * 1000)
    if end_ts is None:
        end_ts = int(time.time() * 1000)

    all_candles: list[dict] = []
    current_start = start_ts
    empty_streak = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        while current_start < end_ts:
            payload = {
                "type": "candleSnapshot",
                "req": {
                    "coin": symbol,
                    "interval": interval,
                    "startTime": current_start,
                    "endTime": end_ts,
                },
            }

            resp = await client.post(HYPERLIQUID_INFO_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if not data:
                empty_streak += 1
                if empty_streak >= 3:
                    break
                interval_ms = _interval_to_ms(interval)
                current_start += 5000 * interval_ms
                await asyncio.sleep(0.3)
                continue

            empty_streak = 0
            for candle in data:
                all_candles.append(
                    {
                        "timestamp": candle["t"],
                        "open": float(candle["o"]),
                        "high": float(candle["h"]),
                        "low": float(candle["l"]),
                        "close": float(candle["c"]),
                        "volume": float(candle["v"]),
                    }
                )

            last_ts = data[-1]["t"]
            if last_ts <= current_start:
                break
            current_start = last_ts + 1

            logger.info(
                "[HL] {} {} — batch {} candles (total: {})",
                symbol,
                interval,
                len(data),
                len(all_candles),
            )
            await asyncio.sleep(0.5)  # Rate limiting

    return _to_df(all_candles)


# ======================================================================
# Binance Futures — Paginated Forward, 1500/request, No API Key
# ======================================================================


async def download_candles_binance(
    symbol: str,
    interval: str = "1h",
    start_ts: int | None = None,
    end_ts: int | None = None,
) -> pd.DataFrame:
    """Download OHLCV from Binance Futures (USDT-M) with forward pagination.

    Public endpoint, no API key required. Returns up to 1500 candles per
    request. Binance has data going back to 2019 for BTC/ETH — perfect
    for multi-year backtests at 15m resolution.
    """
    binance_sym = _BINANCE_SYMBOL_MAP.get(symbol.upper(), f"{symbol.upper()}USDT")

    if start_ts is None:
        start_ts = int((time.time() - 2 * 365 * 86400) * 1000)
    if end_ts is None:
        end_ts = int(time.time() * 1000)

    all_candles: list[dict] = []
    current_start = start_ts

    async with httpx.AsyncClient(timeout=30.0) as client:
        while current_start < end_ts:
            params = {
                "symbol": binance_sym,
                "interval": interval,
                "startTime": current_start,
                "endTime": end_ts,
                "limit": 1500,
            }

            resp = await client.get(BINANCE_FAPI_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            if not data:
                break

            for k in data:
                all_candles.append(
                    {
                        "timestamp": k[0],
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5]),
                    }
                )

            last_ts = data[-1][0]
            if last_ts <= current_start:
                break
            current_start = last_ts + 1

            logger.info(
                "[BN] {} {} — batch {} candles (total: {})",
                binance_sym,
                interval,
                len(data),
                len(all_candles),
            )
            await asyncio.sleep(0.25)

    return _to_df(all_candles)


# ======================================================================
# Helpers
# ======================================================================

_INTERVAL_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}


def _interval_to_ms(interval: str) -> int:
    return _INTERVAL_MS.get(interval, 3_600_000)


def _to_df(candles: list[dict]) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = (
        df.drop_duplicates(subset="timestamp")
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    return df


def _parse_date(s: str) -> int:
    """Parse YYYYMMDD string to timestamp ms."""
    dt = datetime.strptime(s, "%Y%m%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


# ======================================================================
# Download + Save to Parquet
# ======================================================================


async def download_and_save(
    symbol: str,
    interval: str = "1h",
    output_dir: str = "data",
    source: str = "hyperliquid",
    start_ts: int | None = None,
    end_ts: int | None = None,
) -> Path:
    """Download candles and save to Parquet with smart naming."""
    if source == "binance":
        df = await download_candles_binance(symbol, interval, start_ts, end_ts)
        src_tag = "BN"
    else:
        df = await download_candles_hyperliquid(symbol, interval, start_ts, end_ts)
        src_tag = "HL"

    if df.empty:
        logger.warning("[DL] No data for {} {} (source={})", symbol, interval, source)
        return Path()

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    start = df["timestamp"].iloc[0].strftime("%Y%m%d")
    end = df["timestamp"].iloc[-1].strftime("%Y%m%d")
    filename = f"{symbol.upper()}_{interval}_{start}_{end}.parquet"
    out_path = out_dir / filename

    df.to_parquet(out_path, index=False, engine="pyarrow")
    logger.info(
        "[DL] [{}/{}] Saved {} candles → {} ({} → {})",
        src_tag,
        symbol.upper(),
        len(df),
        out_path,
        start,
        end,
    )
    return out_path


# ======================================================================
# CLI Entry Point
# ======================================================================


def main() -> None:
    symbols = ["BTC", "ETH", "SOL"]
    interval = "1h"
    source = "hyperliquid"
    start_ts: int | None = None
    end_ts: int | None = None

    if len(sys.argv) > 1:
        if sys.argv[1] == "--all-scan":
            symbols = ALL_SCAN_COINS
        else:
            symbols = sys.argv[1].split(",")
    if len(sys.argv) > 2 and not sys.argv[2].startswith("--"):
        interval = sys.argv[2]

    for i, arg in enumerate(sys.argv):
        if arg == "--source" and i + 1 < len(sys.argv):
            source = sys.argv[i + 1].lower()
        elif arg == "--start" and i + 1 < len(sys.argv):
            start_ts = _parse_date(sys.argv[i + 1])
        elif arg == "--end" and i + 1 < len(sys.argv):
            end_ts = _parse_date(sys.argv[i + 1])

    print(f"Downloading {len(symbols)} symbols at {interval} from {source}...")

    async def _run() -> None:
        for i, symbol in enumerate(symbols, 1):
            print(f"  [{i}/{len(symbols)}] {symbol}...")
            try:
                await download_and_save(
                    symbol.strip(),
                    interval,
                    source=source,
                    start_ts=start_ts,
                    end_ts=end_ts,
                )
            except Exception as e:
                logger.warning("[DL] Failed {}: {}", symbol, e)

    asyncio.run(_run())
    print(f"Done. Downloaded {len(symbols)} symbols.")


if __name__ == "__main__":
    main()
