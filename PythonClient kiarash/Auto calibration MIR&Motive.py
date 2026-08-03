# ==============================================================================
# Author: Kiarash Amiri
# Email: S322803@studenti.polito.it
# ==============================================================================
# GitHub: https://github.com/kiarashAmiri-polito2023
#
# Description:
# - Connects to Motive streaming via universal local loopback (127.0.0.1) 
#   to bypass network/firewall barriers.
# - Prompts the user for the MiR robot IP address dynamically at runtime.
# - Automatically detects 'mir' or 'robot' rigid bodies without unnecessary prompts.
# - Guides the user through a 6-point spatial calibration with a 2-second 
#   physical stabilization settling time and robust auto-retry logic.
# - Computes, validates, and saves the final Affine Transformation Matrix 
#   ('mir_to_motive_matrix.npy') using OpenCV.
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


CALIBRATION_POINTS = 6
SETTLING_TIME_SEC = 2.0  # 2 seconds physical stabilization time


class AutoCalibrator:
    def __init__(self, mir_ip):
        self.mir_ip = mir_ip
        self.mir_api_url = f"http://{self.mir_ip}/api/v2.0.0/status"
        self.mir_headers = {"Accept-Language": "en_US", "Content-Type": "application/json"}
        
        self.natnet_client = None
        self.id_to_name = {}
        self.rb_names = []
        self.target_rb_name = None  
        self.latest_motive_pos = {} 
        
        self.mir_points = []        
        self.motive_points = []     
        self.model_def_received = False
        
    # --- NatNet Callbacks ---
    def _on_model_definitions(self, data_descs):
        self.id_to_name = {}
        self.rb_names = []
        for desc in data_descs.rigid_body_list:
            rb_id = getattr(desc, 'id_num', getattr(desc, 'rigid_body_id', None))
            rb_name = getattr(desc, 'sz_name', getattr(desc, 'rb_name', None))
            if rb_id is not None and rb_name is not None:
                if isinstance(rb_name, bytes):
                    rb_name = rb_name.decode('utf-8', errors='ignore')
                self.id_to_name[rb_id] = rb_name
                if rb_name not in self.rb_names:
                    self.rb_names.append(rb_name)
        self.model_def_received = True


    def _on_rigid_body(self, new_id, position, rotation):
        if new_id not in self.id_to_name:
            return
        name = self.id_to_name[new_id]
        
        if position is not None and not np.isnan(position[0]):
            # X = pos[0], Z = pos[2] (converted to mm)
            self.latest_motive_pos[name] = (position[0] * 1000.0, position[2] * 1000.0)
        else:
            self.latest_motive_pos[name] = None


    def connect_to_natnet(self):
        client = NatNetClient()
        client.set_client_address('127.0.0.1')
        client.set_server_address('127.0.0.1')
        client.set_use_multicast(True)
        client.rigid_body_listener = self._on_rigid_body
        client.model_def_listener = self._on_model_definitions


        self._natnet_thread = threading.Thread(target=client.run, daemon=True)
        self._natnet_thread.start()
        time.sleep(1.5)
        self.natnet_client = client


    def build_rigid_body_map(self):
        timeout_sock = 0
        while (not hasattr(self.natnet_client, 'command_socket') or self.natnet_client.command_socket is None) and timeout_sock < 30:
            time.sleep(0.1)
            timeout_sock += 1


        try:
            if self.natnet_client.command_socket is not None:
                self.natnet_client.send_request(
                    self.natnet_client.command_socket, 
                    self.natnet_client.NAT_REQUEST_MODELDEF, 
                    "", 
                    (self.natnet_client.server_ip_address, self.natnet_client.command_port)
                )
        except Exception:
            pass


        timeout = 0
        while not self.model_def_received and timeout < 30:
            time.sleep(0.2)
            timeout += 1


    # --- MiR API Helper ---
    def get_mir_status(self):
        try:
            response = requests.get(self.mir_api_url, headers=self.mir_headers, timeout=3)
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


        print("Connecting to local Motive stream (127.0.0.1)...")
        self.connect_to_natnet()
        self.build_rigid_body_map()
        
        if not self.rb_names:
            print("\n[CRITICAL] No Rigid Bodies found in Motive. Ensure streaming is ON.")
            return


        # Smart Auto-Detection for 'mir' or 'robot' without bothering about other bodies
        candidate_rb = None
        for name in self.rb_names:
            if "mir" in name.lower() or "robot" in name.lower():
                candidate_rb = name
                break
        
        if candidate_rb:
            confirm = input(f"\nTarget robot detected as '{candidate_rb}'. Is this correct? (y/n): ").strip().lower()
            if confirm == 'y':
                self.target_rb_name = candidate_rb
            else:
                print("\nAvailable Rigid Bodies in Motive:")
                for name in self.rb_names:
                    print(f"   - {name}")
                self.target_rb_name = input("\nEnter the exact name of the Robot's Rigid Body: ").strip()
        else:
            print("\nCould not auto-detect 'mir' or 'robot'. Available Rigid Bodies in Motive:")
            for name in self.rb_names:
                print(f"   - {name}")
            self.target_rb_name = input("\nEnter the exact name of the Robot's Rigid Body: ").strip()


        if self.target_rb_name not in self.rb_names:
            print(f"[ERROR] '{self.target_rb_name}' not found. Exiting.")
            return
            
        print(f"\n[SUCCESS] Locked onto Rigid Body: '{self.target_rb_name}'.")


        # 3. The Interactive Calibration Loop (with Retry Logic)
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


        try:
            self.natnet_client.shutdown()
        except Exception:
            pass


if __name__ == '__main__':
    user_mir_ip = input("Enter the MiR robot IP address (e.g. 192.168.12.20): ").strip()
    if not user_mir_ip:
        user_mir_ip = "192.168.12.20" # Fallback default
        print(f"No input received. Using default IP: {user_mir_ip}")
        
    calibrator = AutoCalibrator(user_mir_ip)
    calibrator.run()
