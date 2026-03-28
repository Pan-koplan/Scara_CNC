import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, RegisterEventHandler, SetEnvironmentVariable, TimerAction
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch.event_handlers import OnProcessExit
import xacro

def generate_launch_description():
    # === 1. ОБЪЯВЛЕНИЕ АРГУМЕНТОВ ===
    # Те самые аргументы, которые вы просили
    declared_arguments = []
    declared_arguments.append(
        DeclareLaunchArgument('use_sim', default_value='true',
                              description='Запускать симуляцию Gazebo?'))
    declared_arguments.append(
        DeclareLaunchArgument('use_moveit', default_value='true',
                              description='Запускать MoveIt? (Group + RViz)'))
    declared_arguments.append(
        DeclareLaunchArgument('use_rviz', default_value='true',
                              description='Запускать RViz (если MoveIt выключен)?'))

    # Инициализация переменных из аргументов
    use_sim = LaunchConfiguration('use_sim')
    use_moveit = LaunchConfiguration('use_moveit')
    use_rviz = LaunchConfiguration('use_rviz')

    # === 2. НАСТРОЙКА ПУТЕЙ ===
    pkg_description = get_package_share_directory('scara_description')
    pkg_cnc = get_package_share_directory('scara_cnc')
    pkg_app = get_package_share_directory('scara_application')
    
    # Путь к моделям (чтобы Gazebo не ругался на model://table)
    models_path = os.path.join(pkg_description, 'models')
    workspace_share = os.path.dirname(pkg_description)
    
    set_env_res = SetEnvironmentVariable(
        name='GZ_SIM_RESOURCE_PATH',
        value=models_path + ':' + workspace_share + ':' + os.environ.get('GZ_SIM_RESOURCE_PATH', '')
    )

    # === 3. ЗАГРУЗКА URDF/XACRO ===
    xacro_file = os.path.join(pkg_description, 'urdf', 'scara.xacro')
    doc = xacro.process_file(xacro_file)
    robot_description_content = doc.toxml()
    
    robot_description = {'robot_description': robot_description_content}

    # === 4. НОДЫ ===

    # Robot State Publisher (Публикует TF) - ЗАПУСКАЕМ ВСЕГДА
    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[robot_description, {'use_sim_time': use_sim}]
    )

    # --- БЛОК СИМУЛЯЦИИ (GAZEBO) ---
    # Запускается только если use_sim:=true
    
    world_path = os.path.join(pkg_description, 'worlds', 'lab.sdf')
    
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': ['-r ', world_path]}.items(),
        condition=IfCondition(use_sim)
    )

    # Спавн робота (ТОЛЬКО ОДИН РАЗ!)
    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-name', 'scara',
            '-string', robot_description_content,
            '-x', '0.7', '-y', '-0.5', '-z', '1.01',
            '-Y', '1.5708',
            '-allow_renaming', 'false' # Запрещаем создавать scara_1, scara_2...
        ],
        output='screen',
        condition=IfCondition(use_sim)
    )

    # Мост ROS-Gazebo
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',
            '/tf@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V',
            '/tf_static@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V',
            '/gripper/attach@std_msgs/msg/Empty@gz.msgs.Empty',
            '/gripper/detach@std_msgs/msg/Empty@gz.msgs.Empty'
        ],
        output='screen',
        condition=IfCondition(use_sim)
    )

    # --- КОНТРОЛЛЕРЫ ---
    # Запускаем их после спавна
    
    jsb_spawner = Node(
        package='controller_manager', executable='spawner',
        arguments=['joint_state_broadcaster', '--controller-manager', '/controller_manager'],
        condition=IfCondition(use_sim)
    )
    
    arm_spawner = Node(
        package='controller_manager', executable='spawner',
        arguments=['scara_controller', '--controller-manager', '/controller_manager'],
        condition=IfCondition(use_sim)
    )
    
    grip_spawner = Node(
        package='controller_manager', executable='spawner',
        arguments=['gripper_controller', '--controller-manager', '/controller_manager'],
        condition=IfCondition(use_sim)
    )

    # --- ПРИЛОЖЕНИЕ (CNC + BRAIN) ---
    # Это ваша логика. Она нужна всегда, когда работает симуляция.

    cnc_node = Node(
        package='scara_cnc',
        executable='cnc_node.py',
        name='cnc_node',
        output='screen',
        parameters=[{'use_sim_time': use_sim}]
    )

    brain_node = Node(
        package='scara_application',
        executable='MoveIT_cnc_coop',
        name='scara_brain',
        output='screen',
        parameters=[{'use_sim_time': use_sim}]
    )

    # --- VISUALIZATION (RVIZ) ---
    # Если MoveIt выключен, но мы хотим просто посмотреть RViz
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        parameters=[{'use_sim_time': use_sim}],
        condition=IfCondition(use_rviz) # Работает, если use_rviz:=true
    )

    # === ЦЕПОЧКИ СОБЫТИЙ (ЧТО ЗА ЧЕМ ЗАПУСКАТЬ) ===
    
    # 1. Сначала Gazebo, RSP и Мост (они стартуют сразу)
    
    # 2. Спавн робота -> Запуск Joint State Broadcaster
    spawn_event = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=spawn_entity,
            on_exit=[jsb_spawner]
        )
    )

    # 3. JSB -> Запуск основных контроллеров
    controllers_event = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=jsb_spawner,
            on_exit=[arm_spawner, grip_spawner]
        )
    )

    # 4. Контроллер руки готов -> Запуск МОЗГОВ (Скрипта)
    # Если мы не используем MoveIt в полном понимании (move_group), а просто ваш скрипт
    brain_event = RegisterEventHandler(
        event_handler=OnProcessExit(
            target_action=arm_spawner,
            on_exit=[brain_node]
        )
    )

    # Собираем все ноды
    nodes_to_start = [
        set_env_res,
        rsp_node,
        gazebo,
        spawn_entity,
        bridge,
        cnc_node, # CNC независим
        spawn_event,
        controllers_event,
        brain_event,
        # rviz_node # Можно включить, если нужно
    ]

    return LaunchDescription(declared_arguments + nodes_to_start)
