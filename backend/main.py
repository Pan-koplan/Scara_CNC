import json
import math
import threading
import time
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from builtin_interfaces.msg import Duration

import rclpy
from rclpy.node import Node

app = FastAPI()

# ==================== КОНФИГУРАЦИЯ ====================
# Кинематика для цифрового двойника (в метрах)
L1 = 0.35  # длина первого звена, м
L2 = 0.35  # длина второго звена, м

# Лимиты суставов: {min, max, step, unit, ros_unit_factor}
JOINT_LIMITS = {
    "j1":   {"min": -135, "max": 135, "step": 0.1, "unit": "°", "ros_factor": math.pi/180},
    "j2":   {"min": -135, "max": 135, "step": 0.1, "unit": "°", "ros_factor": math.pi/180},
    "z":    {"min": 0,    "max": 200, "step": 0.5, "unit": " мм", "ros_factor": 0.001},  # мм → м
    "tool": {"min": -180, "max": 180, "step": 0.1, "unit": "°", "ros_factor": math.pi/180},
}

# Троттлинг: мин. интервал между публикациями в ROS (сек)
ROS_PUBLISH_INTERVAL = 0.05  # 20 Гц — достаточно для плавности

# ==================== ГЛОБАЛЬНОЕ СОСТОЯНИЕ ====================
# Текущее состояние робота (в единицах UI: градусы, мм)
robot_state = {
    "j1": 0.0,
    "j2": 0.0,
    "z": 0.0,
    "tool": 0.0,
}

# Время последней публикации в ROS (для троттлинга)
_last_ros_publish: dict[str, float] = {}

# ROS-нода и поток
ros_node: Optional[Node] = None
ros_thread: Optional[threading.Thread] = None


# ==================== УТИЛИТЫ ====================
def clamp(value: float, min_val: float, max_val: float) -> float:
    """Ограничение значения в диапазоне [min, max]."""
    return max(min_val, min(max_val, value))


def fk_deg(j1_deg: float, j2_deg: float) -> tuple[float, float]:
    """Прямая кинематика: углы в градусах → координаты в мм (для UI)."""
    j1 = math.radians(j1_deg)
    j2 = math.radians(j2_deg)
    x_mm = (L1 * math.cos(j1) + L2 * math.cos(j1 + j2)) * 1000
    y_mm = (L1 * math.sin(j1) + L2 * math.sin(j1 + j2)) * 1000
    return x_mm, y_mm


def to_ros_units(joint: str, value_ui: float) -> float:
    """Конвертация из UI-единиц в ROS-единицы (рад/м)."""
    factor = JOINT_LIMITS[joint]["ros_factor"]
    return value_ui * factor


def should_publish_ros(joint: str) -> bool:
    """Проверка троттлинга: можно ли публиковать команду в ROS."""
    now = time.time()
    last = _last_ros_publish.get(joint, 0)
    if now - last >= ROS_PUBLISH_INTERVAL:
        _last_ros_publish[joint] = now
        return True
    return False


# ==================== ROS NODE ====================
class WebBridgeNode(Node):
    def __init__(self):
        super().__init__("web_bridge_node")
        self.trajectory_pub = self.create_publisher(
            JointTrajectory, 
            "/scara_controller/joint_trajectory", 
            10
        )
        self.get_logger().info("✅ web_bridge_node готов")

    def publish_trajectory(self, joints: dict[str, float], time_sec: float = 0.5):
        """
        Публикация траектории в ros2_control.
        joints: {"j1": val, "j2": val, "z": val} — уже в ROS-единицах (рад/м)
        """
        msg = JointTrajectory()
        msg.joint_names = ["hand1_joint", "hand2_joint", "hand3_joint"]
        
        point = JointTrajectoryPoint()
        # Порядок должен соответствовать joint_names!
        point.positions = [
            joints.get("j1", 0.0),
            joints.get("j2", 0.0),
            joints.get("z", 0.0),
        ]
        point.time_from_start = Duration(sec=int(time_sec), nanosec=0)
        msg.points.append(point)
        
        self.trajectory_pub.publish(msg)
        self.get_logger().debug(f"📤 Published trajectory: {joints}")


