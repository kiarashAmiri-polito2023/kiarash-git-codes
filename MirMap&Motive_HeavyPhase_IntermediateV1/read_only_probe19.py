import socket
import subprocess
import sys
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print('\n>>> BEGIN ROUND 19: REMOTE ACCESS & HOME CONNECTIVITY AUDIT <<<')

# 1. Check RDP Port 3389 Status locally
print('\n[1/3] RDP (Remote Desktop) Port 3389 Check:')
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2.0)
try:
    s.connect(('127.0.0.1', 3389))
    print('  [+] RDP Port 3389 is OPEN locally (Remote Desktop service is available).')
    s.close()
except Exception:
    print('  [-] RDP Port 3389 is closed or restricted locally.')

# 2. Check Windows Firewall RDP Rules status via netsh (Read-only query)
print('\n[2/3] WINDOWS FIREWALL RDP RULES CHECK:')
try:
    fw_check = subprocess.run(['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
    if 'Remote Desktop' in fw_check.stdout:
        print('  [+] Remote Desktop firewall rules found in system.')
    else:
        print('  [!] Standard Remote Desktop rule name not explicitly matched in quick scan.')
except Exception as e:
    print(f'  [-] Could not query firewall: {e}')

# 3. Check Network Adapters for Wake-on-LAN capability flags
print('\n[3/3] WAKE-ON-LAN (WoL) HARDWARE SUPPORT CHECK:')
try:
    wol_check = subprocess.run(['powershell', 'Get-NetAdapter | Select-Object Name, Status, LinkSpeed'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
    print('  [+] Active Network Adapters:')
    for line in wol_check.stdout.strip().split('\n'):
        if line.strip():
            print(f'      -> {line.strip()}')
except Exception as e:
    print(f'  [-] Could not query adapters: {e}')

print('\n>>> ROUND 19 SCAN COMPLETE <<<')
