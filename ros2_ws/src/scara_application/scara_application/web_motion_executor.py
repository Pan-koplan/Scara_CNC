#!/usr/bin/env python3
import math
import time

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import Point
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint
from builtin_interfaces.msg import Duration


ARM_JOINT_NAMES = ['hand1_joint', 'hand2_joint', 'hand3_joint']

# Геометрия
LINK1 = 0.25
LINK2 = 0.245

# Смещение базы в мире
ROBOT_OFFSET_X = 0.7
ROBOT_OFFSET_Y = -0.5
ROBOT_OFFSET_Z = 1.0

# Пока фиксированная высота
TARGET_WORLD_Z = 1.0


class WebMotionExecutor(Node):
    def __init__(self):
        super().__init__('web_motion_executor')

        self.subscription = self.create_subscription(
            Point,
            '/scara/goal_xy',
            self.goal_callback,
            10
        )

        self.arm_client = ActionClient(
            self,
            FollowJointTrajectory,
            '/scara_controller/follow_joint_trajectory'
        )

        self.get_logger().info('Ожидание action-сервера scara_controller...')
        self.arm_client.wait_for_server()
        self.get_logger().info('web_motion_executor готов')

    def inverse_kinematics(self, x, y, z):
        l1 = LINK1
        l2 = LINK2
        max_reach = l1 + l2

        r = math.sqrt(x**2 + y**2)

        if r > (max_reach * 0.98):
            scale = (max_reach * 0.98) / r
            x = x * scale
            y = y * scale
            r = max_reach * 0.98

        if r == 0:
            return None

        cos_theta2 = (x**2 + y**2 - l1**2 - l2**2) / (2 * l1 * l2)
        cos_theta2 = max(-1.0, min(1.0, cos_theta2))

        theta2 = math.acos(cos_theta2)

        k1 = l1 + l2 * math.cos(theta2)
        k2 = l2 * math.sin(theta2)
        theta1 = math.atan2(y, x) - math.atan2(k2, k1)

        theta3 = z

        return [theta1, theta2, theta3]

    def move_arm(self, positions, duration_sec=2.0):
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = ARM_JOINT_NAMES
        goal.trajectory.header.stamp.sec = 0
        goal.trajectory.header.stamp.nanosec = 0
    
        point = JointTrajectoryPoint()
        point.positions = [float(p) for p in positions]
    
        sec = int(duration_sec)
        nanosec = int((duration_sec - sec) * 1e9)
        point.time_from_start = Duration(sec=sec, nanosec=nanosec)
    
        goal.trajectory.points = [point]
        goal.goal_time_tolerance = Duration(sec=0, nanosec=0)
    
        self.get_logger().info(f'Отправка траектории: {point.positions}')
    
        future_goal = self.arm_client.send_goal_async(goal)
        future_goal.add_done_callback(self.goal_response_callback)

    def get_result_callback(self, future):
        result = future.result()
        if result is not None:
            self.get_logger().info(f'Движение завершено, status={result.status}')
        else:
            self.get_logger().warn('Результат действия пустой')
            
    def goal_response_callback(self, future):
        goal_handle = future.result()
    
        if goal_handle is None:
            self.get_logger().error('Не удалось отправить goal')
            return
    
        if not goal_handle.accepted:
            self.get_logger().warn('Goal не принят')
            return
    
        self.get_logger().info('Goal принят, жду результат...')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.get_result_callback)

    def goal_callback(self, msg: Point):
        wx = msg.x
        wy = msg.y
        wz = TARGET_WORLD_Z

        self.get_logger().info(f'Получена web-команда: world x={wx}, y={wy}, z={wz}')

        # World -> Local
        ly = wx - ROBOT_OFFSET_X
        lx = wy - ROBOT_OFFSET_Y
        lz = wz - ROBOT_OFFSET_Z

        self.get_logger().info(f'Локальные координаты: x={lx:.3f}, y={ly:.3f}, z={lz:.3f}')

        joints = self.inverse_kinematics(lx, ly, lz)
        if joints is None:
            self.get_logger().error('IK не смогла вычислить суставы')
            return

        self.move_arm(joints, duration_sec=2.0)


def main(args=None):
    rclpy.init(args=args)
    node = WebMotionExecutor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