def ros_spin():
    """Функция для потока rclpy.spin()."""
    if ros_node is not None:
        rclpy.spin(ros_node)


# ==================== FASTAPI ====================
@app.get("/")
def root():
    return FileResponse("/app/backend/static/index.html")


app.mount("/assets", StaticFiles(directory="/app/backend/static/assets"), name="assets")


@app.on_event("startup")
async def startup_event():
    global ros_node, ros_thread
    
    rclpy.init()
    ros_node = WebBridgeNode()
    
    ros_thread = threading.Thread(target=ros_spin, daemon=True)
    ros_thread.start()
    print("🚀 ROS 2 node started in background thread")


@app.on_event("shutdown")
async def shutdown_event():
    global ros_node
    
    if ros_node is not None:
        ros_node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()
    print("🛑 ROS 2 node shutdown")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("🔌 WebSocket connected")

    try:
        # Отправляем начальный статус
        x, y = fk_deg(robot_state["j1"], robot_state["j2"])
        await websocket.send_json({
            "type": "STATUS",
            **robot_state,
            "x": round(x, 2),
            "y": round(y, 2),
        })

        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            print(f"⬇️ WS RECV: {msg_type} — {msg}")

            # ==================== ОБРАБОТКА КОМАНД ====================
            
            # 1. Плавный джоггинг: изменение на дельту
            if msg_type == "JOINT_JOG":
                joint = msg["joint"]
                delta = float(msg["delta"])
                if joint in robot_state:
                    limits = JOINT_LIMITS[joint]
                    new_val = robot_state[joint] + delta
                    robot_state[joint] = clamp(new_val, limits["min"], limits["max"])
                    print(f"🕹️ JOG {joint}: {robot_state[joint]}")

            # 2. Абсолютное положение одного сустава (для ползунков)
            elif msg_type == "SET_JOINT":
                joint = msg["joint"]
                value = float(msg["value"])
                if joint in robot_state:
                    limits = JOINT_LIMITS[joint]
                    robot_state[joint] = clamp(value, limits["min"], limits["max"])
                    print(f"🎚️ SET {joint}: {robot_state[joint]}")

            # 3. Установка нескольких суставов сразу (пресеты)
            elif msg_type == "SET_JOINTS":
                for joint in ["j1", "j2", "z", "tool"]:
                    if joint in msg:
                        value = float(msg[joint])
                        limits = JOINT_LIMITS[joint]
                        robot_state[joint] = clamp(value, limits["min"], limits["max"])
                print(f"🎯 PRESET: {robot_state}")

            # 4. Возврат в домашнюю позицию
            elif msg_type == "HOME":
                for joint in robot_state:
                    robot_state[joint] = 0.0
                print("🏠 HOME")

            # ==================== ОТПРАВКА В РОС (с троттлингом) ====================
            # Публикуем в ROS только если прошёл мин. интервал
            if any(should_publish_ros(j) for j in ["j1", "j2", "z"]):
                # Конвертируем в ROS-единицы
                ros_cmd = {
                    "j1": to_ros_units("j1", robot_state["j1"]),
                    "j2": to_ros_units("j2", robot_state["j2"]),
                    "z":  to_ros_units("z",  robot_state["z"]),
                }
                
                if ros_node is not None:
                    ros_node.publish_trajectory(ros_cmd, time_sec=0.3)  # плавное движение за 300 мс

            # ==================== ОБРАТНАЯ СВЯЗЬ В UI ====================
            # Считаем координаты для цифрового двойника
            x, y = fk_deg(robot_state["j1"], robot_state["j2"])
            
            await websocket.send_json({
                "type": "STATUS",
                "j1": round(robot_state["j1"], 2),
                "j2": round(robot_state["j2"], 2),
                "z":  round(robot_state["z"], 2),
                "tool": round(robot_state["tool"], 2),
                "x": round(x, 2),
                "y": round(y, 2),
            })

    except WebSocketDisconnect:
        print("🔌 WebSocket disconnected")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🤖 SCARA Backend v2 — с плавным джоггингом и троттлингом")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")