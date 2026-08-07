import psutil
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print('\n>>> BEGIN ROUND 15: SYSTEM RESOURCE & PROCESS AUDIT <<<')

# 1. RAM and CPU Health Check
print('\n[1/2] HARDWARE RESOURCE HEALTH:')
ram = psutil.virtual_memory()
cpu_percent = psutil.cpu_percent(interval=1)

print(f'  [+] Total RAM: {ram.total / (1024**3):.1f} GB')
print(f'  [+] Available RAM: {ram.available / (1024**3):.1f} GB ({ram.available/ram.total*100:.1f}%)')
print(f'  [+] Current CPU Load: {cpu_percent}%')

if ram.available / (1024**3) > 16.0:
    print('  [+] EXCELLENT: Plenty of RAM for UR-MCP Server + LMStudio + ROS.')
else:
    print('  [-] WARNING: RAM is running low. Might affect local LLM inference speed.')

# 2. Python Zombie Process Check
print('\n[2/2] ZOMBIE / HEAVY PYTHON PROCESS CHECK:')
python_procs = []
for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
    try:
        if 'python' in proc.info['name'].lower():
            mem_mb = proc.info['memory_info'].rss / (1024**2)
            python_procs.append((proc.info['pid'], mem_mb))
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

python_procs = sorted(python_procs, key=lambda x: x[1], reverse=True)
print(f'  [+] Found {len(python_procs)} active Python processes.')
for pid, mem in python_procs[:3]:
    print(f'      -> PID: {pid} consuming {mem:.1f} MB')

print('\n>>> ROUND 15 SCAN COMPLETE <<<')
