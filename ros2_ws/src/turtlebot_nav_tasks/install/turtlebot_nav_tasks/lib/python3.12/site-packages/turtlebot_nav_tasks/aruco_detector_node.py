#!/usr/bin/env python3
import math
from typing import Optional

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image, CameraInfo
from geometry_msgs.msg import Pose, PoseArray
from visualization_msgs.msg import Marker, MarkerArray
from std_msgs.msg import Header, Int32MultiArray

from cv_bridge import CvBridge

import cv2
import numpy as np


def rvec_tvec_to_pose(rvec: np.ndarray, tvec: np.ndarray) -> Pose:
    R, _ = cv2.Rodrigues(rvec.reshape(3, 1))

    tr = float(R[0, 0] + R[1, 1] + R[2, 2])
    if tr > 0.0:
        S = math.sqrt(tr + 1.0) * 2.0
        qw = 0.25 * S
        qx = (R[2, 1] - R[1, 2]) / S
        qy = (R[0, 2] - R[2, 0]) / S
        qz = (R[1, 0] - R[0, 1]) / S
    elif (R[0, 0] > R[1, 1]) and (R[0, 0] > R[2, 2]):
        S = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2.0
        qw = (R[2, 1] - R[1, 2]) / S
        qx = 0.25 * S
        qy = (R[0, 1] + R[1, 0]) / S
        qz = (R[0, 2] + R[2, 0]) / S
    elif R[1, 1] > R[2, 2]:
        S = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2.0
        qw = (R[0, 2] - R[2, 0]) / S
        qx = (R[0, 1] + R[1, 0]) / S
        qy = 0.25 * S
        qz = (R[1, 2] + R[2, 1]) / S
    else:
        S = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2.0
        qw = (R[1, 0] - R[0, 1]) / S
        qx = (R[0, 2] + R[2, 0]) / S
        qy = (R[1, 2] + R[2, 1]) / S
        qz = 0.25 * S

    pose = Pose()
    pose.position.x = float(tvec[0])
    pose.position.y = float(tvec[1])
    pose.position.z = float(tvec[2])
    pose.orientation.x = float(qx)
    pose.orientation.y = float(qy)
    pose.orientation.z = float(qz)
    pose.orientation.w = float(qw)
    return pose


