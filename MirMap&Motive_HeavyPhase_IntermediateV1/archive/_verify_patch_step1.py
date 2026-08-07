# -*- coding: utf-8 -*-
import os
import sys
import time

print("=== 1. CHECKING INJECTED SECTIONS IN launch_session.py ===")
with open(os.path.join("agents", "launch_session.py"), "r", encoding="utf-8", errors="ignore") as f:
    code = f.read()

checks = [
    ("MirCommandLogger Import", "from mir_command_logger import MirCommandLogger"),
    ("MirSlamLogger try_connect", "self.client = roslibpy.Ros(host=ROBOT_IP, port=ROS_PORT)"),
    ("MirCommandLogger Instance", "cmd_logger = MirCommandLogger"),
    ("MirCommandLogger Stop", "cmd_logger.stop()"),
    ("MirCommandLogger Save", "cmd_logger.save_final()")
]

for label, needle in checks:
    status = "OK" if needle in code else "MISSING"
    print(f"  [{status}] {label}")

print("\n=== 2. LIVE COMPONENT TEST (MIRSlamLogger + MirCommandLogger) ===")
try:
    from launch_session import MirSlamLogger, MirCommandLogger, ROBOT_IP, ROS_PORT
    test_session = os.path.join("sessions", "_test_temp_session")
    os.makedirs(test_session, exist_ok=True)

    print(f"  Target: {ROBOT_IP}:{ROS_PORT}")
    
    # Test SLAM Logger connection
    slam = MirSlamLogger(test_session)
    slam_connected = slam.try_connect()
    print(f"  MirSlamLogger connection: {'SUCCESS' if slam_connected else 'FAILED'}")

    # Test Command Logger connection
    cmd = MirCommandLogger(test_session, robot_ip=ROBOT_IP, ros_port=ROS_PORT) if MirCommandLogger else None
    cmd_connected = cmd.try_connect() if cmd else False
    print(f"  MirCommandLogger connection: {'SUCCESS' if cmd_connected else 'FAILED'}")

    # Cleanup connections
    if slam_connected:
        slam.stop()
    if cmd_connected:
        cmd.stop()

    # Cleanup temp folder
    import shutil
    shutil.rmtree(test_session, ignore_errors=True)
    print("  Temporary test cleaned up.")

except Exception as e:
    print(f"  [ERROR] Live test encountered exception: {e}")
    import traceback
    traceback.print_exc()

print("\n=== VERIFICATION COMPLETE ===")
