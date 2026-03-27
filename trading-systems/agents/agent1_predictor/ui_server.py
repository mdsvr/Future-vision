"""
ui_server.py — Quintyx Agent 1 Web Dashboard
=============================================
Flask backend that:
  - Serves the dashboard UI
  - Runs the trading analysis pipeline
  - Streams live logs to the browser via SSE (Server-Sent Events)
  - Returns the final prediction JSON to the frontend

Run:  py ui_server.py
Open: http://localhost:5000
"""

import sys
import os
import json
import queue
import threading
import logging
import traceback

# Make sure imports from agent1_predictor work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template, request, Response, stream_with_context

app = Flask(__name__, template_folder="templates")

# ── Shared state ───────────────────────────────────────────────────────────────
_log_queue: queue.Queue = queue.Queue()
_analysis_lock = threading.Lock()   # Only one analysis at a time


# ── Custom log handler that feeds into the SSE queue ──────────────────────────
class QueueLogHandler(logging.Handler):
    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q
        self.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self.q.put(("log", record.levelname, msg))
        except Exception:
            pass


# ── Analysis runner (runs in a background thread) ─────────────────────────────
def _run_analysis(symbol: str, allow_network: bool):
    """
    Imports and calls main.run() in a thread.
    Injects a QueueLogHandler so every log line is sent to the SSE queue.
    """
    agent_logger = logging.getLogger("Agent1")
    handler = QueueLogHandler(_log_queue)
    agent_logger.addHandler(handler)

    try:
        # Lazy-import so we don't have import-time side effects
        from main import run
        result = run(symbol=symbol, mode="SAFE", allow_network=allow_network)
        _log_queue.put(("result", result))
    except Exception as e:
        tb = traceback.format_exc()
        _log_queue.put(("error", f"{e}\n{tb}"))
    finally:
        agent_logger.removeHandler(handler)
        _log_queue.put(("done", None))


# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze")
def analyze():
    """
    SSE endpoint. Client connects here; we stream log lines and the final result.
    Query params:
      symbol  — stock ticker (default: AAPL)
      network — 'true' to allow LLM API calls (default: false)
    """
    symbol = request.args.get("symbol", "AAPL").upper().strip()
    allow_network = request.args.get("network", "false").lower() == "true"

    def generate():
        # Drain any stale messages from a previous run
        while not _log_queue.empty():
            try:
                _log_queue.get_nowait()
            except queue.Empty:
                break

        # Signal the frontend that we're starting
        yield f"data: {json.dumps({'type': 'start', 'symbol': symbol})}\n\n"

        # Launch analysis in background thread
        t = threading.Thread(
            target=_run_analysis,
            args=(symbol, allow_network),
            daemon=True,
        )
        t.start()

        # Forward all events from the queue to the client
        while True:
            try:
                item = _log_queue.get(timeout=60)
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                continue

            event_type = item[0]

            if event_type == "log":
                _, level, msg = item
                payload = json.dumps({"type": "log", "level": level, "message": msg})
                yield f"data: {payload}\n\n"

            elif event_type == "result":
                _, result = item
                if result:
                    payload = json.dumps({"type": "result", "data": result})
                    yield f"data: {payload}\n\n"

            elif event_type == "error":
                _, msg = item
                payload = json.dumps({"type": "error", "message": msg})
                yield f"data: {payload}\n\n"
                break

            elif event_type == "done":
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  QUINTYX — Agent 1 Web Dashboard")
    print("  Open your browser at:  http://localhost:5000")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True, use_reloader=False)
