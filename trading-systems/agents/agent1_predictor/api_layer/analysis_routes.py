from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import sys
import os
import asyncio

from logger import get_logger
logger = get_logger()

from data_layer.live_market_feed import fetch_ohlcv
from data_layer.websocket_client import MarketStreamer
from main import run as agent_pipeline

router = APIRouter()

class AnalysisResponse(BaseModel):
    """
    FastAPI Pydantic schema for the structured response.
    We return the exact JSON the ML pipeline generates.
    """
    prediction_id: str
    symbol: str
    timestamp: str
    action: str
    confidence: float
    recommended_allocation_pct: float
    time_horizon: str
    entry_price: float
    stop_loss: float
    targets: list[float]
    strategy_signals: dict
    market_regime: str
    reasoning: str
    guardian_status: str

@router.get("/analyze/{symbol}", response_model=AnalysisResponse)
async def analyze_stock(
    symbol: str, 
    mode: str = Query("SAFE", description="Operating mode: SAFE, LIVE_DATA, or PAPER")
):
    """
    Primary Agent 1 Analysis Endpoint.
    1. Asynchronously fetches OHLCV data from Redis or external API.
    2. Dispatches the heavy ML/LLM pipeline to a synchronous thread pool.
    """
    # ── 1. Async Data Fetch (Sub-millisecond if cached) ──
    df = await fetch_ohlcv(symbol)
    
    if df is None or df.empty:
        raise HTTPException(
            status_code=404, 
            detail=f"Market data for {symbol} not found or insufficient rows."
        )

    # ── 2. Run Heavy Pipeline in Thread Pool ──
    # The agent_pipeline (main.run) is synchronous and blocks while talking to LLMs.
    # We use to_thread so the FastAPI event loop isn't blocked for other users.
    try:
        result = await asyncio.to_thread(
            agent_pipeline,
            symbol=symbol,
            mode=mode,
            allow_network=True,
            precomputed_df=df
        )
    except Exception as e:
        logger.exception("Agent pipeline crashed")
        raise HTTPException(status_code=500, detail="Internal server error")

    if not result:
        raise HTTPException(status_code=500, detail="Agent pipeline failed to produce a valid prediction.")

    return result

@router.websocket("/ws/market_data/{symbol}")
async def websocket_market_data(websocket: WebSocket, symbol: str):
    """
    Phase 5: WebSocket Streaming Endpoint.
    Connects to the MarketStreamer which automatically pushes tick updates.
    Runs the agent pipeline on every tick update and pushes JSON to the frontend.
    """
    await websocket.accept()
    logger.info(f"Frontend WebSocket client connected for {symbol} stream.")
    
    streamer = MarketStreamer(symbol)
    
    # Run the stream indefinitely until client disconnects
    try:
        # `streamer.stream()` yields an updated DataFrame every 2 seconds (or physical tick)
        async for live_df in streamer.stream():
            try:
                # Dispatch the heavy pipeline locally
                result = await asyncio.to_thread(
                    agent_pipeline,
                    symbol=symbol,
                    mode="SAFE",
                    allow_network=True,
                    precomputed_df=live_df
                )
                
                # Push the analysis back to the React UI immediately
                if result:
                    await websocket.send_json(result)
            except Exception as e:
                logger.error(f"[WebSocket] Internal Pipeline Error: {e}")
                await websocket.send_json({"error": "Internal Pipeline Error", "detail": str(e)})

    except WebSocketDisconnect:
        logger.info(f"Frontend WebSocket client disconnected from {symbol} stream.")
    except Exception as e:
        logger.error(f"[WebSocket] Connection dropped ungracefully: {e}")
        try:
            await websocket.close()
        except:
            pass
