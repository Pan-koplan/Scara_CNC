#!/usr/bin/env python3
import math
import itertools
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import yaml

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from std_msgs.msg import Int32MultiArray


# ---------------- utils ----------------

def yaw_to_quaternion(yaw: float):
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


def dist2d(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


@dataclass(frozen=True)
class MarkerGoal:
    marker_id: int
    x: float
    y: float
    yaw: float


# ---------------- node ----------------

class NavArucoFourOptimal(Node):
    def __init__(self):
        super().__init__("nav_aruco_four_optimal")

        # ---------- parameters ----------
        self.declare_parameter("aruco_map_file", "")
        self.declare_parameter("marker_ids", [10, 20, 30, 40])
        self.declare_parameter("aruco_ids_topic", "/aruco_ids")
        self.declare_parameter("confirm_timeout_sec", 10.0)
        self.declare_parameter("start_x", 0.0)
        self.declare_parameter("start_y", 0.0)

        self.map_file = self.get_parameter("aruco_map_file").value
        self.marker_ids = list(self.get_parameter("marker_ids").value)
        self.aruco_ids_topic = self.get_parameter("aruco_ids_topic").value
        self.confirm_timeout = float(self.get_parameter("confirm_timeout_sec").value)
        self.start_x = float(self.get_parameter("start_x").value)
        self.start_y = float(self.get_parameter("start_y").value)

        # ---------- load map ----------
        self.aruco_map = self.load_aruco_map(self.map_file)
        self.goals = self.build_goals(self.marker_ids)

        # ---------- aruco confirmation ----------
        self._seen_ids: set[int] = set()
        self._ids_lock = threading.Lock()
        self._ids_event = threading.Event()

        self.create_subscription(
            Int32MultiArray,
            self.aruco_ids_topic,
            self.on_aruco_ids,
            10,
        )

        # ---------- nav2 ----------
        self.client = ActionClient(self, NavigateToPose, "/navigate_to_pose")

    # ---------- map ----------

    def load_aruco_map(self, path: str) -> Dict[int, dict]:
        if not path:
            raise RuntimeError("Parameter 'aruco_map_file' is empty")

        with open(path, "r") as f:
            data = yaml.safe_load(f)

        markers = {}
        for mid, pose in data["markers"].items():
            markers[int(mid)] = pose

        self.get_logger().info(f"Loaded {len(markers)} ArUco markers from map")
        return markers

    def build_goals(self, ids: List[int]) -> List[MarkerGoal]:
        goals: List[MarkerGoal] = []

        for mid in ids:
            if mid not in self.aruco_map:
                self.get_logger().error(f"Marker {mid} not found in map")
                continue

            m = self.aruco_map[mid]
            goals.append(
                MarkerGoal(
                    marker_id=mid,
                    x=float(m["x"]),
                    y=float(m["y"]),
                    yaw=float(m["yaw"]),
                )
            )

        self.get_logger().info("Selected markers:")
        for g in goals:
            self.get_logger().info(
                f"  id={g.marker_id} -> ({g.x:.2f}, {g.y:.2f}, yaw={g.yaw:.2f})"
            )
        return goals

    # ---------- aruco ids ----------

    def on_aruco_ids(self, msg: Int32MultiArray):
        with self._ids_lock:
            self._seen_ids = set(int(x) for x in msg.data)
        self._ids_event.set()

    def wait_for_confirmation(self, marker_id: int) -> bool:
        deadline = (
            self.get_clock().now().nanoseconds
            + int(self.confirm_timeout * 1e9)
        )

        while self.get_clock().now().nanoseconds < deadline:
            self._ids_event.wait(timeout=0.5)
            self._ids_event.clear()

            with self._ids_lock:
                if marker_id in self._seen_ids:
                    return True

            rclpy.spin_once(self, timeout_sec=0.0)

        return False

    # ---------- routing ----------

    def find_optimal_order(self) -> List[MarkerGoal]:
        start = (self.start_x, self.start_y)

        best_len: Optional[float] = None
        best_perm: Optional[Tuple[MarkerGoal, ...]] = None

        for perm in itertools.permutations(self.goals):
            length = 0.0
            cx, cy = start

            for g in perm:
                length += dist2d(cx, cy, g.x, g.y)
                cx, cy = g.x, g.y

            if best_len is None or length < best_len:
                best_len = length
                best_perm = perm

        assert best_perm is not None

        self.get_logger().info(f"Optimal route length: {best_len:.3f} m")
        self.get_logger().info("Optimal visiting order:")
        for i, g in enumerate(best_perm, 1):
            self.get_logger().info(f"  #{i}: marker {g.marker_id}")

        return list(best_perm)

    # ---------- nav ----------

    def send_goal(self, g: MarkerGoal) -> bool:
        if not self.client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Nav2 action server not available")
            return False

        qx, qy, qz, qw = yaw_to_quaternion(g.yaw)

        pose = PoseStamped()
        pose.header.frame_id = "map"
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = g.x
        pose.pose.position.y = g.y
        pose.pose.orientation.x = qx
        pose.pose.orientation.y = qy
        pose.pose.orientation.z = qz
        pose.pose.orientation.w = qw

        goal = NavigateToPose.Goal()
        goal.pose = pose

        self.get_logger().info(f"Navigating to marker {g.marker_id}")
        future = self.client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)

        handle = future.result()
        if not handle or not handle.accepted:
            self.get_logger().error("Goal rejected")
            return False

        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        self.get_logger().info("Nav2 goal reached")
        return True

    # ---------- run ----------

    def run(self):
        if len(self.goals) != 4:
            self.get_logger().error("Exactly 4 markers must be selected")
            return

        route = self.find_optimal_order()

        for g in route:
            if not self.send_goal(g):
                break

            if self.wait_for_confirmation(g.marker_id):
                self.get_logger().info(
                    f"✅ Arrived at marker {g.marker_id} (confirmed by vision)"
                )
            else:
                self.get_logger().warn(
                    f"⚠️ Marker {g.marker_id} not confirmed by camera"
                )


# ---------------- main ----------------

def main(args=None):
    rclpy.init(args=args)
    node = NavArucoFourOptimal()
    try:
        node.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
