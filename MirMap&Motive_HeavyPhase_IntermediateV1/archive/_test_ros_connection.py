# -*- coding: utf-8 -*-
"""
ROS Bridge Connection Test for MiR Robot
Tests: connectivity + topic availability + sample data
No files are modified. Read-only test.
"""
import sys
import time

ROBOT_IP = "192.168.12.20"
ROS_PORT = 9090

TOPICS_TO_TEST = [
    ("/robot_pose", "geometry_msgs/Pose", "Robot position (x,y,yaw)"),
    ("/f_scan",     "sensor_msgs/LaserScan", "Front LiDAR"),
    ("/b_scan",     "sensor_msgs/LaserScan", "Back LiDAR"),
    ("/cmd_vel",    "geometry_msgs/Twist", "Robot velocity commands (ACTION col)"),
    ("/odom",       "nav_msgs/Odometry", "Odometry"),
    ("/map",        "nav_msgs/OccupancyGrid", "SLAM Map"),
]

def main():
    print("=" * 60)
    print("  MiR ROS Bridge Connection Test")
    print("  Target: %s:%d" % (ROBOT_IP, ROS_PORT))
    print("=" * 60)
    print("")

    # --- Step 1: Check roslibpy ---
    print("[1/4] Checking roslibpy...")
    try:
        import roslibpy
        print("  OK - roslibpy imported successfully")
    except ImportError:
        print("  FAIL - roslibpy not installed!")
        sys.exit(1)

    # --- Step 2: Connect ---
    print("")
    print("[2/4] Connecting to ROS Bridge...")
    try:
        client = roslibpy.Ros(host=ROBOT_IP, port=ROS_PORT)
        client.run()
    except Exception as e:
        print("  FAIL - Connection error: %s" % str(e))
        sys.exit(1)

    if not client.is_connected:
        print("  FAIL - client.is_connected is False after run()")
        print("  CHECK: Is the robot ON? Is rosbridge_server running?")
        sys.exit(1)

    print("  OK - Connected to %s:%d" % (ROBOT_IP, ROS_PORT))

    # --- Step 3: Test Topics ---
    print("")
    print("[3/4] Testing topics (5s each)...")
    print("")
    print("  %-25s %-30s %-8s %s" % ("TOPIC", "TYPE", "STATUS", "SAMPLE"))
    print("  " + "-" * 85)

    results = {}
    for topic_name, topic_type, description in TOPICS_TO_TEST:
        received_data = {"count": 0, "sample": None}

        def make_callback(rd):
            def cb(msg):
                rd["count"] += 1
                if rd["sample"] is None:
                    rd["sample"] = msg
            return cb

        try:
            listener = roslibpy.Topic(client, topic_name, topic_type)
            listener.subscribe(make_callback(received_data))
            time.sleep(5)
            listener.unsubscribe()
        except Exception as e:
            received_data["error"] = str(e)

        if received_data["count"] > 0:
            status = "LIVE"
            sample_str = str(received_data["sample"])[:40]
        else:
            status = "SILENT"
            sample_str = "(no data)"

        if "error" in received_data:
            status = "ERROR"
            sample_str = received_data["error"][:40]

        results[topic_name] = status
        print("  %-25s %-30s %-8s %s" % (topic_name, topic_type, status, sample_str))

    # --- Step 4: Summary ---
    print("")
    print("[4/4] Summary")
    print("=" * 60)
    print("  LIVE topics: %d" % sum(1 for v in results.values() if v == "LIVE"))
    print("=" * 60)

    client.terminate()

if __name__ == "__main__":
    main()
