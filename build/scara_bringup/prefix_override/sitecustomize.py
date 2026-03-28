import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/spoonge/Projects/Scara_arm_CNC/install/scara_bringup'
