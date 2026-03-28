#!/usr/bin/env python3
import math
import os
import time
from typing import Dict, List, Tuple

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from ament_index_python.packages import get_package_share_directory

from geometry_msgs.msg import PoseStamped, Quaternion, Twist
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
from std_msgs.msg import Int32MultiArray

import yaml


def yaw_to_quaternion(yaw: float) -> Quaternion:
    q = Quaternion()
    q.w = math.cos(yaw / 2.0)
    q.x = 0.0
    q.y = 0.0
    q.z = math.sin(yaw / 2.0)
    return q


class NavArucoToId(Node):
    """
    Скрипт №2: движение к маркеру по его ID, даже если маркер сдвинули.

    Логика:
      1) Берём initial guess по координатам маркера из aruco_map.yaml.
      2) Едем туда через Nav2.
      3) Если маркер не виден, начинаем поиск:
         - вращаемся на месте, пока ID не появится в /aruco/ids
         - (позже можно добавить спираль / дополнительные шаги)
    """

    def __init__(self):
        super().__init__('nav_aruco_to_id')

        # --- параметры ---
        pkg_share = get_package_share_directory('turtlebot_nav_tasks')
        default_map_path = os.path.join(pkg_share, 'aruco_map.yaml')

        self.declare_parameter('aruco_map_path', default_map_path)
        self.declare_parameter('target_marker_id', 40)
        self.declare_parameter('arrival_timeout', 60.0)
        self.declare_parameter('search_timeout', 120.0)
        self.declare_parameter('search_angular_speed', 0.5)  # rad/s

        aruco_map_path = self.get_parameter('aruco_map_path').get_parameter_value().string_value
        self.target_marker_id = self.get_parameter('target_marker_id').get_parameter_value().integer_value
        self.arrival_timeout = self.get_parameter('arrival_timeout').get_parameter_value().double_value
        self.search_timeout = self.get_parameter('search_timeout').get_parameter_value().double_value
        self.search_angular_speed = self.get_parameter('search_angular_speed').get_parameter_value().double_value

        self.get_logger().info(f"Target marker ID: {self.target_marker_id}")
        self.get_logger().info(f"ArUco map: {aruco_map_path}")

        # --- карта маркеров ---
        self.markers = self.load_aruco_map(aruco_map_path)
        if self.target_marker_id not in self.markers:
            self.get_logger().error(
                f"Marker {self.target_marker_id} not found in aruco_map.yaml"
            )

        # --- Nav2 ---
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # --- текущие ID маркеров ---
        self.current_ids: List[int] = []
        self.create_subscription(
            Int32MultiArray,
            '/aruco/ids',
            self.aruco_ids_callback,
            10
        )

        # --- одометрия (может пригодиться позже) ---
        self.current_pose: Tuple[float, float] = (0.0, 0.0)
        self.create_subscription(
            Odometry,
            '/odom',
            self.odom_callback,
            10
        )

        # --- управление вращением ---
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # запуск основной логики один раз
        self._started = False
        self.create_timer(2.0, self.start_once)

    # -------- callbacks --------

    def aruco_ids_callback(self, msg: Int32MultiArray):
        self.current_ids = list(msg.data)

    def odom_callback(self, msg: Odometry):
        self.current_pose = (
            msg.pose.pose.position.x,
            msg.pose.pose.position.y
        )

    # -------- helpers --------

    def load_aruco_map(self, path: str) -> Dict[int, Dict[str, float]]:
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            self.get_logger().error(f"Failed to load ArUco map yaml: {e}")
            return {}

        markers_raw = data.get('markers', {})
        markers: Dict[int, Dict[str, float]] = {}
        for k, v in markers_raw.items():
            try:
                mid = int(k)
            except ValueError:
                mid = int(v.get('id', -1))
            if mid < 0:
                continue
            markers[mid] = {
                'x': float(v.get('x', 0.0)),
                'y': float(v.get('y', 0.0)),
                'z': float(v.get('z', 0.0)),
                'yaw': float(v.get('yaw', 0.0)),
            }
        return markers

    def wait_for_nav2(self) -> bool:
        self.get_logger().info("Waiting for Nav2 action server...")
        if not self.nav_client.wait_for_server(timeout_sec=30.0):
            self.get_logger().error("Nav2 action server not available!")
            return False
        self.get_logger().info("Nav2 action server is ready.")
        return True

    def build_goal(self, x: float, y: float, yaw: float) -> NavigateToPose.Goal:
        goal = NavigateToPose.Goal()
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0
        pose.pose.orientation = yaw_to_quaternion(yaw)
        goal.pose = pose
        return goal

    def send_goal_and_wait(self, goal: NavigateToPose.Goal) -> bool:
        send_future = self.nav_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send_future)
        goal_handle = send_future.result()
        if not goal_handle.accepted:
            self.get_logger().warn("Goal rejected by Nav2")
            return False
        self.get_logger().info("Goal accepted, waiting for result...")
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result()
        if result.status != 4:  # SUCCEEDED
            self.get_logger().warn(f"Goal finished with status {result.status}")
            return False
        self.get_logger().info("Goal reached (Nav2).")
        return True

    def wait_for_marker_id(self, marker_id: int, timeout: float) -> bool:
        """
        Ждём, пока нужный ID появится в /aruco/ids.
        """
        self.get_logger().info(
            f"Waiting for ArUco ID {marker_id} for up to {timeout:.1f} seconds..."
        )
        start = self.get_clock().now()

        while rclpy.ok():
            if marker_id in self.current_ids:
                self.get_logger().info(f"ArUco ID {marker_id} detected!")
                return True

            elapsed = (self.get_clock().now() - start).nanoseconds * 1e-9
            if elapsed > timeout:
                self.get_logger().warn(f"Timeout waiting for ID {marker_id}")
                return False

            time.sleep(0.1)

    def rotate_search(self, marker_id: int, timeout: float) -> bool:
        """
        Простой поиск: вращаемся на месте, пока не увидим нужный ID.
        """
        self.get_logger().info(
            f"Starting rotation search for marker {marker_id} (timeout {timeout:.1f}s)..."
        )
        start = self.get_clock().now()

        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = self.search_angular_speed

        rate_hz = 20.0
        dt = 1.0 / rate_hz

        while rclpy.ok():
            if marker_id in self.current_ids:
                self.get_logger().info(f"Marker {marker_id} detected during search!")
                # остановиться
                stop = Twist()
                self.cmd_vel_pub.publish(stop)
                return True

            elapsed = (self.get_clock().now() - start).nanoseconds * 1e-9
            if elapsed > timeout:
                self.get_logger().warn(f"Search timeout, marker {marker_id} not found.")
                stop = Twist()
                self.cmd_vel_pub.publish(stop)
                return False

            self.cmd_vel_pub.publish(twist)
            time.sleep(dt)

    # -------- main logic --------

    def start_once(self):
        if self._started:
            return
        self._started = True
        self.get_logger().info("Starting NavArucoToId task...")
        self.run_task()

    def run_task(self):
        if self.target_marker_id not in self.markers:
            self.get_logger().error("Target marker not in map, aborting.")
            return

        if not self.wait_for_nav2():
            return

        m = self.markers[self.target_marker_id]
        x = m['x']
        y = m['y']
        yaw = m['yaw']

        self.get_logger().info(
            f"Initial navigation to marker {self.target_marker_id} at "
            f"({x:.2f}, {y:.2f}), yaw={yaw:.2f}"
        )

        goal = self.build_goal(x, y, yaw)
        reached = self.send_goal_and_wait(goal)

        if not reached:
            self.get_logger().warn("Failed to reach initial marker position via Nav2.")

        # после прибытия или неуспеха — ждём ID прямо здесь
        if self.wait_for_marker_id(self.target_marker_id, self.arrival_timeout):
            self.get_logger().info("Marker detected at initial position, done.")
            return

        # если не увидели — начинаем поиск
        self.rotate_search(self.target_marker_id, self.search_timeout)

        self.get_logger().info("NavArucoToId task finished.")


def main(args=None):
    rclpy.init(args=args)
    node = NavArucoToId()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
