import json
import math
import threading

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray

app = FastAPI()

state = {
    "j1": 0.0,    # degrees
    "j2": 0.0,    # degrees
    "z": 0.0,     # mm
    "tool": 0.0,  # degrees, пока только в UI
}

L1 = 0.35
L2 = 0.35

ros_node = None
ros_thread = None


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def fk(j1_deg, j2_deg):
    j1 = math.radians(j1_deg)
    j2 = math.radians(j2_deg)
    x = L1 * math.cos(j1) + L2 * math.cos(j1 + j2)
    y = L1 * math.sin(j1) + L2 * math.sin(j1 + j2)
    return x, y


class WebBridgeNode(Node):
    def __init__(self):
        super().__init__("web_bridge_node")
        self.pub = self.create_publisher(Float64MultiArray, "/scara/joint_goal", 10)
        self.get_logger().info("web_bridge_node готов")

    def publish_joint_command(self, cmd: dict):
        msg = Float64MultiArray()

        # j1, j2 в радианах, z в метрах
        msg.data = [
            float(cmd.get("j1", 0.0)),
            float(cmd.get("j2", 0.0)),
            float(cmd.get("z", 0.0)),
        ]

        self.pub.publish(msg)
        self.get_logger().info(
            f"Опубликована joint-команда: "
            f"j1={msg.data[0]:.4f} rad, "
            f"j2={msg.data[1]:.4f} rad, "
            f"z={msg.data[2]:.4f} m"
        )


def ros_spin():
    rclpy.spin(ros_node)


@app.on_event("startup")
async def startup_event():
    global ros_node, ros_thread

    rclpy.init()
    ros_node = WebBridgeNode()

    ros_thread = threading.Thread(target=ros_spin, daemon=True)
    ros_thread.start()


@app.on_event("shutdown")
async def shutdown_event():
    global ros_node

    if ros_node is not None:
        ros_node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        # отправим начальный статус
        x, y = fk(state["j1"], state["j2"])
        await websocket.send_json({
            "type": "STATUS",
            "j1": state["j1"],
            "j2": state["j2"],
            "z": state["z"],
            "tool": state["tool"],
            "x": x,
            "y": y,
        })

        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)

            print("WS RECV:", msg)

            if msg["type"] == "JOINT_JOG":
                joint = msg["joint"]
                delta = float(msg["delta"])
                if joint in state:
                    state[joint] += delta

            elif msg["type"] == "SET_JOINTS":
                for key in ["j1", "j2", "z", "tool"]:
                    if key in msg:
                        state[key] = float(msg[key])

            elif msg["type"] == "HOME":
                state["j1"] = 0.0
                state["j2"] = 0.0
                state["z"] = 0.0
                state["tool"] = 0.0

            # Ограничения
            state["j1"] = clamp(state["j1"], -180.0, 180.0)
            state["j2"] = clamp(state["j2"], -180.0, 180.0)
            state["z"] = clamp(state["z"], -100.0, 100.0)       # мм
            state["tool"] = clamp(state["tool"], -180.0, 180.0)

            # Для цифрового двойника считаем FK
            x, y = fk(state["j1"], state["j2"])

            # Для ROS публикуем суставы напрямую
            ros_cmd = {
                "j1": math.radians(state["j1"]),
                "j2": math.radians(state["j2"]),
                "z": state["z"] / 1000.0,   # мм -> м
            }

            print("ROS JOINT CMD:", ros_cmd)

            if ros_node is not None:
                ros_node.publish_joint_command(ros_cmd)

            await websocket.send_json({
                "type": "STATUS",
                "j1": state["j1"],
                "j2": state["j2"],
                "z": state["z"],
                "tool": state["tool"],
                "x": x,
                "y": y,
            })

    except WebSocketDisconnect:
        print("WebSocket disconnected")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)