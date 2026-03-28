from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
import threading
from typing import Optional

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point
from sensor_msgs.msg import JointState

app = FastAPI()


class RosBridge(Node):
    PRESETS = {
        "HOME": {"x": 0.70, "y": -0.20},
        "POINT_A": {"x": 0.65, "y": -0.15},
        "POINT_B": {"x": 0.60, "y": -0.25},
    }

    def __init__(self):
        super().__init__("scara_web_bridge")

        self.goal_pub = self.create_publisher(Point, "/scara/goal_xy", 10)
        self.joint_sub = self.create_subscription(
            JointState,
            "/joint_states",
            self.joint_states_callback,
            10,
        )

        self.latest_joint_state: Optional[dict] = None

    def publish_goal(self, x: float, y: float):
        msg = Point()
        msg.x = float(x)
        msg.y = float(y)
        msg.z = 0.0
        self.goal_pub.publish(msg)

    def joint_states_callback(self, msg: JointState):
        self.latest_joint_state = {
            "name": list(msg.name),
            "position": list(msg.position),
            "velocity": list(msg.velocity),
            "effort": list(msg.effort),
        }


ros_node: Optional[RosBridge] = None


def ros_spin():
    global ros_node
    rclpy.init()
    ros_node = RosBridge()
    rclpy.spin(ros_node)
    ros_node.destroy_node()
    rclpy.shutdown()


@app.on_event("startup")
async def startup_event():
    thread = threading.Thread(target=ros_spin, daemon=True)
    thread.start()
    await asyncio.sleep(1.0)


@app.get("/")
async def root():
    return {"status": "backend is running"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "MOVE":
                x = data.get("x", 0.0)
                y = data.get("y", 0.0)

                if ros_node is not None:
                    ros_node.publish_goal(x, y)

                await websocket.send_json({
                    "type": "ACK",
                    "message": "goal sent to ROS",
                    "x": x,
                    "y": y,
                })

            elif msg_type == "PRESET":
                name = data.get("name")

                if ros_node is not None and name in ros_node.PRESETS:
                    x = ros_node.PRESETS[name]["x"]
                    y = ros_node.PRESETS[name]["y"]
                    ros_node.publish_goal(x, y)

                    await websocket.send_json({
                        "type": "ACK",
                        "message": f"preset {name} sent",
                        "x": x,
                        "y": y,
                    })
                else:
                    await websocket.send_json({
                        "type": "ERROR",
                        "message": "unknown preset"
                    })

            elif msg_type == "GET_STATE":
                await websocket.send_json({
                    "type": "STATE",
                    "joint_states": ros_node.latest_joint_state if ros_node else None
                })

            else:
                await websocket.send_json({
                    "type": "ERROR",
                    "message": f"unknown message type: {msg_type}"
                })

    except WebSocketDisconnect:
        pass
