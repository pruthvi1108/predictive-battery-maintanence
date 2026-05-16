#!/usr/bin/env python3
"""
retrain_model.py
────────────────
Run this ONCE on your ROS2 machine to retrain the Isolation Forest
on the locally installed sklearn version (1.4.1) and save fresh
model.pkl and scaler.pkl files.

Place this script in:
    ~/ros2_ws/src/battery_monitor/battery_monitor/

Then run:
    cd ~/ros2_ws/src/battery_monitor/battery_monitor/
    python3 retrain_model.py

It will overwrite model.pkl and scaler.pkl in the same directory.
After running, do:
    cd ~/ros2_ws && colcon build --packages-select battery_monitor
"""

import os
import numpy as np
import joblib
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# ── Output paths (same directory as this script) ─────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH  = os.path.join(SCRIPT_DIR, 'model.pkl')
SCALER_PATH = os.path.join(SCRIPT_DIR, 'scaler.pkl')

# ── 1. Reproduce your original training data ──────────────────────────────────
# Replace this block with your actual training CSV if you have it.
# The synthetic data below matches typical LiFePO4 / Li-ion BMS readings:
#   voltage     : 3.0 – 4.2 V
#   current     : 0.0 – 3.0 A  (charging / discharging)
#   temperature : 20  – 40 °C

np.random.seed(42)
N = 2000   # number of normal training samples

voltage     = np.random.uniform(3.0, 4.2, N)
current     = np.random.uniform(0.0, 3.0, N)
temperature = np.random.uniform(20.0, 40.0, N)

X_train = np.column_stack([voltage, current, temperature])

# ── If you have a real CSV, load it instead: ─────────────────────────────────
# import pandas as pd
# df = pd.read_csv('your_training_data.csv')
# X_train = df[['voltage', 'current', 'temperature']].values
# ─────────────────────────────────────────────────────────────────────────────

print(f"Training on {N} samples  shape={X_train.shape}")
print(f"  voltage     : {X_train[:,0].min():.2f} – {X_train[:,0].max():.2f} V")
print(f"  current     : {X_train[:,1].min():.2f} – {X_train[:,1].max():.2f} A")
print(f"  temperature : {X_train[:,2].min():.2f} – {X_train[:,2].max():.2f} °C")

# ── 2. Fit scaler ─────────────────────────────────────────────────────────────
scaler   = StandardScaler()
X_scaled = scaler.fit_transform(X_train)

# ── 3. Train Isolation Forest ─────────────────────────────────────────────────
# contamination = expected fraction of anomalies in your live data.
# 0.05 means "I expect ~5% of readings to be anomalous".
# Tune this to your domain — lower = stricter.
model = IsolationForest(
    n_estimators=100,
    contamination=0.05,
    random_state=42,
)
model.fit(X_scaled)

# ── 4. Quick sanity check ─────────────────────────────────────────────────────
normal_sample  = scaler.transform([[3.7, 1.5, 28.0]])   # typical good reading
anomaly_sample = scaler.transform([[5.5, 15.0, 85.0]])  # clearly bad reading

pred_normal  = model.predict(normal_sample)[0]
pred_anomaly = model.predict(anomaly_sample)[0]
score_normal  = model.decision_function(normal_sample)[0]
score_anomaly = model.decision_function(anomaly_sample)[0]

print("\nSanity check:")
print(f"  Normal  reading [3.7V, 1.5A, 28°C]  → predict={pred_normal:+d}  score={score_normal:.4f}")
print(f"  Anomaly reading [5.5V, 15A,  85°C]  → predict={pred_anomaly:+d}  score={score_anomaly:.4f}")

assert pred_normal  ==  1, "ERROR: normal sample predicted as anomaly — check training data"
assert pred_anomaly == -1, "ERROR: anomaly sample not detected — reduce contamination value"
print("  Both checks passed ✓")

# ── 5. Save ───────────────────────────────────────────────────────────────────
joblib.dump(scaler, SCALER_PATH)
joblib.dump(model,  MODEL_PATH)

print(f"\nSaved:")
print(f"  {SCALER_PATH}")
print(f"  {MODEL_PATH}")
print("\nNow rebuild:")
print("  cd ~/ros2_ws && colcon build --packages-select battery_monitor")
print("  source install/setup.bash")
print("  ros2 launch battery_monitor launch.py")
