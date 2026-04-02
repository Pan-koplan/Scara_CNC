import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from ament_index_python.packages import get_package_share_directory
from moveit_configs_utils import MoveItConfigsBuilder


def generate_launch_description():
    moveit_config = (
        MoveItConfigsBuilder("scara", package_name="scara_moveit_config")
        .robot_description(file_path="config/scara.urdf")
        .robot_description_semantic(file_path="config/scara.srdf")
        .planning_pipelines(pipelines=["ompl"])
        .to_moveit_configs()
    )

    controllers_file = os.path.join(
        get_package_share_directory("scara_moveit_config"),
        "config",
        "moveit_controllers.yaml"
    )

    use_sim_time = LaunchConfiguration("use_sim_time")
    use_rviz = LaunchConfiguration("use_rviz")

    move_group_capabilities = {
        "capabilities": "move_group/ExecuteTaskSolutionCapability",
        "disable_capabilities": "",
    }

    run_move_group_node = Node(
        package="moveit_ros_move_group",
        executable="move_group",
        output="screen",
        parameters=[
            moveit_config.to_dict(),
            controllers_file,
            move_group_capabilities,
            {"use_sim_time": use_sim_time},
        ],
    )

    rviz_config_file = os.path.join(
        get_package_share_directory("scara_moveit_config"),
        "config",
        "moveit.rviz"
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="log",
        arguments=["-d", rviz_config_file],
        parameters=[
            moveit_config.robot_description,
            moveit_config.robot_description_semantic,
            moveit_config.planning_pipelines,
            moveit_config.robot_description_kinematics,
            {"use_sim_time": use_sim_time},
        ],
        condition=IfCondition(use_rviz),
    )

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        DeclareLaunchArgument("use_rviz", default_value="true"),
        run_move_group_node,
        rviz_node,
    ])
