#!/usr/bin/env python3
import math
import random
import itertools
from typing import List, Tuple

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose


def yaw_to_quaternion(yaw: float):
    """Convert yaw angle (rad) to quaternion (x, y, z, w)."""
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


Point = Tuple[float, float, float]  # (x, y, yaw)


class OptimalFourPointNavigator(Node):
    def __init__(self):
        super().__init__('optimal_four_point_navigator')
        self.client = ActionClient(self, NavigateToPose, '/navigate_to_pose')

    def send_goal(self, x: float, y: float, yaw: float) -> bool:
        """Send single Nav2 goal and wait until it is finished."""
        if not self.client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Nav2 action server not available!")
            return False

        qx, qy, qz, qw = yaw_to_quaternion(yaw)

        pose = PoseStamped()
        pose.header.frame_id = 'map'
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
        goal_future = self.client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, goal_future)

        goal_handle = goal_future.result()
        if not goal_handle or not goal_handle.accepted:
            self.get_logger().warn("Goal rejected")
            return False

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        result = result_future.result()
        if result is None:
            self.get_logger().warn("Goal finished with unknown result")
        else:
            self.get_logger().info("Goal completed")

        return True

    @staticmethod
    def euclidean_distance(p1: Point, p2: Point) -> float:
        """2D distance ignoring yaw."""
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    def generate_random_points(self) -> List[Point]:
        """
        Generate 4 random points in map coordinates.
        Диапазон можно подстроить под твой мир.
        """
        points: List[Point] = []

        # Например, вокруг центра карты: [-1.5, 1.5] м
        min_xy = -1.5
        max_xy = 1.5

        for i in range(4):
            x = random.uniform(min_xy, max_xy)
            y = random.uniform(min_xy, max_xy)
            yaw = random.uniform(-math.pi, math.pi)
            points.append((x, y, yaw))

        self.get_logger().info("Generated 4 random points:")
        for i, (x, y, yaw) in enumerate(points):
            self.get_logger().info(f"  P{i + 1}: x={x:.2f}, y={y:.2f}, yaw={yaw:.2f}")
        return points

    def find_optimal_route(self, points: List[Point]) -> List[Point]:
        """
        Find the shortest route visiting all points exactly once.
        Старт считаем из (0, 0, 0) для оценки длины маршрута.
        Возвращаем упорядоченный список точек.
        """
        if len(points) != 4:
            self.get_logger().warn("Expected exactly 4 points, got %d", len(points))

        start: Point = (0.0, 0.0, 0.0)

        best_order: Tuple[Point, ...] | None = None
        best_length: float | None = None

        for perm in itertools.permutations(points):
            length = 0.0
            current = start

            for p in perm:
                length += self.euclidean_distance(current, p)
                current = p

            if best_length is None or length < best_length:
                best_length = length
                best_order = perm

        self.get_logger().info(f"Best route length: {best_length:.3f} m")

        self.get_logger().info("Best order of visiting points:")
        for i, (x, y, yaw) in enumerate(best_order):
            self.get_logger().info(f"  #{i + 1}: x={x:.2f}, y={y:.2f}, yaw={yaw:.2f}")

        return list(best_order)


def main(args=None):
    rclpy.init(args=args)
    node = OptimalFourPointNavigator()

    # 1) генерируем 4 случайные точки
    points = node.generate_random_points()

    # 2) ищем оптимальный порядок посещения
    optimal_route = node.find_optimal_route(points)

    # 3) отправляем цели в Nav2 последовательно
    for (x, y, yaw) in optimal_route:
        ok = node.send_goal(x, y, yaw)
        if not ok:
            node.get_logger().error("Stopping route execution due to failure")
            break

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
