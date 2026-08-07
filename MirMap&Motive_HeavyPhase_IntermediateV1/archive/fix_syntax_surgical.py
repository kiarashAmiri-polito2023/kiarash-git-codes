import sys, os, re, py_compile

launch_path = sys.argv[1]

with open(launch_path, 'r', encoding='utf-8') as f:
    code = f.read()

# 1. پاکسازی هرگونه ایمپورت سرگردان mir_command_logger از داخل متدها
code = re.sub(r'try:\s+from mir_command_logger import MirCommandLogger\s+HAS_CMD_LOGGER = True\s+except ImportError:\s+HAS_CMD_LOGGER = False\s*', '', code)

# 2. بازسازی متد try_connect به ساختار تمیز و اصلی
clean_try_connect = '''    def try_connect(self):
        try:
            import roslibpy
        except ImportError:
            print("[SLAM] WARNING: roslibpy not installed.")
            return False'''

code = re.sub(r'def try_connect\(self\):.*?except ImportError:\s+print\("\[SLAM\] WARNING: roslibpy not installed\."\)\s+return False', clean_try_connect, code, flags=re.DOTALL)

# 3. قرار دادن ایمپورت mir_command_logger در بالای فایل
top_import = '''
try:
    from mir_command_logger import MirCommandLogger
    HAS_CMD_LOGGER = True
except ImportError:
    HAS_CMD_LOGGER = False
'''
if 'from mir_command_logger import MirCommandLogger' not in code:
    if 'import session_manager' in code:
        code = code.replace('import session_manager', 'import session_manager' + top_import, 1)
    else:
        code = top_import + '\n' + code

# 4. اصلاح رشته‌های شکسته print در run_full_pipeline
code = re.sub(r'print\(\s*"[\r\n]+\[pipeline\] Stage:\s*([^"]+)"\)', r'print("\\n[pipeline] Stage: \1")', code)
code = re.sub(r'print\("[\r\n]+\[pipeline\] Stage: ([^"]+)"\)', r'print("\\n[pipeline] Stage: \1")', code)

# 5. اصلاح بلوک ذخیره‌سازی نهایی در main
clean_save_block = '''    print("\\n[INFO] Saving final data files...")
    if slam_ok:
        if 'cmd_logger' in locals() and cmd_logger is not None:
            try:
                cmd_logger.stop()
                cmd_logger.save_final()
            except Exception as e:
                print(f"[launch_session] cmd save error: {e}")
        slam_logger.save_final()'''

code = re.sub(r'print\("(\\n)?\[INFO\] Saving final data files\.\.\."\)\s+if slam_ok:.*?slam_logger\.save_final\(\)', clean_save_block, code, flags=re.DOTALL)

with open(launch_path, 'w', encoding='utf-8') as f:
    f.write(code)

print("[INFO] Surgical fixes applied to launch_session.py")

# اعتبارسنجی سینتکس
try:
    py_compile.compile(launch_path, doraise=True)
    print("\n>>> [SUCCESS] launch_session.py SYNTAX IS 100% VALID! <<<")
except py_compile.PyCompileError as e:
    print(f"\n>>> [FAIL] Syntax error: {e}")
    lines = code.splitlines()
    m = re.search(r'line (\d+)', str(e))
    if m:
        ln = int(m.group(1))
        start = max(0, ln - 6)
        end = min(len(lines), ln + 5)
        print(f"--- Context around line {ln} ---")
        for i in range(start, end):
            prefix = ">> " if i + 1 == ln else "   "
            print(f"{prefix}{i+1}: {lines[i]}")