# ==============================================================================
# Author: Kiarash Amiri
# Email: S322803@studenti.polito.it
# GitHub: https://github.com/kiarashAmiri-polito2023
#
# Workflow Description:
# - Connects to the local SLAM of the robot (MiR API) and Motive software (NatNet).
# - Features a robust polling loop to guarantee Motive Rigid Body detection.
# - Auto-detects Rigid Bodies containing 'mir' or 'robot' with a simple y/n confirmation.
# - Guides the user through a 6-point spatial calibration process.
# - Monitors the robot's state via API (Waits for 'Ready' state + 2s settling time).
# - Features an auto-retry logic: if data is corrupted or out of sight, it retries.
# - Computes the Affine Transformation Matrix using OpenCV and saves it.
# ==============================================================================

import time
import threading
import requests
import numpy as np
import cv2
import sys

try:
    from NatNetClient import NatNetClient
except ImportError:
    print("[ERROR] NatNetClient.py not found. Please place it in the same directory.")
    sys.exit(1)

# --- Configuration ---
MIR_IP = "192.168.12.20"
MIR_API_URL = f"http://{MIR_IP}/api/v2.0.0/status"
MIR_HEADERS = {"Accept-Language": "en_US", "Content-Type": "application/json"}

CALIBRATION_POINTS = 6
SETTLING_TIME_SEC = 2.0  

