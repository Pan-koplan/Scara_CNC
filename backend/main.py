# backend/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json
import math

app = FastAPI()

# Эмуляция параметров робота
L1, L2 = 200, 200

def calculate_ik(x, y):
    # Обратная кинематика (углы для SCARA)
    try:
        d2 = (x**2 + y**2 - L1**2 - L2**2) / (2 * L1 * L2)
        angle2 = math.acos(max(-1, min(1, d2)))
        angle1 = math.atan2(y, x) - math.atan2(L2 * math.sin(angle2), L1 + L2 * math.cos(angle2))
        return math.degrees(angle1), math.degrees(angle2)
    except:
        return 0, 0

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("\n[INFO] Клиент подключился к WebSocket")
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            if msg.get('type') == 'MOVE':
                x, y = float(msg['x']), float(msg['y'])
                a1, a2 = calculate_ik(x, y)
                
                # Имитация отправки в ESP32
                gcode = f"G1 X{a1:.2f} Y{a2:.2f} F3000"
                
                print(f"\n--- РОБОТ ИСПОЛНЯЕТ ---")
                print(f"Цель: X:{x} Y:{y}")
                print(f"G-код: {gcode}")
                print(f"----------------------")
                
                # Отправляем ответ фронтенду для отрисовки
                await websocket.send_json({
                    "type": "STATUS",
                    "a1": a1,
                    "a2": a2,
                    "x": x,
                    "y": y
                })
    except WebSocketDisconnect:
        print("[INFO] Клиент отключился")
if __name__ == "__main__":
    import uvicorn
    # 8000 — порт, который мы пробросили в docker-compose
    uvicorn.run(app, host="0.0.0.0", port=8000)
