import math

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from std_msgs.msg import Float64MultiArray
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
from control_msgs.action import FollowJointTrajectory
from sensor_msgs.msg import JointState
from builtin_interfaces.msg import Duration


class WebJointExecutor(Node):
    def __init__(self):
        super().__init__("web_joint_executor")

        self.joint_names = ["hand1_joint", "hand2_joint", "hand3_joint"]

        self.current_positions = {
            "hand1_joint": 0.0,
            "hand2_joint": 0.0,
            "hand3_joint": 0.0,
        }

        self.goal_sub = self.create_subscription(
            Float64MultiArray,
            "/scara/joint_goal",
            self.on_joint_goal,
            10,
        )

        self.joint_state_sub = self.create_subscription(
            JointState,
            "/joint_states",
            self.on_joint_states,
            10,
        )

        self.client = ActionClient(
            self,
            FollowJointTrajectory,
            "/scara_controller/follow_joint_trajectory",
        )

        self.motion_time_sec = 1.0

        self.get_logger().info("web_joint_executor готов")

    def on_joint_states(self, msg: JointState):
        for i, name in enumerate(msg.name):
            if name in self.current_positions and i < len(msg.position):
                self.current_positions[name] = msg.position[i]

    def on_joint_goal(self, msg: Float64MultiArray):
        if len(msg.data) < 3:
            self.get_logger().error("Получена joint_goal с недостаточным числом значений")
            return

        target_positions = list(msg.data[:3])

        self.get_logger().info(
            f"Получена joint-команда: "
            f"j1={target_positions[0]:.4f}, "
            f"j2={target_positions[1]:.4f}, "
            f"j3={target_positions[2]:.4f}"
        )

        current = [
            self.current_positions[self.joint_names[0]],
            self.current_positions[self.joint_names[1]],
            self.current_positions[self.joint_names[2]],
        ]

        traj = JointTrajectory()
        traj.joint_names = self.joint_names

        p0 = JointTrajectoryPoint()
        p0.positions = current
        p0.velocities = [0.0, 0.0, 0.0]
        p0.time_from_start = Duration(sec=0, nanosec=0)

        p1 = JointTrajectoryPoint()
        p1.positions = target_positions
        p1.velocities = [0.0, 0.0, 0.0]
        p1.time_from_start = Duration(sec=int(self.motion_time_sec), nanosec=0)

        traj.points = [p0, p1]

        goal = FollowJointTrajectory.Goal()
        goal.trajectory = traj

        if not self.client.wait_for_server(timeout_sec=1.0):
            self.get_logger().error("Action server /scara_controller/follow_joint_trajectory недоступен")
            return

        self.get_logger().info(
            f"Отправка joint-траектории: current={current}, target={target_positions}"
        )

        send_goal_future = self.client.send_goal_async(goal)
        send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if goal_handle is None:
            self.get_logger().error("Не удалось отправить goal")
            return

        if not goal_handle.accepted:
            self.get_logger().warn("Goal отклонен контроллером")
            return

        self.get_logger().info("Goal принят контроллером")
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.result_callback)

    def result_callback(self, future):
        result = future.result()
        if result is None:
            self.get_logger().error("Не удалось получить result")
            return

        status = result.status
        self.get_logger().info(f"Траектория завершена, status={status}")


def main(args=None):
    rclpy.init(args=args)
    node = WebJointExecutor()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()