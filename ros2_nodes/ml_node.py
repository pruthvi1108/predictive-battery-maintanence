import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray, String
import numpy as np
import joblib
import os
 
 
# ── Topic names ──────────────────────────────────────────────────────
TOPIC_IN        = '/bms/battery_data'
TOPIC_STATUS    = '/bms/anomaly_status'   # "NORMAL" | "ANOMALY"
TOPIC_SCORE     = '/bms/anomaly_score'    # raw IF decision score (float)
 
 
class MLNode(Node):
    """
    Isolation Forest inference node.
 
    Subscribes to:  /bms/battery_data      (Float32MultiArray: voltage, current, temperature)
    Publishes to:   /bms/anomaly_status     (String:           "NORMAL" or "ANOMALY")
                    /bms/anomaly_score      (Float32MultiArray: [score, voltage, current, temperature])
 
    The anomaly_score topic carries the raw decision_function score (more negative
    = more anomalous) together with the original readings so the alert_node can
    log or act on both pieces of information without re-subscribing to battery_data.
    """
 
    def __init__(self):
        super().__init__('ml_node')
 
        # ── Parameters ──────────────────────────────────────────────
        self.declare_parameter('model_path',  self._default_path('model.pkl'))
        self.declare_parameter('scaler_path', self._default_path('scaler.pkl'))
        self.declare_parameter('score_threshold', -0.1)
        # Isolation Forest predict() already uses the model's contamination threshold,
        # but you can tighten/loosen sensitivity here by comparing decision scores.
 
        model_path  = self.get_parameter('model_path').value
        scaler_path = self.get_parameter('scaler_path').value
        self.threshold = self.get_parameter('score_threshold').value
 
        # ── Load model ───────────────────────────────────────────────
        self.model = None
        try:
            self.model = joblib.load(model_path)
            self.get_logger().info(f'Model loaded: {model_path}')
        except Exception as e:
            self.get_logger().error(f'Failed to load model: {e}')
 
        # ── Load scaler (optional but recommended) ───────────────────
        self.scaler = None
        if os.path.exists(scaler_path):
            try:
                self.scaler = joblib.load(scaler_path)
                self.get_logger().info(f'Scaler loaded: {scaler_path}')
            except Exception as e:
                self.get_logger().warn(f'Scaler found but could not load: {e}')
        else:
            self.get_logger().warn(
                'No scaler.pkl found — running inference on raw values. '
                'If you trained with StandardScaler, save and provide scaler.pkl.'
            )
 
        # ── Pub / Sub ────────────────────────────────────────────────
        self.sub = self.create_subscription(
            Float32MultiArray, TOPIC_IN, self.on_battery_data, 10
        )
        self.pub_status = self.create_publisher(String,            TOPIC_STATUS, 10)
        self.pub_score  = self.create_publisher(Float32MultiArray, TOPIC_SCORE,  10)
 
        self.get_logger().info('MLNode ready — waiting for battery data...')
 
    # ────────────────────
    def on_battery_data(self, msg: Float32MultiArray):
        if self.model is None:
            return
 
        data = list(msg.data)
 
        if len(data) != 3:
            self.get_logger().error(
                f'Expected 3 fields [voltage, current, temperature], got {len(data)}'
            )
            return
 
        voltage, current, temperature = data
 
        try:
            X = np.array([data], dtype=np.float32)   # shape (1, 3)
 
            if self.scaler is not None:
                X = self.scaler.transform(X)
 
            prediction = self.model.predict(X)[0]         # 1 = normal, -1 = anomaly
            score      = self.model.decision_function(X)[0]  # lower = more anomalous
 
            is_anomaly = (prediction == -1)
 
            # ── Publish status string ────────────────────────────────
            status_msg      = String()
            status_msg.data = 'ANOMALY' if is_anomaly else 'NORMAL'
            self.pub_status.publish(status_msg)
 
            # ── Publish score + readings (for alert_node) ────────────
            score_msg      = Float32MultiArray()
            score_msg.data = [float(score), voltage, current, temperature]
            self.pub_score.publish(score_msg)
 
            if is_anomaly:
                self.get_logger().warn(
                    f'ANOMALY  score={score:.4f}  '
                    f'V={voltage:.3f}  I={current:.3f}  T={temperature:.2f}'
                )
            else:
                self.get_logger().debug(
                    f'Normal   score={score:.4f}  '
                    f'V={voltage:.3f}  I={current:.3f}  T={temperature:.2f}'
                )
 
        except Exception as e:
            self.get_logger().error(f'Inference error: {e}')
 
    # ────────────────────────────────────────────────────────────────
    @staticmethod
    def _default_path(filename: str) -> str:
        """Resolve path relative to this file's directory."""
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
 
 
# ────────────────────────────────────────────────────────────────────
def main(args=None):
    rclpy.init(args=args)
    node = MLNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
 
 
if __name__ == '__main__':
    main()
 