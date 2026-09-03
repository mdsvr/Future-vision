"""
websocket_client.py
===================
Real-Time Market Data Integration (Phase 5).
Connects to market websockets (e.g. Fyers/Polygon) and falls back to a 
high-fidelity realistic simulator if API credentials aren't present.

Provides an async generator stream of DataFrames suitable for real-time analysis.
"""

import asyncio
import random
import logging
from datetime import datetime, timezone
import pandas as pd
from data_layer.live_market_feed import fetch_ohlcv
from cache_layer.redis_manager import cache

logger = logging.getLogger(__name__)

class TickAggregator:
    """Aggregates sub-second ticks into the LIVE forming candle."""
    def __init__(self, historical_df: pd.DataFrame):
        self.df = historical_df.copy()
        
    def add_tick(self, price: float, volume: float, timestamp: pd.Timestamp):
        """Append a tick to the DataFrame."""
        # Simple implementation: we continuously overwrite the LAST candle 
        # to simulate the "current" live 15m candle forming.
        # In a full-blown exchange stream, we would create a new row when the clock rolls over.
        last_idx = self.df.index[-1]
        
        current_candle = self.df.loc[last_idx].copy()
        
        current_candle['close'] = price
        current_candle['high'] = max(current_candle['high'], price)
        current_candle['low'] = min(current_candle['low'], price)
        current_candle['volume'] += volume
        
        self.df.loc[last_idx] = current_candle
        return self.df


class MarketStreamer:
    """
    Connects to external WebSocket providers or runs a highly accurate Simulator pipeline.
    Yields updated DataFrames.
    """
    def __init__(self, symbol: str):
        self.symbol = symbol

    async def _simulate_stream(self):
        """
        Fallback Ticker Stream:
        Generates realistic micro-ticks using random walks based on the symbol's last known ATR and price.
        """
        logger.info(f"[Simulator] Initializing Real-Time Ticker Simulator for {self.symbol}...")
        
        # 1. Fetch historical data to anchor the simulator
        historical_df = await fetch_ohlcv(self.symbol)
        if historical_df is None or historical_df.empty:
            logger.error(f"[Simulator] Missing historical data. Cannot simulate ticks for {self.symbol}.")
            return
            
        aggregator = TickAggregator(historical_df)
        
        # 2. Extract baseline parameters for realistic random walk
        last_price = historical_df['close'].iloc[-1]
        
        # Compute dynamic volatility (approximated via daily std dev)
        # We will use this to bound our micro-ticks
        recent_std = historical_df['close'].tail(20).std()
        tick_magnitude = recent_std * 0.05 if recent_std > 0 else (last_price * 0.001)

        logger.info(f"[Simulator] Stream ACTIVE. Emitting synthetic WebSocket ticks every 2.0s.")

        current_price = last_price
        
        try:
            while True:
                # Sleep interval defines our "refresh rate" (e.g. 2s for realism without overloading CPU)
                await asyncio.sleep(2.0)
                
                # Introduce a random walk bounded by the calculated dynamic magnitude
                random_shock = random.uniform(-tick_magnitude, tick_magnitude)
                current_price += random_shock
                current_price = max(0.01, current_price)  # Prevent negative prices
                
                fake_volume = random.uniform(10, 500)
                
                now = pd.Timestamp.utcnow()
                
                # 3. Aggregate into live DataFrame and YIELD it
                updated_df = aggregator.add_tick(current_price, fake_volume, now)
                
                yield updated_df
                
        except asyncio.CancelledError:
            logger.info(f"[Simulator] Stopping Stream for {self.symbol}.")
            raise

    async def _fyers_stream(self):
        """
        Connects to the official Fyers Data WebSocket using the fyers_apiv3 SDK.
        """
        logger.info(f"[Fyers WS] Initializing real-time WebSocket for {self.symbol}...")
        
        try:
            from fyers_apiv3.FyersWebsocket import data_ws
        except ImportError:
            logger.error("[Fyers WS] fyers_apiv3 SDK not installed! Falling back to Simulator.")
            async for df in self._simulate_stream():
                yield df
            return

        # Load auth from Config
        try:
            from config import Config
            access_token = Config.FYERS_ACCESS_TOKEN
        except ImportError:
            access_token = None
            
        if not access_token:
            logger.warning("[Fyers WS] No ACCESS_TOKEN found in config. Falling back to Simulator.")
            async for df in self._simulate_stream():
                yield df
            return

        # 1. Fetch initial background DataFrame to anchor the live aggregator
        historical_df = await fetch_ohlcv(self.symbol)
        if historical_df is None or historical_df.empty:
            logger.error(f"[Fyers WS] Missing historical data. Cannot anchor {self.symbol}.")
            return
            
        aggregator = TickAggregator(historical_df)
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()   # captured here — the SDK callback thread has no loop of its own

        def custom_message(msg):
            # Fyers callback: push tick into asyncio Queue thread-safely
            try:
                if msg and isinstance(msg, list) and len(msg) > 0:
                    tick = msg[0]
                    price = float(tick.get('ltp', 0)) # Last Traded Price
                    vol = float(tick.get('vol_traded_today', 0))
                    ts = float(tick.get('ech_tm', 0))
                    
                    if price > 0:
                        # Schedule pushing to queue from synchronous callback
                        asyncio.run_coroutine_threadsafe(
                            queue.put({"price": price, "vol": vol, "ts": ts}),
                            loop
                        )
            except Exception as e:
                logger.error(f"[Fyers WS] Callback parsing error: {e}")

        # Initialize SDK WebSocket
        # Fyers requires Symbol format e.g. "NSE:SBIN-EQ" or "BSE:SENSEX-INDEX"
        fyers = data_ws.FyersDataSocket(
            access_token=access_token,
            log_path="", 
            litemode=False, 
            write_to_file=False
        )
        fyers.websocket_data = custom_message
        
        # Subscribe in background thread
        import threading
        fyers.subscribe(symbols=[self.symbol], data_type="SymbolUpdate")
        threading.Thread(target=fyers.keep_running, daemon=True).start()
        
        logger.info(f"[Fyers WS] Successfully subscribed to {self.symbol}! Waiting for streaming ticks...")

        try:
            while True:
                # Wait for next tick from Fyers
                tick_data = await queue.get()
                
                # Use UTC timestamp from exchange or local
                if tick_data["ts"] > 0:
                    timestamp = pd.to_datetime(tick_data["ts"], unit='s', utc=True)
                else:
                    timestamp = pd.Timestamp.utcnow()
                
                # Aggregate and yield
                updated_df = aggregator.add_tick(tick_data["price"], tick_data["vol"], timestamp)
                yield updated_df
                
        except asyncio.CancelledError:
            logger.info(f"[Fyers WS] Disconnecting from Fyers Stream for {self.symbol}.")
        finally:
            try:
                fyers.unsubscribe(symbols=[self.symbol])
            except:
                pass


    async def stream(self):
        """
        Main unified streaming interface.
        If config requests Fyers, dispatch to _fyers_stream().
        Otherwise, fallback to the Simulator.
        """
        import json, os
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
        with open(cfg_path, "r") as f:
            cfg = json.load(f)
            provider = cfg.get("data", {}).get("market_data_provider", "").lower()
            
        if provider == "fyers":
            async for df in self._fyers_stream():
                yield df
        else:
            logger.info(f"[Streamer] Provider '{provider}' has no native WebSocket integration. Using Simulator Phase 5 stream.")
            async for df in self._simulate_stream():
                yield df
