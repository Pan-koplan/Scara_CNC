#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose


def yaw_to_quaternion(yaw: float):
    """Преобразует yaw в кватернион."""
    return (
        0.0,                               # x
        0.0,                               # y
        math.sin(yaw / 2.0),               # z
        math.cos(yaw / 2.0)                # w
    )


class ThreePointNavigator(Node):
    """Простая нода для отправки роботу трёх точек."""
    def __init__(self):
        super().__init__('three_point_navigator')

        # Action клиент навигации
        self.action_name = '/navigate_to_pose'
        self.client = ActionClient(self, NavigateToPose, self.action_name)

        self.get_logger().info("Navigator node initialized.")

    def send_goal(self, x: float, y: float, yaw: float):
        """Отправка цели в Nav2."""
        self.get_logger().info(
            f"Waiting for action server '{self.action_name}'..."
        )

        if not self.client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error("Nav2 action server not available!")
            return None, False

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

        self.get_logger().info(
            f"Sending goal: ({x:.2f}, {y:.2f}), yaw={yaw:.2f}"
        )

        send_future = self.client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send_future)
        goal_handle = send_future.result()

        if not goal_handle.accepted:
            self.get_logger().warn("Goal rejected.")
            return None, False

        self.get_logger().info("Goal accepted, waiting for result...")
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result()

        self.get_logger().info("Goal completed.")
        return result, True


def main(args=None):
    rclpy.init(args=args)
    node = ThreePointNavigator()

    points = [
        (0.0, 0.0, 0.0),
        (2.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
        (0.0, 0.0, 0.0),
    ]

    node.get_logger().info("Starting navigation through 3 points...")

    for x, y, yaw in points:
        result, ok = node.send_goal(x, y, yaw)
        if not ok:
            node.get_logger().error("Stopping sequence — goal failed.")
            break

    node.get_logger().info("Sequence finished.")
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
