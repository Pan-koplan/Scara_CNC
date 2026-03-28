#!/usr/bin/env python3
import math
import itertools
from typing import Dict, List, Tuple, Optional

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.duration import Duration

from std_msgs.msg import Int32MultiArray
from geometry_msgs.msg import PoseStamped, Twist
from nav2_msgs.action import NavigateToPose, Spin

import yaml


Point = Tuple[float, float, float]  # (x, y, yaw)


def yaw_to_quaternion(yaw: float):
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


def normalize_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def load_markers_yaml(path: str) -> Dict[int, Point]:
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    markers = data.get("markers", {})
    out: Dict[int, Point] = {}
    for k, v in markers.items():
        mid = int(k)
        x = float(v["x"])
        y = float(v["y"])
        yaw = float(v.get("yaw", 0.0))
        out[mid] = (x, y, yaw)
    return out


class FourArucoOptimalMission(Node):
    def __init__(self):
        super().__init__("four_aruco_optimal_mission")

        # --- params ---
        self.declare_parameter("aruco_map_yaml", "")
        self.declare_parameter("target_ids", [10, 20, 30, 40])
        self.declare_parameter("aruco_ids_topic", "/aruco_ids")

        self.declare_parameter("nav2_action", "/navigate_to_pose")
        self.declare_parameter("map_frame", "map")
        self.declare_parameter("nav_server_timeout_sec", 10.0)

        # approach (по YAML yaw) + сдвиг направления смещения
        self.declare_parameter("approach_distance", 1.0)
        self.declare_parameter("approach_yaw_offset", 0.0)   # ±pi/2 если подход "сбоку"
        self.declare_parameter("yaw_flip", False)             # yaw += pi
        self.declare_parameter("face_marker", True)           # goal yaw = yaw + pi (смотреть на маркер)

        # spinning / confirm
        self.declare_parameter("cmd_vel_topic", "/cmd_vel")
        self.declare_parameter("spin_speed", 1.0)            # используется только в fallback /cmd_vel
        self.declare_parameter("spin_timeout_sec", 30.0)
        self.declare_parameter("spin_hz", 10.0)
        self.declare_parameter("confirm_hits", 3)

        # Nav2 Spin action endpoints (пробуем оба, что есть в системе)
        self.declare_parameter("spin_action_candidates",
                               ["/spin", "/behavior_server/spin"])

        self.aruco_map_yaml = str(self.get_parameter("aruco_map_yaml").value)
        self.target_ids = [int(x) for x in self.get_parameter("target_ids").value]
        self.aruco_ids_topic = str(self.get_parameter("aruco_ids_topic").value)

        self.nav2_action = str(self.get_parameter("nav2_action").value)
        self.map_frame = str(self.get_parameter("map_frame").value)
        self.nav_server_timeout_sec = float(self.get_parameter("nav_server_timeout_sec").value)

        self.approach_distance = float(self.get_parameter("approach_distance").value)
        self.approach_yaw_offset = float(self.get_parameter("approach_yaw_offset").value)
        self.yaw_flip = bool(self.get_parameter("yaw_flip").value)
        self.face_marker = bool(self.get_parameter("face_marker").value)

        self.cmd_vel_topic = str(self.get_parameter("cmd_vel_topic").value)
        self.spin_speed = float(self.get_parameter("spin_speed").value)
        self.spin_timeout_sec = float(self.get_parameter("spin_timeout_sec").value)
        self.spin_hz = float(self.get_parameter("spin_hz").value)
        self.confirm_hits = int(self.get_parameter("confirm_hits").value)

        self.spin_action_candidates = [str(x) for x in self.get_parameter("spin_action_candidates").value]

        if not self.aruco_map_yaml:
            self.get_logger().error("Parameter 'aruco_map_yaml' is empty.")
            raise RuntimeError("aruco_map_yaml not set")

        self.all_markers: Dict[int, Point] = load_markers_yaml(self.aruco_map_yaml)

        missing = [mid for mid in self.target_ids if mid not in self.all_markers]
        if missing:
            self.get_logger().error(f"These target_ids are missing in YAML: {missing}")
            raise RuntimeError("missing target ids in map")

        # --- aruco subscription ---
        self.last_seen_ids: set[int] = set()
        self.create_subscription(Int32MultiArray, self.aruco_ids_topic, self.on_ids, 10)

        # --- cmd_vel fallback ---
        self.pub_cmd = self.create_publisher(Twist, self.cmd_vel_topic, 10)

        # --- nav2 action clients ---
        self.nav_client = ActionClient(self, NavigateToPose, self.nav2_action)

        # spin clients: создаём на кандидатов, выберем доступный при первом использовании
        self.spin_clients = [ActionClient(self, Spin, name) for name in self.spin_action_candidates]
        self._spin_client_idx: Optional[int] = None

        self.get_logger().info(
            f"Started. approach_distance={self.approach_distance}, yaw_offset={self.approach_yaw_offset}, "
            f"cmd_vel={self.cmd_vel_topic}, spin_candidates={self.spin_action_candidates}"
        )

    def on_ids(self, msg: Int32MultiArray):
        self.last_seen_ids = set(int(x) for x in msg.data)

    def stop_robot(self):
        t = Twist()
        t.linear.x = 0.0
        t.angular.z = 0.0
        self.pub_cmd.publish(t)

    @staticmethod
    def euclidean(p1: Point, p2: Point) -> float:
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    def compute_goal_from_marker(self, marker_pose: Point) -> Point:
        """
        Цель = точка перед маркером по yaw из YAML, но направление смещения можно повернуть через approach_yaw_offset.
        """
        x, y, yaw = marker_pose

        if self.yaw_flip:
            yaw = normalize_angle(yaw + math.pi)

        # смещение делаем по yaw + offset (обычно ±pi/2 если раньше подход был "сбоку")
        yaw_off = normalize_angle(yaw + self.approach_yaw_offset)

        d = self.approach_distance
        gx = x - d * math.cos(yaw_off)
        gy = y - d * math.sin(yaw_off)

        gyaw = yaw
        if self.face_marker:
            gyaw = normalize_angle(yaw + math.pi)

        return (gx, gy, gyaw)

    def find_optimal_order(self, points: List[Tuple[int, Point]]) -> List[Tuple[int, Point]]:
        start: Point = (0.0, 0.0, 0.0)
        best_perm: Optional[Tuple[Tuple[int, Point], ...]] = None
        best_len: Optional[float] = None

        for perm in itertools.permutations(points):
            length = 0.0
            cur = start
            for (_id, p) in perm:
                length += self.euclidean(cur, p)
                cur = p
            if best_len is None or length < best_len:
                best_len = length
                best_perm = perm

        self.get_logger().info(f"Best route length: {best_len:.3f} m")
        for i, (mid, (x, y, yaw)) in enumerate(best_perm):
            self.get_logger().info(f"  #{i+1}: id={mid}, x={x:.3f}, y={y:.3f}, yaw={yaw:.3f}")
        return list(best_perm)

    def send_goal(self, x: float, y: float, yaw: float) -> bool:
        if not self.nav_client.wait_for_server(timeout_sec=self.nav_server_timeout_sec):
            self.get_logger().error("Nav2 action server not available!")
            return False

        qx, qy, qz, qw = yaw_to_quaternion(yaw)

        pose = PoseStamped()
        pose.header.frame_id = self.map_frame
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.orientation.x = qx
        pose.pose.orientation.y = qy
        pose.pose.orientation.z = qz
        pose.pose.orientation.w = qw

        goal = NavigateToPose.Goal()
        goal.pose = pose

        self.get_logger().info(f"Sending goal: ({x:.2f}, {y:.2f}, yaw={yaw:.2f})")
        goal_future = self.nav_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, goal_future)

        goal_handle = goal_future.result()
        if not goal_handle or not goal_handle.accepted:
            self.get_logger().warn("Goal rejected")
            return False

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        self.get_logger().info("Goal completed")
        return True

    # --------- SPIN (preferred): Nav2 Spin action ----------
    def _get_working_spin_client(self) -> Optional[ActionClient]:
        if self._spin_client_idx is not None:
            return self.spin_clients[self._spin_client_idx]

        # попробуем найти доступный spin action
        for i, c in enumerate(self.spin_clients):
            if c.wait_for_server(timeout_sec=0.5):
                self._spin_client_idx = i
                self.get_logger().info(f"Using Nav2 Spin action: {self.spin_action_candidates[i]}")
                return c

        self.get_logger().warn(
            f"No Nav2 Spin action server found among {self.spin_action_candidates}. "
            f"Fallback to cmd_vel."
        )
        return None

    def _spin_tick_via_nav2(self, angle_rad: float, allowance_sec: float) -> Optional[object]:
        c = self._get_working_spin_client()
        if c is None:
            return None

        goal = Spin.Goal()
        goal.target_yaw = float(angle_rad)
        goal.time_allowance = Duration(seconds=float(allowance_sec)).to_msg()

        fut = c.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, fut)
        gh = fut.result()
        if not gh or not gh.accepted:
            return None
        return gh

    def spin_until_marker(self, marker_id: int) -> bool:
        """
        Пытаемся крутиться через Nav2 Spin action (чтобы не конфликтовать с controller/velocity_smoother).
        Если Spin action нет — fallback на прямой cmd_vel.
        Таймаут — по sim-time.
        """
        start = self.get_clock().now()
        timeout = Duration(seconds=self.spin_timeout_sec)
        period = 1.0 / max(1.0, self.spin_hz)

        self.get_logger().info(
            f"Spinning to find ArUco id={marker_id} (timeout {self.spin_timeout_sec:.1f}s sim-time)"
        )

        hits = 0

        # 1) Prefer Nav2 Spin
        spin_client = self._get_working_spin_client()
        if spin_client is not None:
            # крутимся маленькими шагами, чтобы можно было рано остановиться при обнаружении
            step = math.radians(30.0)          # 30° за тик
            allowance = 2.0                    # сколько секунд дать на этот шаг

            gh = None
            while rclpy.ok():
                if self.get_clock().now() - start > timeout:
                    break

                # если нет активного шага — отправим новый
                if gh is None:
                    gh = self._spin_tick_via_nav2(step, allowance)
                    if gh is None:
                        # если spin action вдруг стал недоступен, fallback на cmd_vel
                        self.get_logger().warn("Nav2 Spin goal rejected; fallback to cmd_vel.")
                        spin_client = None
                        break

                # обработаем /aruco_ids, /clock
                rclpy.spin_once(self, timeout_sec=period)

                if marker_id in self.last_seen_ids:
                    hits += 1
                    if hits >= self.confirm_hits:
                        # отменим текущий spin, чтобы остановиться сразу
                        try:
                            cf = gh.cancel_goal_async()
                            rclpy.spin_until_future_complete(self, cf, timeout_sec=0.5)
                        except Exception:
                            pass
                        self.get_logger().info(f"✅ Marker found: id={marker_id}")
                        return True
                else:
                    hits = 0

                # если шаг закончился — сбросим и отправим следующий
                try:
                    # неблокирующе проверять результат сложно; проще периодически сбрасывать
                    # через небольшой allowance: после него spin закончится сам
                    # поэтому просто обнулим gh, когда allowance прошло
                    # (по sim-time)
                    pass
                finally:
                    # грубо: каждые allowance секунд будем отправлять новый
                    if self.get_clock().now() - start > Duration(seconds=allowance):
                        gh = None

            return False

        # 2) Fallback: direct cmd_vel (может конфликтовать, но лучше чем ничего)
        twist = Twist()
        twist.linear.x = 0.0
        twist.angular.z = self.spin_speed

        while rclpy.ok():
            if self.get_clock().now() - start > timeout:
                break

            self.pub_cmd.publish(twist)
            rclpy.spin_once(self, timeout_sec=period)

            if marker_id in self.last_seen_ids:
                hits += 1
                if hits >= self.confirm_hits:
                    self.stop_robot()
                    self.get_logger().info(f"✅ Marker found: id={marker_id}")
                    return True
            else:
                hits = 0

        self.stop_robot()
        self.get_logger().warn(f"⚠️ Marker NOT found (timeout): id={marker_id}")
        return False

    def run(self):
        # 1) точки целей из YAML
        points: List[Tuple[int, Point]] = []
        for mid in self.target_ids:
            marker_pose = self.all_markers[mid]
            goal_pose = self.compute_goal_from_marker(marker_pose)
            points.append((mid, goal_pose))

            mx, my, myaw = marker_pose
            gx, gy, gyaw = goal_pose
            self.get_logger().info(
                f"id={mid} marker=({mx:.3f},{my:.3f},yaw={myaw:.3f}) "
                f"goal=({gx:.3f},{gy:.3f},yaw={gyaw:.3f}) "
                f"d={self.approach_distance:.2f} yaw_offset={self.approach_yaw_offset:.3f}"
            )

        # 2) оптимальный порядок
        order = self.find_optimal_order(points)

        # 3) ехать + подтверждать маркер вращением
        for mid, (x, y, yaw) in order:
            ok = self.send_goal(x, y, yaw)
            if not ok:
                self.get_logger().error("Stopping mission due to Nav2 failure")
                return
            self.spin_until_marker(mid)

        self.get_logger().info("Mission finished.")


def main(args=None):
    rclpy.init(args=args)
    node = FourArucoOptimalMission()
    try:
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.stop_robot()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