class ArucoDetectorNode(Node):
    def __init__(self):
        self.declare_parameter("ids_topic", "/aruco_ids")
        self.ids_topic = self.get_parameter("ids_topic").value
        self.pub_ids = self.create_publisher(Int32MultiArray, self.ids_topic, 10)
        
        super().__init__("aruco_detector")
        self.got_caminfo = False
        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("camera_info_topic", "/camera/camera_info")
        self.declare_parameter("debug_image_topic", "~/debug_image")
        self.declare_parameter("poses_topic", "~/poses")
        self.declare_parameter("markers_topic", "~/viz_markers")

        self.declare_parameter("aruco_dictionary", "DICT_4X4_50")
        self.declare_parameter("marker_length", 0.05)  # meters
        self.declare_parameter("use_camera_info", True)
        self.declare_parameter("publish_debug_image", True)
        self.declare_parameter("publish_pose", True)

        self.image_topic = self.get_parameter("image_topic").value
        self.caminfo_topic = self.get_parameter("camera_info_topic").value
        self.debug_image_topic = self.get_parameter("debug_image_topic").value
        self.poses_topic = self.get_parameter("poses_topic").value
        self.markers_topic = self.get_parameter("markers_topic").value

        self.marker_length = float(self.get_parameter("marker_length").value)
        self.use_camera_info = bool(self.get_parameter("use_camera_info").value)
        self.publish_debug_image = bool(self.get_parameter("publish_debug_image").value)
        self.publish_pose = bool(self.get_parameter("publish_pose").value)

        dict_name = str(self.get_parameter("aruco_dictionary").value)
        self.aruco_dict = self._make_aruco_dict(dict_name)

        # OpenCV 4.6: DetectorParameters_create() is the common path
        if hasattr(cv2.aruco, "DetectorParameters_create"):
            self.aruco_params = cv2.aruco.DetectorParameters_create()
        else:
            # fallback (rare)
            self.aruco_params = cv2.aruco.DetectorParameters()

        self.bridge = CvBridge()

        self.K: Optional[np.ndarray] = None
        self.D: Optional[np.ndarray] = None
        self.frame_id: str = "camera_frame"

        self.sub_image = self.create_subscription(Image, self.image_topic, self.on_image, 10)
        if self.use_camera_info:
            self.sub_info = self.create_subscription(CameraInfo, self.caminfo_topic, self.on_caminfo, 10)

        self.pub_debug = self.create_publisher(Image, self.debug_image_topic, 10)
        self.pub_poses = self.create_publisher(PoseArray, self.poses_topic, 10)
        self.pub_viz = self.create_publisher(MarkerArray, self.markers_topic, 10)

        self.get_logger().info(
            f"ArUco detector started. OpenCV={cv2.__version__}, dict={dict_name}, image={self.image_topic}"
        )
        self.aruco_params.adaptiveThreshWinSizeMin = 3
        self.aruco_params.adaptiveThreshWinSizeMax = 53
        self.aruco_params.adaptiveThreshWinSizeStep = 10
        self.aruco_params.adaptiveThreshConstant = 7
        self.aruco_params.minMarkerPerimeterRate = 0.01
        self.aruco_params.polygonalApproxAccuracyRate = 0.05
        
        if hasattr(cv2.aruco, "CORNER_REFINE_SUBPIX"):
            self.aruco_params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        

    def _make_aruco_dict(self, name: str):
        mapping = {
            "DICT_4X4_50": cv2.aruco.DICT_4X4_50,
            "DICT_4X4_100": cv2.aruco.DICT_4X4_100,
            "DICT_5X5_50": cv2.aruco.DICT_5X5_50,
            "DICT_5X5_100": cv2.aruco.DICT_5X5_100,
            "DICT_6X6_50": cv2.aruco.DICT_6X6_50,
            "DICT_6X6_100": cv2.aruco.DICT_6X6_100,
            "DICT_ARUCO_ORIGINAL": cv2.aruco.DICT_ARUCO_ORIGINAL,
        }
        if name not in mapping:
            self.get_logger().warn(f"Unknown dict '{name}', fallback to DICT_4X4_50")
            name = "DICT_4X4_50"

        # OpenCV 4.6 supports getPredefinedDictionary
        return cv2.aruco.getPredefinedDictionary(mapping[name])

    def on_caminfo(self, msg: CameraInfo):
        if self.got_caminfo:
            return
    
        self.frame_id = msg.header.frame_id or self.frame_id
        self.K = np.array(msg.k, dtype=np.float64).reshape(3, 3)
        self.D = np.array(msg.d, dtype=np.float64).reshape(-1, 1)
    
        self.get_logger().info(f"Got CameraInfo. frame_id={self.frame_id}")
        self.got_caminfo = True
    

    def on_image(self, msg: Image):
        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().error(f"cv_bridge failed: {e}")
            return

        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        

        # OpenCV 4.6: старый API
        corners, ids, rejected = cv2.aruco.detectMarkers(
            gray, self.aruco_dict, parameters=self.aruco_params
        )
        n_rej = 0 if rejected is None else len(rejected)
        if ids is None:
            self.get_logger().info(f"No markers. rejected={n_rej}")
        else:
            self.get_logger().info(f"Detected {len(ids)} markers: {ids.flatten().tolist()}, rejected={n_rej}")
        

        header = Header()
        header.stamp = msg.header.stamp
        header.frame_id = msg.header.frame_id or self.frame_id

        pose_array = PoseArray()
        pose_array.header = header
        viz = MarkerArray()

        if ids is not None and len(ids) > 0:
            cv2.aruco.drawDetectedMarkers(cv_img, corners, ids)

            can_pose = (
                self.publish_pose
                and (self.K is not None)
                and (self.D is not None)
                and (self.marker_length > 0.0)
            )

            if can_pose:
                rvecs, tvecs, _obj = cv2.aruco.estimatePoseSingleMarkers(
                    corners, self.marker_length, self.K, self.D
                )

                for i, marker_id in enumerate(ids.flatten().tolist()):
                    rvec = rvecs[i].reshape(3)
                    tvec = tvecs[i].reshape(3)

                    cv2.drawFrameAxes(cv_img, self.K, self.D, rvec, tvec, self.marker_length * 0.5)

                    pose = rvec_tvec_to_pose(rvec, tvec)
                    pose_array.poses.append(pose)

                    m = Marker()
                    m.header = header
                    m.ns = "aruco"
                    m.id = int(marker_id)
                    m.type = Marker.ARROW
                    m.action = Marker.ADD
                    m.pose = pose
                    m.scale.x = self.marker_length * 0.8
                    m.scale.y = self.marker_length * 0.15
                    m.scale.z = self.marker_length * 0.15
                    m.color.a = 1.0
                    m.color.r = 0.1
                    m.color.g = 1.0
                    m.color.b = 0.1
                    viz.markers.append(m)
            else:
                for i, marker_id in enumerate(ids.flatten().tolist()):
                    c = corners[i].reshape(-1, 2)
                    center = c.mean(axis=0).astype(int)
                    cv2.putText(
                        cv_img, f"id:{marker_id}", (int(center[0]), int(center[1])),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
                    )

        if self.publish_pose:
            self.pub_poses.publish(pose_array)
            self.pub_viz.publish(viz)
        ids_msg = Int32MultiArray()
        
        if ids is not None and len(ids) > 0:
            ids_msg.data = [int(x) for x in ids.flatten().tolist()]
        else:
            ids_msg.data = []
        self.pub_ids.publish(ids_msg)
        
        if self.publish_debug_image:
            out = self.bridge.cv2_to_imgmsg(cv_img, encoding="bgr8")
            out.header = header
            self.pub_debug.publish(out)


def main():
    rclpy.init()
    node = ArucoDetectorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
