import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Point


class WebGoalListener(Node):
    def __init__(self):
        super().__init__("web_goal_listener")
        self.subscription = self.create_subscription(
            Point,
            "/scara/goal_xy",
            self.goal_callback,
            10
        )

    def goal_callback(self, msg: Point):
        self.get_logger().info(f"Received goal: x={msg.x}, y={msg.y}")
        # здесь позже будет вызов MoveIt
        # пока просто лог


def main(args=None):
    rclpy.init(args=args)
    node = WebGoalListener()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()