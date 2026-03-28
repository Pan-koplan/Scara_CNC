from setuptools import find_packages, setup
import os
from glob import glob
package_name = 'turtlebot_nav_tasks'
setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/turtlebot_nav_tasks/launch', ['launch/aruco_test.launch.py']),
        (os.path.join('share', 'turtlebot_nav_tasks', 'launch'),
            glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='root@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
        'nav_three_points = turtlebot_nav_tasks.nav_three_points:main',
        'nav_optimal_four = turtlebot_nav_tasks.nav_optimal_four:main',
        'aruco_detector = turtlebot_nav_tasks.aruco_detector:main',
        'nav_aruco_optimal = turtlebot_nav_tasks.nav_aruco_optimal:main',
        'nav_aruco_to_id = turtlebot_nav_tasks.nav_aruco_to_id:main',
        'aruco_to_id = turtlebot_nav_tasks.nav_aruco_to_id:main', 
        'aruco_detector_node = turtlebot_nav_tasks.aruco_detector_node:main',
        ],
    },
)
