#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from moveit_msgs.action import MoveGroup
from moveit_msgs.msg import Constraints, JointConstraint, PositionIKRequest
from geometry_msgs.msg import PoseStamped

# --- НАСТРОЙКИ ---
GROUP_NAME = "scara_arm"
JOINT_NAME = "hand1_joint" # Имя первого сустава (проверьте в URDF!)
TARGET_ANGLE = -2.0         # Угол в радианах (примерно 57 градусов)
# -----------------

class SimpleMover(Node):
    def __init__(self):
        super().__init__('simple_mover')
        
        # Action Client для главного интерфейса MoveIt
        self.move_group_client = ActionClient(self, MoveGroup, 'move_action')
        
        self.get_logger().info("Жду MoveIt...")
        self.move_group_client.wait_for_server()
        self.get_logger().info("MoveIt готов!")

    def move_joint(self):
        goal_msg = MoveGroup.Goal()
        
        # 1. Заполняем основные параметры
        goal_msg.request.workspace_parameters.header.frame_id = "base_link"
        goal_msg.request.group_name = GROUP_NAME
        goal_msg.request.allowed_planning_time = 5.0
        goal_msg.request.max_velocity_scaling_factor = 1.0 # Двигаемся медленно (10% скорости)
        goal_msg.request.max_acceleration_scaling_factor = 0.1
        
        # 2. Создаем ограничение для сустава (цель)
        jc = JointConstraint()
        jc.joint_name = JOINT_NAME
        jc.position = TARGET_ANGLE
        jc.tolerance_above = 0.01
        jc.tolerance_below = 0.01
        jc.weight = 1.0

        # 3. Добавляем цель в запрос
        constraints = Constraints()
        constraints.joint_constraints.append(jc)
        goal_msg.request.goal_constraints.append(constraints)
        
        # 4. Режим "Plan & Execute"
        goal_msg.planning_options.plan_only = False
        goal_msg.planning_options.look_around = False
        goal_msg.planning_options.replan = True

        self.get_logger().info(f"Отправляю команду: {JOINT_NAME} -> {TARGET_ANGLE} рад.")
        
        # 5. Отправка
        future = self.move_group_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, future)
        goal_handle = future.result()

        if not goal_handle.accepted:
            self.get_logger().error("Цель отклонена!")
            return

        self.get_logger().info("Цель принята, выполняю...")
        res_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, res_future)
        
        result = res_future.result().result
        if result.error_code.val == 1: # 1 = SUCCESS
            self.get_logger().info("УСПЕХ! Робот повернулся.")
        else:
            self.get_logger().error(f"ОШИБКА: Код {result.error_code.val}")

def main():
    rclpy.init()
    mover = SimpleMover()
    mover.move_joint()
    rclpy.shutdown()

if __name__ == '__main__':
    main()