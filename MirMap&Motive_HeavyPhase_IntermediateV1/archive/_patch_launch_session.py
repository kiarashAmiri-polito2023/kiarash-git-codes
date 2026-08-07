# -*- coding: utf-8 -*-
import os
import shutil
import re
import py_compile
from datetime import datetime

file_path = os.path.join("agents", "launch_session.py")
if not os.path.exists(file_path):
    print("[ERROR] agents/launch_session.py not found!")
    exit(1)

# 1. CREATE BACKUP
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = file_path + f".bak_{timestamp}"
shutil.copy2(file_path, backup_path)
print(f"[BACKUP] Created: {backup_path}")

with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
    code = f.read()

# 2. PATCH 1: Fix MirSlamLogger.try_connect()
slam_connect_fixed = """    def try_connect(self):
        try:
            import roslibpy
            self.client = roslibpy.Ros(host=ROBOT_IP, port=ROS_PORT)
            self.client.run()
            if not self.client.is_connected:
                print("[SLAM] WARNING: Could not connect to MiR at " + str(ROBOT_IP) + ":" + str(ROS_PORT))
                self.connected = False
                return False
            print("[SLAM] Connected to MiR at " + str(ROBOT_IP) + ":" + str(ROS_PORT))
            self.connected = True
            return True
        except ImportError:
            print("[SLAM] WARNING: roslibpy not installed.")
            self.connected = False
            return False
        except Exception as e:
            print(f"[SLAM] WARNING: Connection error: {e}")
            self.connected = False
            return False"""

code = re.sub(
    r'def try_connect\(self\):\s+try:\s+import roslibpy\s+except ImportError:\s+print\(\"\[SLAM\] WARNING: roslibpy not installed\.\"\)\s+return False\s+self\.client = roslibpy\.Ros.*?return True',
    slam_connect_fixed.strip(),
    code,
    flags=re.DOTALL
)
print("[PATCH 1] MirSlamLogger.try_connect patched.")

# 3. PATCH 2: Ensure MirCommandLogger is imported
import_statement = "from mir_command_logger import MirCommandLogger"
if import_statement not in code:
    code = code.replace(
        "import traceback",
        "import traceback\ntry:\n    from mir_command_logger import MirCommandLogger\nexcept ImportError:\n    MirCommandLogger = None"
    )
    print("[PATCH 2] MirCommandLogger import added.")

# 4. PATCH 3: Instantiate MirCommandLogger in session lifecycle
old_instantiation = """    slam_logger = MirSlamLogger(session_path)
    motive_tracker = MotiveTrackerThread(session_path)

    slam_ok = slam_logger.try_connect()
    motive_ok = motive_tracker.try_connect()"""

new_instantiation = """    slam_logger = MirSlamLogger(session_path)
    cmd_logger = MirCommandLogger(session_path, robot_ip=ROBOT_IP, ros_port=ROS_PORT) if MirCommandLogger else None
    motive_tracker = MotiveTrackerThread(session_path)

    slam_ok = slam_logger.try_connect()
    cmd_ok = cmd_logger.try_connect() if cmd_logger else False
    motive_ok = motive_tracker.try_connect()"""

if old_instantiation in code:
    code = code.replace(old_instantiation, new_instantiation)
    print("[PATCH 3] MirCommandLogger initialization added.")
else:
    print("[WARN] Patch 3 pattern not found verbatim. Attempting flexible match...")
    pattern_init = r'(slam_logger = MirSlamLogger\(session_path\)\s+)(motive_tracker = MotiveTrackerThread\(session_path\)\s+)(slam_ok = slam_logger\.try_connect\(\)\s+)(motive_ok = motive_tracker\.try_connect\(\))'
    replacement_init = r'\1cmd_logger = MirCommandLogger(session_path, robot_ip=ROBOT_IP, ros_port=ROS_PORT) if MirCommandLogger else None\n    \2\3cmd_ok = cmd_logger.try_connect() if cmd_logger else False\n    \4'
    code = re.sub(pattern_init, replacement_init, code)

# 5. PATCH 4: Stop & Save MirCommandLogger
old_stopping = """    slam_logger.stop()
    motive_tracker.stop()"""

new_stopping = """    slam_logger.stop()
    if cmd_logger and cmd_ok:
        cmd_logger.stop()
    motive_tracker.stop()"""

if old_stopping in code:
    code = code.replace(old_stopping, new_stopping)
    print("[PATCH 4] MirCommandLogger stop sequence added.")

old_saving = """    if slam_ok:
        slam_logger.save_final()
    if motive_ok:
        motive_tracker.save_final()"""

new_saving = """    if slam_ok:
        slam_logger.save_final()
    if cmd_logger and cmd_ok:
        cmd_logger.save_final()
    if motive_ok:
        motive_tracker.save_final()"""

if old_saving in code:
    code = code.replace(old_saving, new_saving)
    print("[PATCH 5] MirCommandLogger save_final sequence added.")

# SAVE PATCHED FILE
with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

# 6. VERIFY SYNTAX
try:
    py_compile.compile(file_path, doraise=True)
    print("[VERIFY] SUCCESS: launch_session.py compiled cleanly with zero syntax errors!")
except Exception as e:
    print(f"[FATAL] Syntax error after patch: {e}")
    shutil.copy2(backup_path, file_path)
    print("[REVERT] Reverted to original backup file.")
