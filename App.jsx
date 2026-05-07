// src/App.jsx
// Matched exactly to your three ROS2 nodes:
//
//  serial_node  → /bms/battery_data      Float32MultiArray [voltage, current, temperature]
//                  /bms/serial_diagnostics String
//
//  ml_node      → /bms/anomaly_status    String  "NORMAL" | "ANOMALY"
//                  /bms/anomaly_score     Float32MultiArray [score, voltage, current, temperature]
//
//  alert_node   → /bms/alert             String  "[CRITICAL|WARNING] BMS anomaly #N at ..."

import { useState, useEffect, useRef, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

// const WS_URL   = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws/bms";
const MAX_PTS  = 60;
const W_THRESH = -0.10;  // matches ml_node THRESHOLD_WARNING
const C_THRESH = -0.25;  // matches ml_node THRESHOLD_CRITICAL

// Force IPv4 loopback if on localhost to prevent Ubuntu IPv6 routing bugs
const rawHost = window.location.hostname;
const safeHost = rawHost === "localhost" ? "127.0.0.1" : rawHost;
const WS_URL = import.meta.env.VITE_WS_URL || `ws://${safeHost}:8000/ws/bms`;

function severityFromScore(score) {
  if (score === null) return "ANOMALY";
  if (score < C_THRESH) return "CRITICAL";
  if (score < W_THRESH) return "WARNING";
  return "NORMAL";
}

function healthFromRate(rate) {
  if (rate > 0.5) return "CRITICAL";
  if (rate > 0.2) return "DEGRADED";
  return "HEALTHY";
}

function NodePill({ label, active }) {
  return (
    <span style={{ display:"inline-flex", alignItems:"center", gap:5, padding:"3px 8px", borderRadius:20,
      fontSize:10, fontFamily:"monospace", border:"0.5px solid var(--color-border-tertiary)",
      background:"var(--color-background-secondary)", color:"var(--color-text-secondary)" }}>
      <span style={{ width:6, height:6, borderRadius:"50%", background: active?"#639922":"#E24B4A",
        animation: active?"pulse 1.5s infinite":"none" }} />
      {label}
    </span>
  );
}

function MetricCard({ label, value, unit, accentColor, sub, subUp }) {
  return (
    <div style={{ background:"var(--color-background-secondary)",
      borderRadius:"0 0 var(--border-radius-md) var(--border-radius-md)",
      borderTop:`2px solid ${accentColor}`, padding:"12px 14px" }}>
      <div style={{ fontSize:11, color:"var(--color-text-secondary)", fontFamily:"monospace", letterSpacing:".04em", marginBottom:6 }}>{label}</div>
      <div style={{ fontSize:22, fontWeight:500, fontFamily:"monospace", lineHeight:1 }}>
        {value ?? "—"}<span style={{ fontSize:11, color:"var(--color-text-secondary)", fontWeight:400 }}> {unit}</span>
      </div>
      <div style={{ fontSize:10, marginTop:4,
        color: subUp === true ? "#639922" : subUp === false ? "#E24B4A" : "var(--color-text-tertiary)" }}>
        {sub}
      </div>
    </div>
  );
}

function HealthBadge({ health }) {
  const s = {
    HEALTHY:  { bg:"var(--color-background-success)", c:"var(--color-text-success)", b:"var(--color-border-success)", dot:"#639922" },
    DEGRADED: { bg:"var(--color-background-warning)", c:"var(--color-text-warning)", b:"var(--color-border-warning)", dot:"#BA7517" },
    CRITICAL: { bg:"var(--color-background-danger)",  c:"var(--color-text-danger)",  b:"var(--color-border-danger)",  dot:"#E24B4A" },
  }[health] || { bg:"var(--color-background-success)", c:"var(--color-text-success)", b:"var(--color-border-success)", dot:"#639922" };
  return (
    <div style={{ display:"inline-flex", alignItems:"center", gap:7, padding:"6px 12px",
      borderRadius:"var(--border-radius-md)", fontFamily:"monospace", fontSize:12, fontWeight:500,
      background:s.bg, color:s.c, border:`0.5px solid ${s.b}` }}>
      <div style={{ width:7, height:7, borderRadius:"50%", background:s.dot }} />{health}
    </div>
  );
}

function RateBar({ pct, color }) {
  return (
    <div style={{ height:4, background:"var(--color-background-tertiary)", borderRadius:2, overflow:"hidden" }}>
      <div style={{ height:"100%", width:`${Math.min(100,pct)}%`, background:color,
        borderRadius:2, transition:"width .5s, background .5s" }} />
    </div>
  );
}

function AlertRow({ entry }) {
  const sc = {
    WARNING:  { bg:"var(--color-background-warning)", c:"var(--color-text-warning)" },
    CRITICAL: { bg:"var(--color-background-danger)",  c:"var(--color-text-danger)"  },
    NORMAL:   { bg:"var(--color-background-success)", c:"var(--color-text-success)" },
  }[entry.severity] || {};
  return (
    <div style={{ display:"flex", gap:8, padding:"6px 0", borderBottom:"0.5px solid var(--color-border-tertiary)" }}>
      <div style={{ fontFamily:"monospace", fontSize:10, color:"var(--color-text-tertiary)", minWidth:52, paddingTop:1 }}>{entry.time}</div>
      <div style={{ fontSize:10, fontWeight:500, padding:"1px 6px", borderRadius:3, fontFamily:"monospace",
        background:sc.bg, color:sc.c, whiteSpace:"nowrap", alignSelf:"flex-start" }}>{entry.severity}</div>
      <div style={{ fontSize:11, color:"var(--color-text-secondary)", lineHeight:1.4 }}>{entry.msg}</div>
    </div>
  );
}

const PANEL = { background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:"var(--border-radius-lg)", padding:14 };
const PTITLE = { fontSize:11, fontFamily:"monospace", color:"var(--color-text-secondary)", letterSpacing:".06em", marginBottom:12, textTransform:"uppercase" };
const DROW = { display:"flex", justifyContent:"space-between", fontSize:11, padding:"4px 0", borderBottom:"0.5px solid var(--color-border-tertiary)" };
const TT = { contentStyle:{ background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:6, fontSize:11, fontFamily:"monospace" }, labelStyle:{ color:"var(--color-text-tertiary)" } };

export default function App() {
  const [connected, setConnected] = useState(false);
  const [history,   setHistory]   = useState([]);
  const [latest,    setLatest]    = useState(null);
  const [alerts,    setAlerts]    = useState([]);
  const [anomWin,   setAnomWin]   = useState([]);
  const [counters,  setCounters]  = useState({ reads:0, alertN:0, serialErrs:0 });
  const wsRef = useRef(null);

  const handleMsg = useCallback((raw) => {
    const d = JSON.parse(raw);
    const point = {
      time:        new Date().toTimeString().slice(0,8),
      voltage:     +d.voltage.toFixed(3),
      current:     +d.current.toFixed(3),
      temperature: +d.temperature.toFixed(2),
      score:       +d.score.toFixed(4),
      label:       d.label,    // 1 or -1  (from ml_node predict())
      status:      d.status,   // "NORMAL" | "ANOMALY"
    };
    setHistory(p => [...p.slice(-MAX_PTS+1), point]);
    setLatest(point);
    setAnomWin(p => [...p.slice(-19), point.label]);
    setCounters(p => ({
      reads:      p.reads + 1,
      alertN:     point.label === -1 ? p.alertN + 1 : p.alertN,
      serialErrs: d.serial_errors ?? p.serialErrs,
    }));
    if (point.label === -1) {
      const sev = severityFromScore(point.score);
      setAlerts(p => [{
        time: point.time, severity: sev,
        msg: `score=${point.score.toFixed(4)} V=${point.voltage.toFixed(2)} I=${point.current.toFixed(3)} T=${point.temperature.toFixed(1)}°C`,
      }, ...p].slice(0, 12));
    }
  }, []);

  useEffect(() => {
    let ws = null;
    let reconnectTimer = null;
    let isMounted = true; // Tracks if the component is actually alive

    function connect() {
      ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        // If React already unmounted this render, close the ghost connection
        if (!isMounted) {
          ws.close();
          return;
        }
        setConnected(true);
        console.log("WebSocket Connected to: ", WS_URL);
      };

      ws.onclose = () => {
        if (!isMounted) return;
        setConnected(false);
        console.log("WebSocket Disconnected. Reconnecting in 3s...");
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = (err) => {
        console.error("WebSocket Error: ", err);
        // Do NOT call ws.close() here; let onclose handle it to avoid state conflicts
      };

      ws.onmessage = (e) => {
        try {
          // Python sometimes outputs 'NaN' in JSON which breaks Javascript. 
          // This safely converts them to null before parsing.
          const safeData = e.data.replace(/\bNaN\b/g, "null");
          handleMsg(safeData);
        } catch(err) {
          console.error("Failed to parse WebSocket JSON:", err, e.data);
        }
      };
    }

    connect();

    // The cleanup function
    return () => {
      isMounted = false;
      clearTimeout(reconnectTimer);
      
      // Only close if fully open. If it is still connecting, let the onopen handler kill it.
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [handleMsg]);

  const prev      = history.length >= 2 ? history[history.length-2] : null;
  const anomRate  = anomWin.length ? anomWin.filter(l=>l===-1).length / anomWin.length : 0;
  const health    = healthFromRate(anomRate);
  const scoreSev  = latest ? severityFromScore(latest.score) : "NORMAL";
  const scoreCol  = scoreSev==="CRITICAL"?"#E24B4A":scoreSev==="WARNING"?"#BA7517":"#639922";
  const rateCol   = health==="CRITICAL"?"#E24B4A":health==="DEGRADED"?"#BA7517":"#639922";
  const vD = latest && prev ? latest.voltage - prev.voltage : null;
  const iD = latest && prev ? latest.current - prev.current : null;

  return (
    <div style={{ background:"var(--color-background-tertiary)", minHeight:"100vh", paddingBottom:16 }}>
      <style>{`@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}`}</style>

      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
        padding:"10px 16px", background:"var(--color-background-primary)",
        borderBottom:"0.5px solid var(--color-border-tertiary)" }}>
        <div style={{ fontFamily:"monospace", fontSize:12, fontWeight:500 }}>BMS / anomaly monitor</div>
        <div style={{ display:"flex", gap:6, alignItems:"center" }}>
          <NodePill label="serial_node" active={connected} />
          <NodePill label="ml_node"     active={connected} />
          <NodePill label="alert_node"  active={connected} />
          <span style={{ marginLeft:4, display:"inline-flex", alignItems:"center", gap:5, padding:"3px 8px",
            borderRadius:20, fontSize:10, fontFamily:"monospace", border:"0.5px solid var(--color-border-tertiary)",
            background:"var(--color-background-secondary)", color:"var(--color-text-secondary)" }}>
            <span style={{ width:6, height:6, borderRadius:"50%", background:connected?"#378ADD":"#E24B4A" }} />
            {connected?"ws connected":"reconnecting…"}
          </span>
        </div>
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:8, padding:"12px 16px" }}>
        <MetricCard label="voltage"     value={latest?.voltage.toFixed(2)}     unit="V"  accentColor="#378ADD"
          sub={vD!==null?`${vD>=0?"+":""}${vD.toFixed(3)} V`:"INA219 · serial_node"} subUp={vD!==null?vD>=0:null} />
        <MetricCard label="current"     value={latest?.current.toFixed(3)}     unit="A"  accentColor="#1D9E75"
          sub={iD!==null?`${iD>=0?"+":""}${iD.toFixed(3)} A`:"INA219 · serial_node"} subUp={iD!==null?iD>=0:null} />
        <MetricCard label="temperature" value={latest?.temperature.toFixed(1)} unit="°C" accentColor="#BA7517"
          sub="DS18B20 · serial_node" />
        <MetricCard label="IF score"    value={latest?.score.toFixed(4)}       unit=""   accentColor="#7F77DD"
          sub={`status: ${scoreSev}`} subUp={scoreSev==="NORMAL"?true:false} />
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 260px", gap:8, padding:"0 16px 8px" }}>

        <div style={PANEL}>
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between" }}>
            <div style={PTITLE}>/bms/battery_data — sensor trend</div>
            <div style={{ display:"flex", gap:12, marginBottom:12 }}>
              {[["#378ADD","voltage"],["#1D9E75","current"],["#BA7517","temp"]].map(([c,l])=>(
                <span key={l} style={{ display:"flex", alignItems:"center", gap:4, fontSize:11, color:"var(--color-text-secondary)", fontFamily:"monospace" }}>
                  <span style={{ width:8, height:3, borderRadius:1, background:c }} />{l}
                </span>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={history} margin={{ top:4, right:4, left:0, bottom:0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,128,128,0.12)" />
              <XAxis dataKey="time" tick={false} />
              <YAxis yAxisId="yL" tick={{ fontSize:9, fontFamily:"monospace", fill:"#888780" }} width={34} tickFormatter={v=>v.toFixed(1)+'V'} />
              <YAxis yAxisId="yR" orientation="right" tick={{ fontSize:9, fontFamily:"monospace", fill:"#888780" }} width={30} />
              <Tooltip {...TT} />
              <Line yAxisId="yL" type="monotone" dataKey="voltage"     stroke="#378ADD" strokeWidth={1.5} dot={false} isAnimationActive={false} />
              <Line yAxisId="yR" type="monotone" dataKey="current"     stroke="#1D9E75" strokeWidth={1.5} dot={false} isAnimationActive={false} />
              <Line yAxisId="yR" type="monotone" dataKey="temperature" stroke="#BA7517" strokeWidth={1.5} dot={false} isAnimationActive={false} strokeDasharray="4 3" />
            </LineChart>
          </ResponsiveContainer>

          <div style={{ ...PTITLE, marginTop:16 }}>/bms/anomaly_score — ml_node decision_function</div>
          <ResponsiveContainer width="100%" height={70}>
            <LineChart data={history} margin={{ top:4, right:4, left:0, bottom:0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,128,128,0.12)" />
              <XAxis dataKey="time" tick={false} />
              <YAxis domain={[-0.5,0.15]} tick={{ fontSize:9, fontFamily:"monospace", fill:"#888780" }} width={34} tickFormatter={v=>v.toFixed(2)} />
              <ReferenceLine y={W_THRESH} stroke="#BA7517" strokeDasharray="3 3" />
              <ReferenceLine y={C_THRESH} stroke="#E24B4A" strokeDasharray="3 3" />
              <Tooltip {...TT} />
              <Line type="monotone" dataKey="score" stroke="#7F77DD" strokeWidth={1.5} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div style={{ display:"flex", flexDirection:"column", gap:8 }}>

          <div style={PANEL}>
            <div style={PTITLE}>battery health</div>
            <HealthBadge health={health} />
            <div style={{ marginTop:10 }}>
              <div style={{ display:"flex", justifyContent:"space-between", fontSize:11, color:"var(--color-text-secondary)", marginBottom:4 }}>
                <span>anomaly rate (last 20)</span>
                <span style={{ fontFamily:"monospace" }}>{(anomRate*100).toFixed(0)}%</span>
              </div>
              <RateBar pct={anomRate*200} color={rateCol} />
              <div style={{ display:"flex", justifyContent:"space-between", fontSize:10, color:"var(--color-text-tertiary)", marginTop:3 }}>
                <span>0%</span><span>20%</span><span>50%+</span>
              </div>
            </div>
            <div style={{ marginTop:10 }}>
              <div style={{ display:"flex", justifyContent:"space-between", fontSize:11, color:"var(--color-text-secondary)", marginBottom:4 }}>
                <span>score severity</span>
                <span style={{ fontFamily:"monospace" }}>{latest?.score.toFixed(4)??"—"}</span>
              </div>
              <RateBar pct={latest?Math.min(100,(-latest.score/0.5)*100):0} color={scoreCol} />
              <div style={{ display:"flex", justifyContent:"space-between", fontSize:10, color:"var(--color-text-tertiary)", marginTop:3 }}>
                <span>normal</span><span>-0.10</span><span>-0.25</span>
              </div>
            </div>
          </div>

          <div style={PANEL}>
            <div style={PTITLE}>node diagnostics</div>
            {[
              ["topic in",       "/bms/battery_data",           "#378ADD"],
              ["ml_node status", latest?.status??"—",            scoreSev==="NORMAL"?"#639922":"#E24B4A"],
              ["alert_node #",   counters.alertN,               null],
              ["serial reads",   counters.reads,                null],
              ["serial errors",  counters.serialErrs,           counters.serialErrs>0?"#E24B4A":null],
              ["last sample",    latest?.time??"—",             null],
            ].map(([k,v,c],i,a)=>(
              <div key={k} style={{ ...DROW, ...(i===a.length-1?{borderBottom:"none"}:{}) }}>
                <span style={{ fontFamily:"monospace", color:"var(--color-text-secondary)" }}>{k}</span>
                <span style={{ fontFamily:"monospace", fontWeight:500, color:c||"var(--color-text-primary)" }}>{v}</span>
              </div>
            ))}
          </div>

          <div style={{ ...PANEL, flex:1 }}>
            <div style={PTITLE}>/bms/alert — alert_node</div>
            <div style={{ overflowY:"auto", maxHeight:220 }}>
              {alerts.length===0
                ? <div style={{ fontSize:11, color:"var(--color-text-tertiary)", fontFamily:"monospace" }}>awaiting alerts...</div>
                : alerts.map((a,i)=><AlertRow key={i} entry={a} />)
              }
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
