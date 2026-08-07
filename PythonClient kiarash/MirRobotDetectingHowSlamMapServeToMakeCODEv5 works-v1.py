#!/usr/init/env python3
# -*- coding: utf-8 -*-
"""
Author: Kiarash Amiri Polito
Email: s322803@studenti.polito.it
GitHub: https://github.com/kiarashAmiri-polito2023/kiarash-git-codes.git

Changelog & Updates (Compared to previous version):
  * Fixed the attribute error by treating client.get_topics() as a list instead of a dictionary.
  * Updated the loop to iterate through the list of active topic names and filter relevant topics properly.
  * Improved diagnostic output to cleanly display active map, scan, and odometry topics on the MiR robot.
"""

import roslibpy

# ===========================================================================
# Configuration
# ===========================================================================
ROBOT_IP = '192.168.12.20'
ROS_PORT = 9090

print("=====================================================")
print("  MiR ROS Topic Diagnostics & Map Finder (Fixed)")
print("=====================================================")

client = roslibpy.Ros(host=ROBOT_IP, port=ROS_PORT)
client.run()

if client.is_connected:
    print("[SUCCESS] Connected to ROS Bridge!")
    print("[INFO] Fetching all active topics from the robot...")
    
    try:
        topics_list = client.get_topics()
        print("\n--- Relevant ROS Topics on MiR ---")
        for topic in sorted(topics_list):
            # Filter and highlight potential map, scan, odom, or costmap topics
            if any(k in topic.lower() for k in ['map', 'scan', 'odom', 'pose', 'costmap']):
                print(f"  [MATCH] {topic}")
        print("----------------------------------\n")
    except Exception as e:
        print(f"[ERROR] Could not fetch topics: {e}")
        
    client.terminate()
else:
    print("[CRITICAL] Could not connect to ROS Bridge.")