# -*- coding: utf-8 -*-
import os

file_path = os.path.join("agents", "project_snapshot.py")
if not os.path.exists(file_path):
    print("[ERROR] project_snapshot.py not found!")
    exit(1)

with open(file_path, "r", encoding="utf-8") as f:
    code = f.read()

# Fix 1: Pass "all" as stdin to sub-agents to avoid interactive prompts, and correct session path formatting
old_run_sub_agent = """def run_sub_agent(agent_name, session_name):
    agent_path = AGENTS_DIR / agent_name
    if not agent_path.exists():
        return {"agent": agent_name, "status": "NOT_FOUND", "output": ""}
    try:
        cmd = [sys.executable, str(agent_path)]
        if session_name:
            cmd.append(session_name)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=str(PROJECT_ROOT), encoding="utf-8", errors="replace")
        return {"agent": agent_name, "status": "OK" if proc.returncode == 0 else "ERROR", "output": proc.stdout[-2000:] if proc.stdout else "", "errors": proc.stderr[-500:] if proc.stderr else ""}"""

new_run_sub_agent = """def run_sub_agent(agent_name, session_name):
    agent_path = AGENTS_DIR / agent_name
    if not agent_path.exists():
        return {"agent": agent_name, "status": "NOT_FOUND", "output": ""}
    try:
        cmd = [sys.executable, str(agent_path)]
        if session_name:
            # Pass correct relative path for session_analysis
            if agent_name == "run_session_analysis.py":
                cmd.append(os.path.join("sessions", session_name))
            else:
                cmd.append(session_name)
        
        # Pass "all" into stdin to bypass any interactive menus in video_quality_agent
        proc = subprocess.run(cmd, input="all\n", capture_output=True, text=True, timeout=180, cwd=str(PROJECT_ROOT), encoding="utf-8", errors="replace")
        return {"agent": agent_name, "status": "OK" if proc.returncode == 0 else "ERROR", "output": proc.stdout[-2000:] if proc.stdout else "", "errors": proc.stderr[-500:] if proc.stderr else ""}"""

if old_run_sub_agent in code:
    code = code.replace(old_run_sub_agent, new_run_sub_agent)
    print("[OK] project_snapshot.py patched to handle sub-agents programmatically!")
else:
    # Try flexible replacement if spacing is different
    print("[WARN] Verbatim pattern not found, trying flexible update...")
    code = code.replace('proc = subprocess.run(cmd, capture_output=True', 'proc = subprocess.run(cmd, input="all\\n", capture_output=True')

with open(file_path, "w", encoding="utf-8") as f:
    f.write(code)

print("[VERIFY] Re-running snapshot to verify...")
os.system("python agents/project_snapshot.py")
