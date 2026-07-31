import requests
 #Added a Python script to probe the MiR robot's REST API at 192.168.12.20.
 #Sends an HTTP GET request without authentication parameters.
 #Checks if the /status endpoint is open (Status 200) or locked (Status 401).
 #Extracts live X, Y, and Theta coordinates if access is granted.
 #Does NOT send movement commands; strictly read-only diagnostics.




# آدرس آی‌پی ربات شما
IP_ADDRESS = "192.168.12.20"
URL = f"http://{IP_ADDRESS}/api/v2.0.0/status"


# هدرهای ضروری برای ربات MiR
headers = {
    "Accept-Language": "en_US",
    "Content-Type": "application/json"
}


print(f"Testing API connection to {IP_ADDRESS} WITHOUT password...\n")


try:
    # ارسال درخواست به ربات کاملاً بدون رمز عبور
    response = requests.get(URL, headers=headers, timeout=5)
    
    # اگر ربات اجازه ورود داد (سیستم باز است)
    if response.status_code == 200:
        print("[SUCCESS] The robot API is OPEN! No password is required.")
        data = response.json()
        
        pos_x = data.get("position", {}).get("x")
        pos_y = data.get("position", {}).get("y")
        theta = data.get("position", {}).get("orientation")
        
        print(f"--- Live Position ---")
        print(f"X: {pos_x} meters")
        print(f"Y: {pos_y} meters")
        print(f"Theta: {theta} degrees")
        
    # اگر ربات دسترسی را رد کرد (سیستم قفل است)
    elif response.status_code == 401:
        print("[LOCKED] The robot returned Status 401 (Unauthorized).")
        print("این یعنی ربات شما برای دسترسی به API قطعاً به نام کاربری و رمز عبور نیاز دارد.")
        
    # خطاهای ناشناخته دیگر
    else:
        print(f"[UNKNOWN] Received Status Code: {response.status_code}")
        print("Response Text:", response.text)


except requests.exceptions.RequestException as e:
    print(f"[CRITICAL ERROR] Could not connect to the robot. Check your Wi-Fi.")
    print(f"Details: {e}")
