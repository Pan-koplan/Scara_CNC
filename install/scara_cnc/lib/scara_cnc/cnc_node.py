#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger
import time

class CncMachine(Node):
    def __init__(self):
        super().__init__('cnc_machine_node')
        
        # Создаем сервис "process_part"
        # Робот дернет его, когда положит деталь
        self.srv = self.create_service(Trigger, 'process_part', self.process_callback)
        
        self.get_logger().info('CNC Machine is READY. Waiting for parts...')

    def process_callback(self, request, response):
        self.get_logger().info('Signal received! Part loaded.')
        self.get_logger().info('Machining started... (zzzzzz)')
        
        # Симуляция работы станка (3 секунды)
        time.sleep(3.0)
        
        self.get_logger().info('Machining FINISHED.')
        
        response.success = True
        response.message = "Part processed successfully"
        return response

def main(args=None):
    rclpy.init(args=args)
    node = CncMachine()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
