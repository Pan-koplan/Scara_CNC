from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{
                'robot_description': '<robot></robot>'
            }]
        ),
        Node(
            package='scara_application',
            executable='web_motion_executor',
            name='web_motion_executor',
            output='screen'
        ),
    ])