import { useEffect, useRef, useState } from "react";
import "./App.css";

const WS_URL = `ws://${window.location.hostname}:8000/ws`;

function App() {
  const wsRef = useRef(null);

  const [connected, setConnected] = useState(false);
  const [status, setStatus] = useState("Нет соединения");
  const [lastResponse, setLastResponse] = useState(null);

  const [x, setX] = useState("0.65");
  const [y, setY] = useState("-0.15");

  useEffect(() => {
    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const connectWebSocket = () => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setStatus("Соединение установлено");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLastResponse(data);

        if (data.type === "ACK") {
          setStatus(`Команда выполнена: ${data.message}`);
        } else if (data.type === "ERROR") {
          setStatus(`Ошибка: ${data.message}`);
        } else if (data.type === "STATE") {
          setStatus("Состояние робота обновлено");
        } else {
          setStatus("Получен ответ от сервера");
        }
      } catch {
        setStatus("Получено некорректное сообщение");
      }
    };

    ws.onclose = () => {
      setConnected(false);
      setStatus("Соединение закрыто");
    };

    ws.onerror = () => {
      setConnected(false);
      setStatus("Ошибка WebSocket");
    };
  };

  const sendMessage = (payload) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      setStatus("WebSocket не подключен");
      return;
    }

    wsRef.current.send(JSON.stringify(payload));
  };

  const sendPreset = (name) => {
    sendMessage({
      type: "PRESET",
      name,
    });
  };

  const sendMove = () => {
    const parsedX = Number(x);
    const parsedY = Number(y);

    if (Number.isNaN(parsedX) || Number.isNaN(parsedY)) {
      setStatus("Некорректные координаты");
      return;
    }

    sendMessage({
      type: "MOVE",
      x: parsedX,
      y: parsedY,
    });
  };

  const requestState = () => {
    sendMessage({
      type: "GET_STATE",
    });
  };

  return (
    <div className="app">
      <div className="container">
        <header className="header">
          <div>
            <h1>SCARA Control Panel</h1>
            <p>Базовый веб-интерфейс управления манипулятором</p>
          </div>

          <div className={`badge ${connected ? "online" : "offline"}`}>
            {connected ? "Подключено" : "Не подключено"}
          </div>
        </header>

        <section className="card">
          <h2>Быстрые команды</h2>
          <div className="button-row">
            <button onClick={() => sendPreset("HOME")}>Домой</button>
            <button onClick={() => sendPreset("POINT_A")}>Точка A</button>
            <button onClick={() => sendPreset("POINT_B")}>Точка B</button>
          </div>
        </section>

        <section className="card">
          <h2>Ручное задание координат</h2>
          <div className="input-row">
            <label>
              X
              <input
                type="number"
                step="0.01"
                value={x}
                onChange={(e) => setX(e.target.value)}
              />
            </label>

            <label>
              Y
              <input
                type="number"
                step="0.01"
                value={y}
                onChange={(e) => setY(e.target.value)}
              />
            </label>
          </div>

          <div className="button-row">
            <button onClick={sendMove}>Отправить XY</button>
            <button className="secondary" onClick={requestState}>
              Запросить состояние
            </button>
          </div>
        </section>

        <section className="card">
          <h2>Статус</h2>
          <div className="status-box">{status}</div>
        </section>

        <section className="card">
          <h2>Последний ответ сервера</h2>
          <pre className="response-box">
            {lastResponse
              ? JSON.stringify(lastResponse, null, 2)
              : "Ответов пока нет"}
          </pre>
        </section>
      </div>
    </div>
  );
}

export default App;
