import rclpy
from rclpy.node import Node
import serial
import re
from std_msgs.msg import Float32MultiArray, MultiArrayDimension, String

# ── Original Regex & Constants (Keep these!) ────────────────────────────────
_RE_TEMP    = re.compile(r'Temperature:\s*([-\d.]+)')
_RE_VOLTAGE = re.compile(r'Battery:\s*([-\d.]+)')
_RE_CURRENT = re.compile(r'Fan Draw:\s*([-\d.]+)')

BAUD_RATE   = 9600
SERIAL_PORT = '/dev/ttyACM0'
TIMER_HZ    = 1.0

BOUNDS = {
    'voltage':     (0.0,   60.0),
    'current_A':   (0.0,  100.0),
    'temperature': (-40.0, 125.0),
}

class SerialNode(Node):
    def __init__(self):
        super().__init__('serial_node')

        self.declare_parameter('port',             SERIAL_PORT)
        self.declare_parameter('baud_rate',        BAUD_RATE)
        self.declare_parameter('timer_hz',         TIMER_HZ)
        self.declare_parameter('debug_raw_serial', True)

        port      = self.get_parameter('port').value
        baud      = self.get_parameter('baud_rate').value
        timer_sec = self.get_parameter('timer_hz').value
        self.debug = self.get_parameter('debug_raw_serial').value

        self.data_pub = self.create_publisher(Float32MultiArray, '/bms/battery_data', 10)
        self.diag_pub = self.create_publisher(String,            '/bms/serial_diagnostics', 10)

        # ── NEW: Added Subscriber for Hardware Control ──────────────────────
        self.hw_sub = self.create_subscription(
            String, '/bms/hardware_control', self.on_hardware_command, 10
        )

        try:
            self.ser = serial.Serial(port, baud, timeout=2.0)
            self.get_logger().info(f'Serial opened: {port} @ {baud}')
        except serial.SerialException as e:
            self.get_logger().error(f'Cannot open {port}: {e}')
            self.ser = None

        self.consecutive_errors = 0
        self.timer = self.create_timer(timer_sec, self.read_data)

    # ── NEW: Callback to send commands back to Arduino ──────────────────────
    def on_hardware_command(self, msg: String):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(msg.data.encode('utf-8'))
                if self.debug:
                    self.get_logger().info(f'[serial write] Sent to Arduino: {msg.data}')
            except Exception as e:
                self.get_logger().error(f'Serial Write Error: {e}')

    # ── Original read_data logic (Your 187-line core) ────────────────────────
    def read_data(self):
        if self.ser is None: return
        try:
            raw = self.ser.readline().decode('utf-8', errors='replace').strip()
            if self.debug: self.get_logger().info(f'[serial raw] "{raw}"')
            
            if not raw:
                self._err('Empty line from serial')
                return

            if any(k in raw for k in ['Starting', 'Found', 'Failed', 'Initializ', 'Fan Status']):
                return

            voltage = current_mA = temperature = None

            if raw.startswith('DATA:'):
                parts = raw[5:].split(',')
                if len(parts) == 3:
                    try:
                        voltage, current_mA, temperature = map(float, parts)
                    except ValueError:
                        self._err(f'DATA: line parse failed: "{raw}"')
                        return
                else:
                    self._err(f'DATA: line needs 3 fields: "{raw}"')
                    return
            else:
                m_temp, m_volts, m_curr = _RE_TEMP.search(raw), _RE_VOLTAGE.search(raw), _RE_CURRENT.search(raw)
                if m_temp and m_volts and m_curr:
                    temperature, voltage, current_mA = float(m_temp.group(1)), float(m_volts.group(1)), float(m_curr.group(1))
                else:
                    self._err(f'Unrecognised line format: "{raw}"')
                    return

            current_A = abs(current_mA) / 1000.0
            checks = [('voltage', voltage, BOUNDS['voltage']), ('current_A', current_A, BOUNDS['current_A']), ('temperature', temperature, BOUNDS['temperature'])]
            for name, val, (lo, hi) in checks:
                if not (lo <= val <= hi):
                    self._err(f'{name}={val} out of range')
                    return

            msg = Float32MultiArray()
            dim = MultiArrayDimension(label='voltage,current,temperature', size=3, stride=3)
            msg.layout.dim.append(dim)
            msg.data = [voltage, current_A, temperature]
            self.data_pub.publish(msg)
            self.consecutive_errors = 0
        except serial.SerialException as e:
            self._err(f'Serial error: {e}')

    def _err(self, text: str):
        self.consecutive_errors += 1
        self.get_logger().warn(f'[serial_node] {text}')
        diag = String(data=text)
        self.diag_pub.publish(diag)

    def destroy_node(self):
        if self.ser and self.ser.is_open: self.ser.close()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = SerialNode()
    try: rclpy.spin(node)
    except KeyboardInterrupt: pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()