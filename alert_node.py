import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32MultiArray, String
from datetime import datetime
import os
import csv

TOPIC_SCORE  = '/bms/anomaly_score'    
TOPIC_ALERT  = '/bms/alert'            
TOPIC_HW_CMD = '/bms/hardware_control' 

# Adjusted thresholds for better stability
THRESHOLD_CRITICAL = -0.15   # Triggers Red LED/Buzzer earlier
THRESHOLD_WARNING  = -0.04   # Now -0.0549 will be caught as a Warning

class AlertNode(Node):
    def __init__(self):
        super().__init__('alert_node')

        self.declare_parameter('log_dir', '/tmp/bms_logs')
        self.log_dir = self.get_parameter('log_dir').value

        self.csv_file = None
        self.csv_writer = None
        self._init_log()

        # Warm-up Logic
        self.warmup_count = 0
        self.warmup_limit = 10 

        self.sub_score = self.create_subscription(
            Float32MultiArray, TOPIC_SCORE, self.on_score, 10
        )

        self.pub_alert = self.create_publisher(String, TOPIC_ALERT, 10)
        self.pub_hw = self.create_publisher(String, TOPIC_HW_CMD, 10)
        
        self.alert_count = 0
        self.get_logger().info('AlertNode ready with 10s Warm-up period.')

    def on_score(self, msg: Float32MultiArray):
        if len(msg.data) != 4:
            return
            
        score, voltage, current, temperature = msg.data
        hw_msg = String()

        # 1. Warm-up Phase
        if self.warmup_count < self.warmup_limit:
            self.warmup_count += 1
            hw_msg.data = 'N' 
            self.pub_hw.publish(hw_msg)
            return 

        # 2. Hardware Command Logic
        if score < THRESHOLD_WARNING:
            hw_msg.data = 'A'
        else:
            hw_msg.data = 'N'
        self.pub_hw.publish(hw_msg)

        # 3. Logging & Alert Logic
        if score >= 0:
            return

        if score < THRESHOLD_CRITICAL:
            severity = 'CRITICAL'
        elif score < THRESHOLD_WARNING:
            severity = 'WARNING'
        else:
            severity = 'ANOMALY'

        self.alert_count += 1
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        alert_text = f'[{severity}] Anomaly #{self.alert_count} | score={score:.4f}'

        alert_msg = String()
        alert_msg.data = alert_text
        self.pub_alert.publish(alert_msg)

        if self.csv_writer:
            self.csv_writer.writerow([timestamp, severity, score, voltage, current, temperature])
            self.csv_file.flush()

    def _init_log(self):
        os.makedirs(self.log_dir, exist_ok=True)
        path = os.path.join(self.log_dir, f'bms_log_{datetime.now().strftime("%H%M%S")}.csv')
        self.csv_file = open(path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(['timestamp', 'severity', 'score', 'voltage', 'current', 'temperature'])

    def destroy_node(self):
        if self.csv_file: self.csv_file.close()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = AlertNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()