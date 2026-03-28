from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    mtc_node = Node(
        package='scara_mtc',
        executable='mtc_hello_node',
        output='screen',
        parameters=[
            {'group_name': 'scara_arm'},
            {'named_target': 'home'},
        ]
    )

    return LaunchDescription([mtc_node])