class AutoCalibrator:
    def __init__(self):
        self.natnet = NatNetClient()
        self.rb_names = {}          
        self.target_rb_name = None  
        self.latest_motive_pos = {} 
        
        self.mir_points = []        
        self.motive_points = []     
        
    # --- NatNet Callbacks ---
    def _on_model_def(self, data_descs):
        for desc in data_descs.rigid_body_list:
            rb_id = getattr(desc, 'id_num', getattr(desc, 'rigid_body_id', None))
            rb_name = getattr(desc, 'sz_name', getattr(desc, 'rb_name', None))
            if rb_id is not None and rb_name is not None:
                name_str = rb_name.decode('utf-8') if isinstance(rb_name, bytes) else rb_name
                self.rb_names[rb_id] = name_str

    def _on_rigid_body(self, new_id, position, rotation):
        if new_id in self.rb_names:
            name = self.rb_names[new_id]
            if position is not None and not np.isnan(position[0]):
                self.latest_motive_pos[name] = (position[0] * 1000.0, position[2] * 1000.0)
            else:
                self.latest_motive_pos[name] = None

    # --- MiR API Helper ---
    def get_mir_status(self):
        try:
            response = requests.get(MIR_API_URL, headers=MIR_HEADERS, timeout=3)
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    # --- Main Workflow ---
    def run(self):
        print("=====================================================")
        print("  MiR - OptiTrack Auto-Calibration Tool Initialized  ")
        print("=====================================================\n")

        # 1. Connect to NatNet via Local Loopback
        self.natnet.set_client_address('127.0.0.1')
        self.natnet.set_server_address('127.0.0.1')
        self.natnet.set_use_multicast(True)
        self.natnet.model_def_listener = self._on_model_def
        self.natnet.rigid_body_listener = self._on_rigid_body
        
        threading.Thread(target=self.natnet.run, daemon=True).start()
        
        print("Requesting Rigid Body list from Motive server...")
        
        wait_time = 0
        while not self.rb_names and wait_time < 10:
            time.sleep(1)
            wait_time += 1
            print(f"Waiting for Motive data... ({wait_time}/10)")
            try:
                self.natnet.send_request(self.natnet.command_socket, 5, "", self.natnet.server_address, self.natnet.command_port)
            except AttributeError:
                pass 
        
        # 2. Handshake: Identify Robot (Auto-detect logic)
        if not self.rb_names:
            print("\n[CRITICAL] No Rigid Bodies found in Motive after 10 seconds.")
            print("Ensure streaming is ON and Local Interface is set to 127.0.0.1 in Motive.")
            return

        print("\nScanning for MiR robot in Motive's Rigid Bodies...")
        target_name = None
        
        for r_id, r_name in self.rb_names.items():
            lower_name = r_name.lower()
            if 'mir' in lower_name or 'robot' in lower_name:
                target_name = r_name
                break
                
        if target_name:
            confirm = input(f"\n? Target robot detected as '{target_name}'. Is this correct? (y/n): ").strip().lower()
            if confirm == 'y':
                self.target_rb_name = target_name
                print(f"\n[SUCCESS] Locked onto Rigid Body: '{self.target_rb_name}'.")
            else:
                print("\n[INFO] Calibration aborted by user. Please check Motive Rigid Body names.")
                return
        else:
            print("\n[ERROR] Could not automatically find any Rigid Body containing 'mir' or 'robot'.")
            print("Available Rigid Bodies are:")
            for r_id, r_name in self.rb_names.items():
                print(f" - {r_name}")
            return

        # 3. The Interactive Calibration Loop
        current_point = 1
        
        while current_point <= CALIBRATION_POINTS:
            print("\n-----------------------------------------------------")
            input(f"STEP {current_point}/{CALIBRATION_POINTS}: Send the robot to Point {current_point} via dashboard. Press ENTER to start monitoring...")
            
            print("Monitoring MiR state API...")
            monitoring = True
            
            while monitoring:
                status = self.get_mir_status()
                if status is None:
                    print("[WARNING] Waiting for MiR network connection...")
                    time.sleep(1)
                    continue
                
                state_text = status.get("state_text", "")
                
                if state_text == "Ready":
                    print(f"Robot state is 'Ready'. Applying {SETTLING_TIME_SEC}s settling time...")
                    time.sleep(SETTLING_TIME_SEC)
                    
                    final_status = self.get_mir_status()
                    if final_status and final_status.get("state_text") == "Ready":
                        
                        motive_pos = self.latest_motive_pos.get(self.target_rb_name)
                        
                        if motive_pos is None:
                            print(f"\n[ERROR] Motive lost track of '{self.target_rb_name}'!")
                            print("--> RETRYING STEP. Please fix tracking and try again.")
                            monitoring = False 
                            continue
                            
                        mir_x = final_status["position"]["x"] * 1000.0
                        mir_y = final_status["position"]["y"] * 1000.0
                        
                        self.mir_points.append((mir_x, mir_y))
                        self.motive_points.append(motive_pos)
                        
                        print(f"\n[SYNCED] Point {current_point} successfully captured!")
                        print(f"   MiR (mm):    X: {mir_x:.1f}, Y: {mir_y:.1f}")
                        print(f"   Motive (mm): X: {motive_pos[0]:.1f}, Y: {motive_pos[1]:.1f}")
                        
                        current_point += 1 
                        monitoring = False 
                        
                    else:
                        print("[INFO] Robot state changed during settling time. Resuming monitoring...")
                
                time.sleep(0.5)

        # 4. Compute Transformation Matrix
        print("\n=====================================================")
        print("All points captured. Computing Transformation Matrix...")
        
        mir_array = np.array(self.mir_points, dtype=np.float32)
        motive_array = np.array(self.motive_points, dtype=np.float32)
        
        matrix, inliers = cv2.estimateAffinePartial2D(mir_array, motive_array)
        
        if matrix is not None:
            print("\n[SUCCESS] Calibration Matrix generated successfully!")
            print(matrix)
            
            np.save("mir_to_motive_matrix.npy", matrix)
            print("\nMatrix saved to 'mir_to_motive_matrix.npy'.")
            
            transformed_mir = cv2.transform(np.array([mir_array]), matrix)[0]
            errors = np.linalg.norm(motive_array - transformed_mir, axis=1)
            mean_error = np.mean(errors)
            print(f"Average Calibration Error (Reprojection): {mean_error:.2f} mm")
        else:
            print("\n[CRITICAL ERROR] Matrix computation failed. Points might be collinear or invalid.")

        self.natnet.shutdown()

if __name__ == '__main__':
    calibrator = AutoCalibrator()
    calibrator.run()