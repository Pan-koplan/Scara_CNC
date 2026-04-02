import React, { useEffect, useRef, useState } from "react";

function App() {
  const ws = useRef(null);

  const [status, setStatus] = useState("Connecting...");
  const [robot, setRobot] = useState({
    j1: 0,
    j2: 0,
    z: 0,
    tool: 0,
    x: 0,
    y: 0,
  });

  const L1 = 120;
  const L2 = 90;
  const center = 220;

  useEffect(() => {
    ws.current = new WebSocket(`ws://${window.location.hostname}:8000/ws`);

    ws.current.onopen = () => setStatus("Online");
    ws.current.onclose = () => setStatus("Offline");

    ws.current.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "STATUS") {
        setRobot(data);
      }
    };

    return () => ws.current?.close();
  }, []);

  const send = (payload) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(payload));
    }
  };

  const jogJoint = (joint, delta) => {
    send({ type: "JOINT_JOG", joint, delta });
  };

  const setPreset = (j1, j2, z = 0, tool = 0) => {
    send({ type: "SET_JOINTS", j1, j2, z, tool });
  };

  const home = () => send({ type: "HOME" });

  const rad1 = (robot.j1 * Math.PI) / 180;
  const rad2 = ((robot.j1 + robot.j2) * Math.PI) / 180;

  const x1 = center + L1 * Math.cos(rad1);
  const y1 = center - L1 * Math.sin(rad1);
  const x2 = x1 + L2 * Math.cos(rad2);
  const y2 = y1 - L2 * Math.sin(rad2);

  return (
    <div style={styles.page}>
      <div style={styles.left}>
        <h1 style={{ marginTop: 0 }}>SCARA Joint Mode</h1>
        <div
          style={{
            ...styles.badge,
            color: status === "Online" ? "#0a7f38" : "#b42318",
          }}
        >
          {status}
        </div>

        <svg width="440" height="440" style={styles.svg}>
          <defs>
            <pattern
              id="grid"
              width="20"
              height="20"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M 20 0 L 0 0 0 20"
                fill="none"
                stroke="#e5e7eb"
                strokeWidth="1"
              />
            </pattern>
          </defs>
          <rect width="440" height="440" fill="url(#grid)" />
          <circle cx={center} cy={center} r="6" fill="#111827" />
          <line
            x1={center}
            y1={center}
            x2={x1}
            y2={y1}
            stroke="#111827"
            strokeWidth="10"
            strokeLinecap="round"
          />
          <line
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="#ef4444"
            strokeWidth="8"
            strokeLinecap="round"
          />
          <circle cx={x1} cy={y1} r="7" fill="#111827" />
          <circle cx={x2} cy={y2} r="7" fill="#ef4444" />
        </svg>

        <div style={styles.state}>
          <div>J1: {robot.j1.toFixed(1)}°</div>
          <div>J2: {robot.j2.toFixed(1)}°</div>
          <div>Z: {robot.z.toFixed(1)} мм</div>
          <div>Tool: {robot.tool.toFixed(1)}°</div>
          <div>X: {robot.x.toFixed(1)} м</div>
          <div>Y: {robot.y.toFixed(1)} м</div>
        </div>
      </div>

      <div style={styles.right}>
        <div style={styles.card}>
          <h3>Позвенное управление</h3>

          <div style={styles.row}>
            <span>J1</span>
            <button style={styles.btn} onClick={() => jogJoint("j1", -5)}>
              -5°
            </button>
            <button style={styles.btn} onClick={() => jogJoint("j1", 5)}>
              +5°
            </button>
          </div>

          <div style={styles.row}>
            <span>J2</span>
            <button style={styles.btn} onClick={() => jogJoint("j2", -5)}>
              -5°
            </button>
            <button style={styles.btn} onClick={() => jogJoint("j2", 5)}>
              +5°
            </button>
          </div>

          <div style={styles.row}>
            <span>Z</span>
            <button style={styles.btn} onClick={() => jogJoint("z", -5)}>
              -5 мм
            </button>
            <button style={styles.btn} onClick={() => jogJoint("z", 5)}>
              +5 мм
            </button>
          </div>

          <div style={styles.row}>
            <span>Tool</span>
            <button style={styles.btn} onClick={() => jogJoint("tool", -5)}>
              -5°
            </button>
            <button style={styles.btn} onClick={() => jogJoint("tool", 5)}>
              +5°
            </button>
          </div>
        </div>

        <div style={styles.card}>
          <h3>Пресеты</h3>
          <button style={styles.btnWide} onClick={() => setPreset(30, 20)}>
            Поза A
          </button>
          <button style={styles.btnWide} onClick={() => setPreset(60, -30)}>
            Поза B
          </button>
          <button style={styles.btnWide} onClick={() => setPreset(90, 0)}>
            Поза C
          </button>
          <button style={styles.btnWide} onClick={home}>
            Домой
          </button>
        </div>
      </div>
    </div>
  );
}

const styles = {
  page: {
    display: "grid",
    gridTemplateColumns: "1.2fr 0.8fr",
    gap: "24px",
    padding: "24px",
    fontFamily: "Inter, Arial, sans-serif",
    background: "#f8fafc",
    minHeight: "100vh",
    color: "#111827",
  },
  left: { display: "flex", flexDirection: "column", gap: "16px" },
  right: { display: "flex", flexDirection: "column", gap: "16px" },
  svg: {
    background: "#ffffff",
    border: "1px solid #e5e7eb",
    borderRadius: "16px",
  },
  card: {
    background: "#ffffff",
    border: "1px solid #e5e7eb",
    borderRadius: "16px",
    padding: "16px",
  },
  row: {
    display: "grid",
    gridTemplateColumns: "50px 1fr 1fr",
    gap: "8px",
    alignItems: "center",
    marginBottom: "10px",
  },
  btn: {
    padding: "10px 12px",
    borderRadius: "10px",
    border: "none",
    background: "#111827",
    color: "#fff",
    cursor: "pointer",
  },
  btnWide: {
    width: "100%",
    padding: "12px",
    borderRadius: "10px",
    border: "none",
    background: "#ef4444",
    color: "#fff",
    cursor: "pointer",
    marginBottom: "10px",
  },
  badge: {
    fontWeight: 700,
  },
  state: {
    background: "#ffffff",
    border: "1px solid #e5e7eb",
    borderRadius: "16px",
    padding: "16px",
    display: "grid",
    gridTemplateColumns: "repeat(2, 1fr)",
    gap: "8px",
  },
};

export default App;
