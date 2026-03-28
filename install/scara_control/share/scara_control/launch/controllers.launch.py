from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    # 1) joint_state_broadcaster
    jsb = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "joint_state_broadcaster",
            "--controller-manager", "/controller_manager",
        ],
        output="screen",
    )

    # 2) основной контроллер (замени имя на своё из controllers.yaml!)
    main_ctrl = Node(
        package="controller_manager",
        executable="spawner",
        arguments=[
            "scara_controller",
            "--controller-manager", "/controller_manager",
        ],
        output="screen",
    )
    # 3. НОВОЕ: Запуск контроллера схвата
    gripper_controller_spawner = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["gripper_controller", "--controller-manager", "/controller_manager"],
    )

    return LaunchDescription([jsb, main_ctrl, gripper_controller_spawner])
