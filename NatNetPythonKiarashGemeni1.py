import time
import numpy as np
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import messagebox
import pickle
from NatNetClient import NatNetClient

# تنظیمات و آستانه‌ها
DANGER_THRESHOLD_MM = 100.0
WARNING_THRESHOLD_MM = 500.0
MIN_APPROACH_SPEED_MMPS = 20.0

class MultiRigidBodyTracker:
    def __init__(self):
        self.natnet = NatNetClient()
        self.rigid_bodies = {}
        self.selected_bodies = []
        self.body_map = {}  # برای نگاشت ID به نام واقعی
        self.is_recording = False
        self.start_time = 0
        self.model_def_received = False
        self.available_bodies = [] # لیست موقت برای ذخیره نام‌های دریافتی از شبکه
        
    def receive_rigid_body_frame(self, new_id, position, rotation):
        """دریافت مختصات زنده از شبکه"""
        if not self.is_recording:
            return
            
        current_time = time.time() - self.start_time
        # پیدا کردن نام واقعی از روی ID
        body_name = self.body_map.get(new_id, None)
        
        if body_name and body_name in self.selected_bodies:
            pos = position if position is not None else [np.nan, np.nan, np.nan]
            self.rigid_bodies[body_name]['time'].append(current_time)
            self.rigid_bodies[body_name]['pos'].append(pos)

    def receive_model_definitions(self, data_descs):
        """ذخیره نام‌ها در پس‌زمینه بدون مسدود کردن ترد شبکه"""
        self.available_bodies = []
        # استخراج نام اجسام صلب از اطلاعات دریافتی
        for rb in data_descs.rigid_body_list:
            raw_name = rb.sz_name
            name = raw_name.decode('utf-8') if isinstance(raw_name, bytes) else raw_name
            body_id = rb.id_num
            self.available_bodies.append((body_id, name))
            
        self.model_def_received = True

    def interactive_selection(self):
        """پرسش از کاربر در ترد اصلی برنامه برای جلوگیری از مسدود شدن ترمینال"""
        print("\n--- Select which Rigid Bodies to record ---")
        print("(Anything you answer 'no' to will NOT be logged or plotted.)\n")
        
        for body_id, name in self.available_bodies:
            ans = input(f"Record '{name}'? (yes/no): ").strip().lower()
            if ans.startswith('y'):
                self.selected_bodies.append(name)
                self.rigid_bodies[name] = {'time': [], 'pos': []}
                self.body_map[body_id] = name
                
        print("\nWill be recorded and plotted:", ", ".join(self.selected_bodies) if self.selected_bodies else "(none)")
        print("-" * 44 + "\n")

    def auto_trim_data(self):
        root = tk.Tk()
        root.withdraw()
        first_valid, last_valid = None, None
        
        for body in self.selected_bodies:
            if len(self.rigid_bodies[body]['pos']) == 0: continue
            pos_array = np.array(self.rigid_bodies[body]['pos'])
            valid_indices = np.where(~np.isnan(pos_array[:, 0]))[0]
            if len(valid_indices) > 0:
                first_valid = valid_indices[0] if first_valid is None else min(first_valid, valid_indices[0])
                last_valid = valid_indices[-1] if last_valid is None else max(last_valid, valid_indices[-1])
                
        if first_valid is not None and last_valid is not None:
            ans = messagebox.askyesno("Auto-Trim", "Active frames detected. Remove dead time (start/end)?")
            if ans:
                for body in self.selected_bodies:
                    self.rigid_bodies[body]['time'] = self.rigid_bodies[body]['time'][first_valid:last_valid+1]
                    self.rigid_bodies[body]['pos'] = self.rigid_bodies[body]['pos'][first_valid:last_valid+1]
        root.destroy()

    def generate_dashboard(self):
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        ax.set_title("Combined 3D Trajectory & Occlusion Map")
        colors = ['b', 'g', 'm', 'c', 'orange', 'purple']
        max_gaps = {}

        for idx, body in enumerate(self.selected_bodies):
            if len(self.rigid_bodies[body]['pos']) == 0: continue
            pos = np.array(self.rigid_bodies[body]['pos'])
            time_arr = np.array(self.rigid_bodies[body]['time'])
            
            valid = ~np.isnan(pos[:, 0])
            ax.plot(pos[valid, 0], pos[valid, 1], pos[valid, 2], color=colors[idx%len(colors)], label=body)
            
            nan_indices = np.where(np.isnan(pos[:, 0]))[0]
            if len(nan_indices) > 0:
                cross_points = pos[nan_indices - 1]
                ax.scatter(cross_points[:, 0], cross_points[:, 1], cross_points[:, 2], 
                           color='r', marker='x', s=100, label=f'Occlusion ({body})')
                
            gap_times = np.diff(time_arr[valid])
            max_gaps[body] = np.max(gap_times) if len(gap_times) > 0 else 0
            
        ax.legend()
        info_text = "Max Gap Durations:\n" + "\n".join([f"{k}: {v:.3f} s" for k, v in max_gaps.items()])
        fig.text(0.02, 0.02, info_text, fontsize=10, bbox=dict(facecolor='white', alpha=0.8))
        plt.show()

    def run(self):
        self.natnet.rigid_body_listener = self.receive_rigid_body_frame
        self.natnet.model_def_listener = self.receive_model_definitions
        
        # ۱. راه‌اندازی ارتباطات شبکه
        if not self.natnet.run():
            print("ERROR: Could not start streaming client.")
            return

        time.sleep(1) # زمان برای تثبیت شبکه
        
        # ۲. ارسال درخواست برای دریافت لیست نام‌ها از موتیو
        print("Requesting Object Data from Motive...")
        self.natnet.send_request(self.natnet.command_socket, self.natnet.NAT_REQUEST_MODELDEF, "", (self.natnet.server_ip_address, self.natnet.command_port))
        
        # منتظر می‌مانیم تا موتیو جواب بدهد (با محدودیت زمانی برای جلوگیری از قفل شدن)
        timeout_counter = 0
        while not self.model_def_received and timeout_counter < 50:
            time.sleep(0.1)
            timeout_counter += 1
            
        if not self.model_def_received:
            print("ERROR: Did not receive model definitions from Motive.")
            print("لطفاً مطمئن شوید که فایل NatNetClient.py را طبق دستورات قبلی آپدیت کرده‌اید.")
            self.natnet.shutdown()
            return
            
        # ۳. فراخوانی پرسش از کاربر در مکان امن (ترد اصلی)
        self.interactive_selection()
            
        if not self.selected_bodies:
            print("No bodies selected. Exiting.")
            self.natnet.shutdown()
            return

        # ۴. شروع استریم و پلات زنده
        self.is_recording = True
        self.start_time = time.time()
        
        plt.ion()
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        
        print("\nStreaming... Press Ctrl+C to STOP.")
        try:
            while True:
                ax.cla()
                for body in self.selected_bodies:
                    if len(self.rigid_bodies[body]['pos']) > 0:
                        pos = np.array(self.rigid_bodies[body]['pos'])
                        valid = ~np.isnan(pos[:, 0])
                        ax.plot(pos[valid, 0], pos[valid, 1], pos[valid, 2])
                plt.pause(0.05)
        except KeyboardInterrupt:
            self.is_recording = False
            self.natnet.shutdown()
            plt.ioff()
            plt.close(fig)
            
        # ۵. پردازش و ذخیره‌سازی
        self.auto_trim_data()
        self.generate_dashboard()
        
        with open(f"MocapSession_{int(time.time())}.pkl", 'wb') as f:
            pickle.dump(self.rigid_bodies, f)

if __name__ == "__main__":
    tracker = MultiRigidBodyTracker()
    tracker.run()