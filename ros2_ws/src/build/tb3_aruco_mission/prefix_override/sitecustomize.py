import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/spoonge/ros2_ws/src/install/tb3_aruco_mission'
