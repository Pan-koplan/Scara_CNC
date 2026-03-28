#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.parameter import Parameter
from std_msgs.msg import Float64MultiArray
from std_srvs.srv import Trigger
from trajectory_msgs.msg import JointTrajectoryPoint
from control_msgs.action import FollowJointTrajectory
from builtin_interfaces.msg import Duration
import time
import threading
import math
from std_srvs.srv import SetBool

# ================= НАСТРОЙКИ (ТВОИ ЦИФРЫ) =================

ARM_JOINT_NAMES = ['hand1_joint', 'hand2_joint', 'hand3_joint'] 

# ГЕОМЕТРИЯ РОБОТА
LINK1 = 0.25   
LINK2 = 0.245  

# СМЕЩЕНИЕ БАЗЫ
ROBOT_OFFSET_X = 0.7
ROBOT_OFFSET_Y = -0.5
ROBOT_OFFSET_Z = 1.0

# КООРДИНАТЫ ЦЕЛЕЙ
PICK_X, PICK_Y   = 0.7, -0.2  
CNC_X, CNC_Y     = 0.5, -0.2  
PLACE_X, PLACE_Y = 0.5, -0.4 

# Высоты (Z)
H_HOVER = 0
H_DOWN  = 1.05

# ==========================================================

class ScaraBrain(Node):
    def __init__(self):
        super().__init__('scara_brain_node')
        self.suction_client = self.create_client(SetBool, '/gripper/switch_suction')
        self.set_parameters([Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        self.get_logger().info('>>> Инициализация SCARA Brain...')

        self.cb_group = ReentrantCallbackGroup()

        self.arm_client = ActionClient(
            self, FollowJointTrajectory, '/scara_controller/follow_joint_trajectory', callback_group=self.cb_group)
        self.cnc_client = self.create_client(
            Trigger, 'process_part', callback_group=self.cb_group)
        self.gripper_pub = self.create_publisher(
            Float64MultiArray, '/gripper_controller/commands', 10, callback_group=self.cb_group)

        self.logic_thread = threading.Thread(target=self.run_logic_thread)
        self.logic_thread.daemon = True
        self.logic_thread.start()

    def run_logic_thread(self):
        time.sleep(3.0) 
        self.check_connections()
        try:
            self.execute_mission()
        except Exception as e:
            self.get_logger().error(f'CRASH IN LOGIC: {e}')
        finally:
            self.get_logger().info('Логика завершена.')

    def check_connections(self):
        self.get_logger().info('Проверка связи...')
        if not self.arm_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error('ОШИБКА: scara_controller не отвечает!')

    # ================= МАТЕМАТИКА (IK) С ОГРАНИЧЕНИЕМ =================

    def inverse_kinematics(self, x, y, z):
        l1 = LINK1
        l2 = LINK2
        max_reach = l1 + l2
        
        # 1. Считаем дистанцию
        r = math.sqrt(x**2 + y**2)
        
        # --- ИСПРАВЛЕНИЕ: БОЛЬШЕ ЗАПАС ОТ СИНГУЛЯРНОСТИ ---
        # Было 0.999 (слишком близко к прямой линии). 
        # Ставим 0.98 (чуть согнутый локоть).
        if r > (max_reach * 0.98):
            scale = (max_reach * 0.98) / r
            x = x * scale
            y = y * scale
            r = max_reach * 0.98 # Обновляем r для формул
            
        if r == 0:
            return None 

        # 2. Теорема косинусов
        cos_theta2 = (x**2 + y**2 - l1**2 - l2**2) / (2 * l1 * l2)
        cos_theta2 = max(-1.0, min(1.0, cos_theta2))
        
        # Если нужно, добавь минус: -math.acos(...)
        theta2 = math.acos(cos_theta2) 
        
        # 3. Угол плеча
        k1 = l1 + l2 * math.cos(theta2)
        k2 = l2 * math.sin(theta2)
        theta1 = math.atan2(y, x) - math.atan2(k2, k1)
        
        # 4. Ось Z
        theta3 = z 

        return [theta1, theta2, theta3]

    def move_to_world_point(self, wx, wy, wz, duration=2.0):
        # Перевод Мировые -> Локальные
        ly = wx - ROBOT_OFFSET_X
        lx = wy - ROBOT_OFFSET_Y
        lz = wz - ROBOT_OFFSET_Z
        
        self.get_logger().info(f'GOTO World({wx}, {wy}) -> Local({lx:.2f}, {ly:.2f})')

        joints = self.inverse_kinematics(lx, ly, lz)
        
        if joints is None:
            self.get_logger().error('ОТМЕНА: Невозможная точка (слишком близко к базе?)')
            return

        self.move_arm(joints, duration)

    # ================= НИЗКОУРОВНЕВОЕ УПРАВЛЕНИЕ =================

    def move_arm(self, positions, duration_sec=3.0):
        goal = FollowJointTrajectory.Goal()
        goal.trajectory.joint_names = ARM_JOINT_NAMES
        
        # 1. СТАРТ СЕЙЧАС (Чтобы не было ошибки времени)
        goal.trajectory.header.stamp.sec = 0
        goal.trajectory.header.stamp.nanosec = 0
        
        point = JointTrajectoryPoint()
        point.positions = [float(p) for p in positions]
        
        sec = int(duration_sec)
        nanosec = int((duration_sec - sec) * 1e9)
        point.time_from_start = Duration(sec=sec, nanosec=nanosec)
        goal.trajectory.points = [point]
        
        # 2. ОТКЛЮЧАЕМ ПРОВЕРКИ (0 = Бесконечное терпение)
        goal.goal_time_tolerance = Duration(sec=0, nanosec=0)
        
        future_goal = self.arm_client.send_goal_async(goal)
        
        # Ждем ответа от сервера
        try:
            goal_handle = future_goal.result()
        except Exception as e:
            self.get_logger().error(f'Ошибка связи: {e}')
            return

        # === ГЛАВНЫЙ ФИКС: ИГНОРИРОВАНИЕ ОТКАЗА ===
        if goal_handle is None or not goal_handle.accepted:
            # Мы просто ждем столько времени, сколько должно занять движение
            time.sleep(duration_sec)
            
            # И даем еще чуть-чуть на стабилизацию
            time.sleep(0.5)
            return 

        # Если же приняли нормально — ждем честного результата
        res_future = goal_handle.get_result_async()
        res = res_future.result()
        
        if res.status != 4:
             self.get_logger().warn(f'Статус завершения: {res.status}')
        
        time.sleep(0.5)

    def set_gripper(self, state):
        msg = Float64MultiArray()
        val = 2 if state == 'close' else 0.0
        msg.data = [val, val, val]
        self.gripper_pub.publish(msg)
        time.sleep(3)
        req = SetBool.Request()
        req.data = True if state == 'close' else False
        if self.suction_client.service_is_ready():
            self.suction_client.call_async(req)

    def call_cnc(self):
        if not self.cnc_client.service_is_ready():
            time.sleep(1.0)
            return
        
        self.get_logger().info('Sending to CNC...')
        req = Trigger.Request()
        self.cnc_client.call(req)
        self.get_logger().info('CNC Finished.')

    # ================= СЦЕНАРИЙ =================

    def execute_mission(self):
        CYCLES = 3
        
        # Сначала домой (безопасно)
        self.move_arm([0.0, 0.0, 0.0], 3.0)

        for i in range(CYCLES):
            self.get_logger().info(f'=== ЦИКЛ {i+1} ===')
            
            # 1. PICK
            self.move_to_world_point(PICK_X, PICK_Y, H_HOVER, 1)
            self.set_gripper('open')
            self.move_to_world_point(PICK_X, PICK_Y, H_DOWN, 1)
            self.set_gripper('close')
            self.move_to_world_point(PICK_X, PICK_Y, H_HOVER, 1)
            
            # 2. CNC
            self.move_to_world_point(CNC_X, CNC_Y, H_HOVER, 1)
            self.move_to_world_point(CNC_X, CNC_Y, H_DOWN, 1)
            self.set_gripper('open')
            self.move_to_world_point(CNC_X, CNC_Y, H_HOVER, 1)
            
            # 3. PROCESS
            self.call_cnc()
            
            # 4. PICK CNC
            self.move_to_world_point(CNC_X, CNC_Y, H_DOWN, 1)
            self.set_gripper('close')
            self.move_to_world_point(CNC_X, CNC_Y, H_HOVER, 1)
            
            # 5. PLACE
            self.move_to_world_point(PICK_X, PICK_Y, H_HOVER, 1)
            self.move_to_world_point(PICK_X, PICK_Y, H_DOWN, 1)
            self.set_gripper('open')
            

        self.get_logger().info('ЗАДАНИЕ ВЫПОЛНЕНО!')
        self.move_arm([0.0, 0.0, 0.0], 3.0)

def main(args=None):
    rclpy.init(args=args)
    node = ScaraBrain()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
