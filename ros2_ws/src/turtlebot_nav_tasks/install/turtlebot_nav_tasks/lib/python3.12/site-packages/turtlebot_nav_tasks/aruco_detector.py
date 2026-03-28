#!/usr/bin/env python3
import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from std_msgs.msg import Int32MultiArray

from cv_bridge import CvBridge
import cv2


class ArucoDetector(Node):
    """
    Узел детекции ArUco-маркеров.
    Работает и со старым API (detectMarkers), и с новым (ArucoDetector).
    """

    def __init__(self):
        super().__init__('aruco_detector')

        self.declare_parameter('image_topic', '/camera/image_raw')
        self.declare_parameter('marker_dictionary', 'DICT_4X4_50')

        image_topic = self.get_parameter('image_topic').value
        dict_name = self.get_parameter('marker_dictionary').value

        self.get_logger().info(f"Subscribing to image topic: {image_topic}")
        self.get_logger().info(f"Using dictionary: {dict_name}")

        self.bridge = CvBridge()

        # Поддержка разных версий OpenCV
        dict_name = dict_name.upper()
        if not hasattr(cv2.aruco, dict_name):
            self.get_logger().warn(f"Dictionary {dict_name} not found, using DICT_4X4_50")
            dict_name = 'DICT_4X4_50'

        dict_id = getattr(cv2.aruco, dict_name)
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dict_id)
        self.aruco_params = cv2.aruco.DetectorParameters_create()

        # Пытаемся использовать новый API
        if hasattr(cv2.aruco, "ArucoDetector"):
            self.get_logger().info("Using new ArUco API (ArucoDetector)")
            self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.aruco_params)

            def detect_function(gray):
                return self.detector.detectMarkers(gray)

        else:
            # Старый API
            self.get_logger().info("Using old ArUco API (detectMarkers)")

            def detect_function(gray):
                return cv2.aruco.detectMarkers(gray, self.aruco_dict, parameters=self.aruco_params)

        self.detect_fn = detect_function

        # ROS интерфейс
        self.subscription = self.create_subscription(
            Image,
            image_topic,
            self.image_callback,
            10
        )

        self.ids_pub = self.create_publisher(
            Int32MultiArray,
            '/aruco/ids',
            10
        )

        self._counter = 0

    def image_callback(self, msg: Image):
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().error(f"cv_bridge error: {e}")
            return

        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

        corners, ids, _ = self.detect_fn(gray)

        ids_list = []
        if ids is not None:
            ids_list = [int(i[0]) for i in ids]

        self.ids_pub.publish(Int32MultiArray(data=ids_list))

        self._counter += 1
        if self._counter % 30 == 0:
            self.get_logger().info(f"Detected: {ids_list}")


def main(args=None):
    rclpy.init(args=args)
    node = ArucoDetector()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
