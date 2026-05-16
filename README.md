
# 🔋 Smart Battery Management System with Predictive Maintenance

An AI-powered Smart Battery Management System (BMS) designed for real-time monitoring, anomaly detection, and predictive maintenance of Li-ion battery packs using ROS2, Machine Learning, and IoT technologies.



---

# ✨ Features

* ✅ Real-time voltage, current, and temperature monitoring
* ✅ Machine Learning based anomaly detection
* ✅ ROS2 distributed node architecture
* ✅ Isolation Forest anomaly detection model
* ✅ Live dashboard using React + FastAPI
* ✅ Automatic cooling and battery protection
* ✅ CSV-based data logging
* ✅ Alert system using buzzer and LEDs

---

# 🏗️ System Workflow

The system operates in 5 major layers:

1. **Input Layer**

   * INA219 current/voltage sensing
   * DS18B20 temperature monitoring

2. **Embedded Controller**

   * Arduino UNO collects and formats sensor data

3. **ROS2 Middleware**

   * `serial_node` receives serial data
   * `ml_node` performs anomaly detection
   * `alert_node` determines system state

4. **Dashboard & Logging**

   * React + FastAPI dashboard
   * Real-time monitoring
   * CSV logging

5. **Output & Protection**

   * Cooling fan activation
   * Relay-based battery cutoff
   * Buzzer alerts
   * LED indicators

---

# 🛠️ Tech Stack

| Technology       | Purpose                   |
| ---------------- | ------------------------- |
| Arduino UNO      | Embedded controller       |
| ROS2             | Middleware communication  |
| FastAPI          | Backend API               |
| React            | Dashboard frontend        |
| Isolation Forest | ML anomaly detection      |
| INA219           | Voltage & current sensing |
| DS18B20          | Temperature sensing       |
| Python           | Data processing           |

---

# 📁 Project Structure

```bash
predictive-battery-maintenance/
│
├── arduino/
├── ros2_nodes/
├── dashboard/
├── models/
├── assets/
└── README.md
```

---

# 🚀 How to Run

## 1. Clone Repository

```bash
git clone https://github.com/yourusername/predictive-battery-maintenance.git
```

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## 3. Run ROS2 Nodes

```bash
python serial_node.py
python ml_node.py
python alert_node.py
```

## 4. Start Dashboard

```bash
uvicorn main:app --reload
```

---

# 🧠 Machine Learning Model

The project uses an **Isolation Forest** algorithm for anomaly detection.

The model identifies:

* Overheating
* Voltage spikes
* Current anomalies
* Unsafe battery conditions

---

# 📊 Future Improvements

* 🔹 Cloud monitoring support
* 🔹 Mobile application integration
* 🔹 Battery State-of-Health estimation
* 🔹 Predictive battery life analytics
* 🔹 MQTT/IoT cloud deployment

---

# 📄 License

MIT License
