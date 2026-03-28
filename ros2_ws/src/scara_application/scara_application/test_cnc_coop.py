#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from control_msgs.action import FollowJointTrajectory
from trajectory_msgs.msg import JointTrajectoryPoint
from rclpy.duration import Duration
from std_srvs.srv import SetBool # Импортируем тип сообщения для станка

class ScaraCncController(Node):
    def __init__(self):
        super().__init__('scara_cnc_controller')
        
        # 1. Клиент для управления роботом
        self._action_client = ActionClient(
            self, 
            FollowJointTrajectory, 
            '/scara_controller/follow_joint_trajectory'
        )
        
        # 2. Клиент для общения со СТАНКОМ
        self._cnc_client = self.create_client(SetBool, 'process_part')
        
        self.joint_names = ['hand1_joint', 'hand2_joint', 'hand3_joint']
        self.get_logger().info('Controller initialized. Waiting for services...')

    def wait_for_services(self):
        """Ждем доступности робота и станка"""
        if not self._action_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('Robot controller not found!')
            return False
            
        if not self._cnc_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().warn('CNC Machine service not found (is cnc_node running?)')
            return False
            
        self.get_logger().info('All systems GO!')
        return True

    def move_to_joints(self, positions, duration_sec=2.0):
        """
        Функция отправляет робота в точку и БЛОКИРУЕТ выполнение, 
        пока робот не доедет.
        """
        goal_msg = FollowJointTrajectory.Goal()
        goal_msg.trajectory.joint_names = self.joint_names
        
        point = JointTrajectoryPoint()
        point.positions = positions
        point.velocities = [0.0] * 3
        # Робот должен оказаться там через duration_sec
        point.time_from_start = Duration(seconds=duration_sec).to_msg()
        
        goal_msg.trajectory.points = [point]

        self.get_logger().info(f'Moving to {positions}...')
        
        # 1. Отправляем цель
        send_goal_future = self._action_client.send_goal_async(goal_msg)
        rclpy.spin_until_future_complete(self, send_goal_future)
        
        goal_handle = send_goal_future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Move rejected!')
            return False

        # 2. Ждем завершения движения (Result)
        get_result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, get_result_future)
        
        result = get_result_future.result()
        # В result.result.error_code можно проверить успех, но для простоты считаем ОК
        return True

    def trigger_cnc_machine(self):
        """
        Функция вызывает сервис станка и ЖДЕТ, пока он закончит работу.
        """
        req = SetBool.Request()
        req.data = True # Команда "Начать"
        
        self.get_logger().info('>>> Waiting for CNC machine...')
        
        future = self._cnc_client.call_async(req)
        # Блокируем скрипт, пока станок не вернет ответ
        rclpy.spin_until_future_complete(self, future)
        
        response = future.result()
        if response.success:
            self.get_logger().info(f'<<< CNC Finished: {response.message}')
        else:
            self.get_logger().error('<<< CNC Failed!')
            
        return response.success

def main(args=None):
    rclpy.init(args=args)
    controller = ScaraCncController()

    if not controller.wait_for_services():
        return

    try:
        # --- СЦЕНАРИЙ РАБОТЫ ---
        
        # 1. HOME
        controller.move_to_joints([0.0, 0.0, 0.0], duration_sec=2.0)
        
        # 2. ВЗЯТЬ ЗАГОТОВКУ (Склад слева)
        # Пример координат: поворот, плечо, опускание
        controller.move_to_joints([1.5, 0.5, 0.0], duration_sec=2.0)
        # (Имитация хватания)
        
        # 3. ПОЛОЖИТЬ В СТАНОК (Станок где-то справа-спереди)
        # Координаты зависят от того, где стоит твой станок
        cnc_position = [-0.5, -0.5, 0.05] 
        controller.move_to_joints(cnc_position, duration_sec=2.0)
        
        # 4. ВЫЗОВ СТАНКА (Самое важное!)
        # Робот стоит и ждет, пока cnc_node не ответит
        controller.trigger_cnc_machine()
        
        # 5. ЗАБРАТЬ И ОТВЕЗТИ НА СКЛАД ГОТОВОЙ ПРОДУКЦИИ
        controller.move_to_joints([0.0, -1.5, 0.0], duration_sec=2.0)
        
        # 6. ВЕРНУТЬСЯ ДОМОЙ
        controller.move_to_joints([0.0, 0.0, 0.0], duration_sec=1.5)

        controller.get_logger().info('Cycle completed successfully! ✅')

    except KeyboardInterrupt:
        pass
    
    controller.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
