import os
import sys
import socket
import psutil
import subprocess

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print('\n>>> BEGIN ROUND 18: 80-DIMENSIONAL DEEP CORE & MCP READINESS AUDIT <<<')

# 1. MCP Network & Port Collision Audit
print('\n[1/4] NETWORK PORT COLLISION AUDIT (Checking MCP & ROS typical ports):')
ports_to_check = [9090, 1234, 11434, 5000, 8080]
for port in ports_to_check:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1', port))
        print(f'  [+] Port {port}: FREE and ready for use.')
        s.close()
    except socket.error as e:
        print(f'  [-] Port {port}: IN USE (Collision potential or service running)')

# 2. Docker Daemon Readiness (Often required for URSim / MCP containers)
print('\n[2/4] DOCKER SERVICE READINESS (For UR Track B):')
try:
    docker_check = subprocess.run(['docker', 'info'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
    if docker_check.returncode == 0:
        print('  [+] Docker Daemon: RUNNING. Ready for URSim deployment.')
    else:
        print('  [-] Docker Daemon: STOPPED or ERRORED.')
except FileNotFoundError:
    print('  [-] Docker CLI: NOT INSTALLED on this system.')
except subprocess.TimeoutExpired:
    print('  [-] Docker Daemon: TIMEOUT (Hung process).')

# 3. Deep Python Environment Variables (Checking for ROS/Motive conflicts)
print('\n[3/4] PYTHON & ROS ENVIRONMENT VARIABLES:')
env_keys = ['PYTHONPATH', 'ROS_MASTER_URI', 'ROS_IP', 'NATNET']
found_env = False
for key in env_keys:
    if key in os.environ:
        print(f'  [+] {key} is SET: {os.environ[key]}')
        found_env = True
if not found_env:
    print('  [!] No explicit ROS or custom PYTHONPATH variables detected (Standard behavior for local pip envs).')

# 4. Storage Bottleneck Check for local LLMs (Drive D:)
print('\n[4/4] DEEP STORAGE AUDIT FOR LLM EXPANSION:')
try:
    usage = psutil.disk_usage('D:\\')
    free_gb = usage.free / (1024**3)
    print(f'  [+] Drive D:\\ Free Space: {free_gb:.1f} GB')
    if free_gb > 100:
        print('  [+] Storage is OPTIMAL for downloading larger models (e.g. Qwen3-14B/72B) if Professor requests it.')
    else:
        print('  [-] WARNING: Storage might become a bottleneck for large LLMs.')
except Exception as e:
    print(f'  [-] Could not read drive stats: {e}')

print('\n>>> ROUND 18 SCAN COMPLETE <<<')
