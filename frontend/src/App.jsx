import React, { useState, useEffect, useRef } from 'react';
import ROSLIB from 'roslib';

const ros = new ROSLIB.Ros({ url: 'ws://localhost:9090' });

const cmdTopic = new ROSLIB.Topic({
  ros: ros,
  name: '/scara/goal_pose',
  messageType: 'geometry_msgs/Pose'
});

const sendMove = (x, y) => {
  const pose = new ROSLIB.Message({ position: { x, y, z: 0 } });
  cmdTopic.publish(pose);
};

function App() {
  // Координаты (X, Y) и Углы (A1, A2)
  const [pos, setPos] = useState({ x: 150, y: 50 });
  const [angles, setAngles] = useState({ a1: 45, a2: 45 });
  const [status, setStatus] = useState("Connecting...");
  const ws = useRef(null);

  const L1 = 100; 
  const L2 = 80;  
  const center = 200; 

  useEffect(() => {
    ws.current = new WebSocket(`ws://${window.location.hostname}:8000/ws`);
    ws.current.onopen = () => setStatus("Online");
    ws.current.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === "STATUS") {
        setAngles({ a1: data.a1, a2: data.a2 });
        setPos({ x: data.x, y: data.y }); // Обновляем текущую позицию из ответа бэкенда
      }
    };
    return () => ws.current?.close();
  }, []);

  const sendMove = (targetX, targetY) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'MOVE', x: targetX, y: targetY }));
    }
  };

  // Расчет визуальных координат
  const rad1 = (angles.a1 * Math.PI) / 180;
  const rad2 = ((angles.a1 + angles.a2) * Math.PI) / 180;
  const x1 = center + L1 * Math.cos(rad1);
  const y1 = center - L1 * Math.sin(rad1);
  const x2 = x1 + L2 * Math.cos(rad2);
  const y2 = y1 - L2 * Math.sin(rad2);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', padding: '20px', fontFamily: 'Arial' }}>
      <div style={{ display: 'flex', gap: '40px' }}>
        {/* Визуализация */}
        <div>
          <h1>SCARA 2D Twin</h1>
          <div style={{ color: status === "Online" ? 'green' : 'red', fontWeight: 'bold' }}>Status: {status}</div>
          
          <svg width="400" height="400" style={{ background: '#1a202c', borderRadius: '8px', marginTop: '10px' }}>
            {/* Сетка для наглядности */}
            <defs>
              <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#2d3748" strokeWidth="0.5"/>
              </pattern>
            </defs>
            <rect width="400" height="400" fill="url(#grid)" />
            
            <circle cx={center} cy={center} r="5" fill="white" />
            <line x1={center} y1={center} x2={x1} y2={y1} stroke="#4fd1c5" strokeWidth="8" strokeLinecap="round" />
            <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="#f6ad55" strokeWidth="6" strokeLinecap="round" />
            <circle cx={x2} cy={y2} r="6" fill="#fc8181" />
          </svg>
        </div>

        {/* Панель управления */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', paddingTop: '60px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <h4>Presets</h4>
            <button onClick={() => sendMove(150, 50)} style={btnStyle}>Move to A</button>
            <button onClick={() => sendMove(50, 150)} style={btnStyle}>Move to B</button>
            <button onClick={() => sendMove(100, -100)} style={btnStyle}>Move to C</button>
          </div>

          <div style={{ borderTop: '1px solid #ccc', paddingTop: '10px' }}>
            <h4>Manual Jogging (10mm)</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 40px)', gap: '5px' }}>
              <div />
              <button onClick={() => sendMove(pos.x, pos.y + 10)} style={jogStyle}>Y+</button>
              <div />
              <button onClick={() => sendMove(pos.x - 10, pos.y)} style={jogStyle}>X-</button>
              <div />
              <button onClick={() => sendMove(pos.x + 10, pos.y)} style={jogStyle}>X+</button>
              <div />
              <button onClick={() => sendMove(pos.x, pos.y - 10)} style={jogStyle}>Y-</button>
              <div />
            </div>
          </div>

          <div style={{ fontSize: '14px', color: '#666', background: '#f7fafc', padding: '10px', borderRadius: '4px' }}>
            <strong>Current State:</strong><br/>
            X: {pos.x.toFixed(1)}, Y: {pos.y.toFixed(1)}<br/>
            A1: {angles.a1.toFixed(1)}°, A2: {angles.a2.toFixed(1)}°
          </div>
        </div>
      </div>
    </div>
  );
}

const btnStyle = { padding: '10px', cursor: 'pointer', background: '#2d3748', color: 'white', border: 'none', borderRadius: '4px' };
const jogStyle = { ...btnStyle, padding: '5px', fontSize: '12px' };

export default App;
