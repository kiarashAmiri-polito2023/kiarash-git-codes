import urllib.request
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
print('\n>>> BEGIN ROUND 4: LMSTUDIO API & WORKSPACE PROBE <<<')

# 1. Test LMStudio Chat API (Crucial for MCP Function Calling)
url = 'http://localhost:1234/v1/chat/completions'
data = json.dumps({
    "model": "qwen/qwen3-vl-8b", 
    "messages": [{"role": "user", "content": "Reply with only the word: READY"}], 
    "max_tokens": 10
}).encode('utf-8')

req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req, timeout=10) as response:
        res = json.loads(response.read().decode('utf-8'))
        answer = res['choices'][0]['message']['content'].strip()
        print(f"  [+] LMStudio Chat API: ONLINE (Model responded: '{answer}')")
except Exception as e:
    print(f"  [-] LMStudio Chat API: OFFLINE or BUSY ({e})")

# 2. Check Workspace readiness for MCP clone
mcp_target = r'D:\kiarash\kiarash git codes\universal-robot-mcp'
if os.path.exists(mcp_target):
    print('  [+] MCP Directory: ALREADY EXISTS in git codes')
else:
    print('  [-] MCP Directory: NOT FOUND (Clear to clone when ready)')

print('>>> ROUND 4 COMPLETE <<<\n')
