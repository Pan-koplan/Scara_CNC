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

  // Реф для доступа к актуальному состоянию робота внутри асинхронных колбэков
  const robotRef = useRef(robot);
  useEffect(() => {
    robotRef.current = robot;
  }, [robot]);

  const [sliders, setSliders] = useState({
    j1: 0,
    j2: 0,
    z: 0,
    tool: 0,
  });

  const [targetPoint, setTargetPoint] = useState(null);
  const [ikError, setIkError] = useState(null);

  const L1 = 120;
  const L2 = 90;
  const center = 220;

  const LIMITS = {
    j1: { min: -135, max: 135, step: 1, unit: "°" },
    j2: { min: -135, max: 135, step: 1, unit: "°" },
    z: { min: 0, max: 110, step: 1, unit: " мм" },
    tool: { min: -180, max: 180, step: 1, unit: "°" },
  };

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    ws.current = new WebSocket(`${proto}://${window.location.host}/ws`);

    ws.current.onopen = () => setStatus("Online");
    ws.current.onclose = () => setStatus("Offline");

    ws.current.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "STATUS") {
        setRobot(data);
        setSliders({
          j1: data.j1,
          j2: data.j2,
          z: data.z,
          tool: data.tool,
        });
      }
    };

    return () => ws.current?.close();
  }, []);

  const send = (payload) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(payload));
    }
  };

  const handleSliderChange = (joint, value) => {
    setSliders((prev) => ({ ...prev, [joint]: value }));
  };

  const handleSliderRelease = (joint, value) => {
    // Проверка лимитов перед отправкой
    const limit = LIMITS[joint];
    const clamped = Math.max(limit.min, Math.min(limit.max, value));
    send({ type: "SET_JOINT", joint, value: clamped });
  };

  const setPreset = (j1, j2, z = 0, tool = 0) => {
    send({ type: "SET_JOINTS", j1, j2, z, tool });
    setSliders({ j1, j2, z, tool });
  };

  const home = () => {
    send({ type: "HOME" });
    setSliders({ j1: 0, j2: 0, z: 0, tool: 0 });
  };

  // === Обратная кинематика ===
  const svgToRobotCoords = (svgX, svgY) => ({
    x: svgX - center,
    y: -(svgY - center),
  });

  const solveIK = (targetX, targetY) => {
    const r = Math.sqrt(targetX ** 2 + targetY ** 2);
    const maxReach = L1 + L2;
    const minReach = Math.abs(L1 - L2);

    if (r > maxReach || r < minReach) return null;

    const cosJ2 =
      (targetX ** 2 + targetY ** 2 - L1 ** 2 - L2 ** 2) / (2 * L1 * L2);
    const clampedCos = Math.max(-1, Math.min(1, cosJ2));

    // "elbow down" конфигурация
    const j2 = Math.atan2(-Math.sqrt(1 - clampedCos ** 2), clampedCos);

    const k1 = L1 + L2 * Math.cos(j2);
    const k2 = L2 * Math.sin(j2);
    const j1 = Math.atan2(targetY, targetX) - Math.atan2(k2, k1);

    return {
      j1: (j1 * 180) / Math.PI,
      j2: (j2 * 180) / Math.PI,
    };
  };

  // Плавное движение к цели
  const moveToTargetSmooth = (
    targetJ1,
    targetJ2,
    steps = 20,
    interval = 50,
  ) => {
    const startJ1 = robotRef.current.j1;
    const startJ2 = robotRef.current.j2;
    const currentZ = robotRef.current.z;
    const currentTool = robotRef.current.tool;

    let step = 0;
    const timer = setInterval(() => {
      step++;
      const progress = step / steps;
      const eased =
        progress < 0.5 ? 2 * progress ** 2 : 1 - (-2 * progress + 2) ** 2 / 2;

      const currentJ1 = startJ1 + (targetJ1 - startJ1) * eased;
      const currentJ2 = startJ2 + (targetJ2 - startJ2) * eased;

      setSliders((prev) => ({ ...prev, j1: currentJ1, j2: currentJ2 }));
      send({
        type: "SET_JOINTS",
        j1: currentJ1,
        j2: currentJ2,
        z: currentZ,
        tool: currentTool,
      });

      if (step >= steps) {
        clearInterval(timer);
        send({
          type: "SET_JOINTS",
          j1: targetJ1,
          j2: targetJ2,
          z: currentZ,
          tool: currentTool,
        });
      }
    }, interval);
  };

  const handleSvgClick = (e) => {
    const svg = e.currentTarget;
    const rect = svg.getBoundingClientRect();

    const svgX = e.clientX - rect.left;
    const svgY = e.clientY - rect.top;

    const { x, y } = svgToRobotCoords(svgX, svgY);
    setTargetPoint({ x, y });
    setIkError(null);

    const result = solveIK(x, y);

    if (result) {
      // Округление и проверка лимитов
      let j1 = Math.round(result.j1 * 10) / 10;
      let j2 = Math.round(result.j2 * 10) / 10;

      j1 = Math.max(LIMITS.j1.min, Math.min(LIMITS.j1.max, j1));
      j2 = Math.max(LIMITS.j2.min, Math.min(LIMITS.j2.max, j2));

      // 🔄 Выбери один из вариантов:

      // Вариант 1: Мгновенное перемещение (раскомментируй, если нужно)
      // send({ type: "SET_JOINTS", j1, j2, z: robotRef.current.z, tool: robotRef.current.tool });
      // setSliders((prev) => ({ ...prev, j1, j2 }));

      // Вариант 2: Плавное перемещение (по умолчанию)
      moveToTargetSmooth(j1, j2);
    } else {
      setIkError("⚠️ Точка вне рабочей зоны!");
      setTimeout(() => setIkError(null), 2000);
    }
  };

  // === Прямая кинематика для визуализации ===
  const rad1 = (robot.j1 * Math.PI) / 180;
  const rad2 = ((robot.j1 + robot.j2) * Math.PI) / 180;
  const x1 = center + L1 * Math.cos(rad1);
  const y1 = center - L1 * Math.sin(rad1);
  const x2 = x1 + L2 * Math.cos(rad2);
  const y2 = y1 - L2 * Math.sin(rad2);

  return (
    <div style={styles.page}>
      <div style={styles.left}>
        <h1 style={{ marginTop: 0 }}>SCARA Joint Control</h1>
        <div
          style={{
            ...styles.badge,
            color: status === "Online" ? "#0a7f38" : "#b42318",
          }}
        >
          {status}
        </div>

        <svg
          width="440"
          height="440"
          style={{ ...styles.svg, cursor: "crosshair" }}
          onClick={handleSvgClick}
        >
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

          {/* Границы рабочей зоны */}
          <circle
            cx={center}
            cy={center}
            r={L1 + L2}
            fill="none"
            stroke="#e5e7eb"
            strokeDasharray="4 4"
          />
          <circle
            cx={center}
            cy={center}
            r={Math.abs(L1 - L2)}
            fill="none"
            stroke="#e5e7eb"
            strokeDasharray="4 4"
          />

          {/* Звенья робота */}
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

          {/* Целевая точка */}
          {targetPoint && (
            <>
              <circle
                cx={center + targetPoint.x}
                cy={center - targetPoint.y}
                r="12"
                fill="none"
                stroke="#3b82f6"
                strokeWidth="2"
                opacity="0.7"
              />
              <circle
                cx={center + targetPoint.x}
                cy={center - targetPoint.y}
                r="4"
                fill="#3b82f6"
              />
              <line
                x1={x2}
                y1={y2}
                x2={center + targetPoint.x}
                y2={center - targetPoint.y}
                stroke="#3b82f6"
                strokeWidth="1"
                strokeDasharray="3 3"
                opacity="0.5"
              />
            </>
          )}
        </svg>

        {ikError && (
          <div
            style={{
              ...styles.errorBadge,
              color: "#b42318",
              background: "#fef2f2",
            }}
          >
            {ikError}
          </div>
        )}

        <div style={styles.state}>
          <div>J1: {robot.j1.toFixed(1)}°</div>
          <div>J2: {robot.j2.toFixed(1)}°</div>
          <div>Z: {robot.z.toFixed(1)} мм</div>
          <div>Tool: {robot.tool.toFixed(1)}°</div>
          <div>X: {robot.x.toFixed(1)} мм</div>
          <div>Y: {robot.y.toFixed(1)} мм</div>
        </div>
      </div>

      <div style={styles.right}>
        <div style={styles.card}>
          <h3>Позвенное управление</h3>
          {["j1", "j2", "z", "tool"].map((joint) => {
            const limit = LIMITS[joint];
            const label = joint.toUpperCase();
            const value = sliders[joint];
            const actual = robot[joint];

            return (
              <div key={joint} style={styles.sliderRow}>
                <div style={styles.sliderLabel}>
                  <span style={styles.jointName}>{label}</span>
                  <span style={styles.sliderValue}>
                    {value.toFixed(0)}
                    {limit.unit}
                    {Math.abs(value - actual) > 0.5 && (
                      <span style={styles.pending}>
                        {" "}
                        → {actual.toFixed(0)}
                        {limit.unit}
                      </span>
                    )}
                  </span>
                </div>
                <input
                  type="range"
                  min={limit.min}
                  max={limit.max}
                  step={limit.step}
                  value={sliders[joint]}
                  onChange={(e) =>
                    handleSliderChange(joint, parseFloat(e.target.value))
                  }
                  onInput={(e) =>
                    handleSliderRelease(joint, parseFloat(e.target.value))
                  }
                  onTouchEnd={(e) =>
                    handleSliderRelease(joint, parseFloat(e.target.value))
                  }
                  style={styles.slider}
                />
                <div style={styles.sliderLimits}>
                  <span>
                    {limit.min}
                    {limit.unit}
                  </span>
                  <span>
                    {limit.max}
                    {limit.unit}
                  </span>
                </div>
              </div>
            );
          })}
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
  sliderRow: { marginBottom: "16px" },
  sliderLabel: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "6px",
    fontSize: "14px",
  },
  jointName: { fontWeight: 600, color: "#374151" },
  sliderValue: {
    fontFamily: "monospace",
    background: "#f3f4f6",
    padding: "2px 8px",
    borderRadius: "6px",
  },
  pending: { color: "#6b7280", marginLeft: "4px", fontSize: "12px" },
  slider: { width: "100%", cursor: "pointer", accentColor: "#ef4444" },
  sliderLimits: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "11px",
    color: "#9ca3af",
    marginTop: "2px",
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
    fontWeight: 500,
  },
  badge: { fontWeight: 700 },
  state: {
    background: "#ffffff",
    border: "1px solid #e5e7eb",
    borderRadius: "16px",
    padding: "16px",
    display: "grid",
    gridTemplateColumns: "repeat(2, 1fr)",
    gap: "8px",
    fontSize: "14px",
  },
  errorBadge: {
    padding: "8px 12px",
    borderRadius: "8px",
    fontSize: "13px",
    fontWeight: 500,
    textAlign: "center",
    border: "1px solid #fecaca",
  },
};

export default App;
