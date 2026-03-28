import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/spoonge/ros2_ws/src/turtlebot_nav_tasks/install/turtlebot_nav_tasks'
