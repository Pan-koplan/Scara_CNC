from setuptools import find_packages, setup
import os
from glob import glob
package_name = 'tb3_aruco_mission'
setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/tb3_aruco_mission/launch', ['launch/aruco_test.launch.py']),
        (os.path.join('share', 'tb3_aruco_mission', 'launch'),
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
        'nav_three_points = tb3_aruco_mission.nav_three_points:main',
        'nav_optimal_four = tb3_aruco_mission.nav_optimal_four:main',
        'aruco_detector = tb3_aruco_mission.aruco_detector:main',
        'nav_aruco_optimal = tb3_aruco_mission.nav_aruco_optimal:main',
        'nav_aruco_to_id = tb3_aruco_mission.nav_aruco_to_id:main',
        'aruco_to_id = tb3_aruco_mission.nav_aruco_to_id:main', 
        'aruco_detector_node = tb3_aruco_mission.aruco_detector_node:main',
        ],
    },
)
