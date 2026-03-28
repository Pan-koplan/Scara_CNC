#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint
from rclpy.duration import Duration

class ScaraFourPointsNode(Node):
    def __init__(self):
        super().__init__('scara_four_points')
        self._action_client = ActionClient(
            self, 
            FollowJointTrajectory, 
            '/scara_controller/follow_joint_trajectory'
        )
        
        self.joint_names = ['hand1_joint', 'hand2_joint', 'hand3_joint']
        
    def send_goal(self):
        self.get_logger().info('Waiting for action server...')
        self._action_client.wait_for_server()
        
        goal_msg = FollowJointTrajectory.Goal()
        goal_msg.trajectory.joint_names = self.joint_names
        
        # --- НАСТРОЙКА ТОЧЕК ---
        # Формат: ([позиции], время_от_старта_траектории)
        # Важно: время должно только увеличиваться!
        points_data = [
            ([0.0, 0.0, 0.0], 2.0),       # Точка 1
            ([-0.15, -1.6, 1.0], 5.0),       # Точка 2
            ([0.7, 0.8, 0.1], 7.0),       # Точка 3
            ([-0.5, 0.5, 0.0], 12.0)      # Точка 4
        ]

        for positions, time_from_start in points_data:
            point = JointTrajectoryPoint()
            point.positions = positions
            point.velocities = [0.0] * 3 
            # Указываем время достижения точки от начала запуска
            point.time_from_start = Duration(seconds=time_from_start).to_msg()
            goal_msg.trajectory.points.append(point)

        self.get_logger().info(f'Sending trajectory with {len(points_data)} points...')
        
        self._send_goal_future = self._action_client.send_goal_async(goal_msg)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info('Goal rejected :(')
            return

        self.get_logger().info('Goal accepted! Executing...')
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        self.get_logger().info('Sequence finished successfully! ✅')
        rclpy.shutdown()

def main(args=None):
    rclpy.init(args=args)
    node = ScaraFourPointsNode()
    node.send_goal()
    rclpy.spin(node)

if __name__ == '__main__':
    main()
