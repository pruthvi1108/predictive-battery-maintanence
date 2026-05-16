# main.py — FastAPI WebSocket bridge for BMS ROS2 pipeline
#
# THE FIX: Use rclpy.executors.SingleThreadedExecutor + executor.spin_once()
# inside the thread loop instead of rclpy.spin(). This avoids the GIL deadlock
# where rclpy.spin() blocks indefinitely and callbacks never fire.
#
# Subscribes to:
#   /bms/battery_data        Float32MultiArray [voltage, current, temperature]
#   /bms/serial_diagnostics  String
#   /bms/anomaly_status      String  "NORMAL" | "ANOMALY"
#   /bms/anomaly_score       Float32MultiArray [score, voltage, current, temperature]
#   /bms/alert               String

import asyncio
import json
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import rclpy
from rclpy.node import Node
from rclpy.executors import SingleThreadedExecutor
from std_msgs.msg import Float32MultiArray, String

# ── Shared cache — written by ROS2 thread, read by FastAPI thread ────────────
# Use a threading.Lock to prevent torn reads on slow machines
_lock = threading.Lock()
cache = {
    "voltage":       0.0,
    "current":       0.0,
    "temperature":   0.0,
    "score":         0.0,
    "label":         1,        # 1 = normal, -1 = anomaly
    "status":        "NORMAL",
    "last_alert":    "",
    "serial_errors": 0,
    "ros_connected": False,    # turns True once the ROS2 node is up
}


def _update(key, value):
    with _lock:
        cache[key] = value


def _snapshot():
    with _lock:
        return dict(cache)


# ── ROS2 bridge node ──────────────────────────────────────────────────────────
class BMSBridge(Node):
    def __init__(self):
        super().__init__("fastapi_bridge")
        self._err_count = 0

        self.create_subscription(
            Float32MultiArray, "/bms/battery_data", self._on_data, 10
        )
        self.create_subscription(
            String, "/bms/serial_diagnostics", self._on_diag, 10
        )
        self.create_subscription(
            Float32MultiArray, "/bms/anomaly_score", self._on_score, 10
        )
        self.create_subscription(
            String, "/bms/anomaly_status", self._on_status, 10
        )
        self.create_subscription(
            String, "/bms/alert", self._on_alert, 10
        )
        _update("ros_connected", True)
        self.get_logger().info("BMSBridge subscriptions active")

    def _on_data(self, msg):
        if len(msg.data) == 3:
            with _lock:
                cache["voltage"]     = round(float(msg.data[0]), 4)
                cache["current"]     = round(float(msg.data[1]), 4)
                cache["temperature"] = round(float(msg.data[2]), 4)

    def _on_diag(self, msg):
        self._err_count += 1
        _update("serial_errors", self._err_count)

    def _on_score(self, msg):
        if len(msg.data) >= 1:
            _update("score", round(float(msg.data[0]), 6))

    def _on_status(self, msg):
        status = msg.data.strip().upper()
        with _lock:
            cache["status"] = status
            cache["label"]  = -1 if status == "ANOMALY" else 1

    def _on_alert(self, msg):
        _update("last_alert", msg.data)


# ── ROS2 spin thread — KEY FIX ────────────────────────────────────────────────
# Instead of rclpy.spin(node) which blocks the GIL, we use an explicit executor
# with spin_once() in a tight loop. This yields control regularly and lets
# FastAPI/asyncio run properly in the main thread.
def _ros_thread():
    rclpy.init()
    node = BMSBridge()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    try:
        while rclpy.ok():
            executor.spin_once(timeout_sec=0.05)  # 50ms slices — 20 Hz callback rate
    except Exception as e:
        print(f"[ROS2 thread] error: {e}")
    finally:
        executor.remove_node(node)
        node.destroy_node()
        rclpy.shutdown()
        _update("ros_connected", False)


# ── FastAPI app ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=_ros_thread, daemon=True, name="ros2-spin")
    t.start()
    # Give ROS2 a moment to come up before accepting requests
    await asyncio.sleep(0.5)
    yield
    # Daemon thread will die with the process — no explicit stop needed


app = FastAPI(title="BMS bridge", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/bms/latest")
async def get_latest():
    return _snapshot()


@app.get("/api/bms/alert")
async def get_alert():
    with _lock:
        return {"alert": cache["last_alert"]}


@app.get("/health")
async def health():
    with _lock:
        ros_ok = cache["ros_connected"]
    return {"status": "ok", "ros_connected": ros_ok}


@app.websocket("/ws/bms")
async def stream(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = _snapshot()
            await ws.send_text(json.dumps(data))
            await asyncio.sleep(1.0)   # 1 Hz — matches serial_node timer
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket] disconnected: {e}")


# ── Entry point (called by ROS2 via setup.py console_scripts) ────────────────
def main(args=None):
    import uvicorn
    uvicorn.run(
        "battery_monitor.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        # IMPORTANT: reload=True would spawn a child process that loses the
        # ROS2 context. Always keep reload=False in production.
        reload=False,
    )


if __name__ == "__main__":
    main()