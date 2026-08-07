#!/usr/bin/env python3
"""
WSL Goal-Oriented Orchestrator v1.0
LAW80: Evidence Verification | LAW81: Bridge Protocol
LAW82: Adaptive Loop | LAW83: Crash Resume
LAW88: Logging | LAW92: Heartbeat/Throttle
"""

import json
import os
import sys
import time
import subprocess
import hashlib
import threading
from datetime import datetime

# ============ PATHS (WSL perspective) ============
ORCH = "/mnt/c/Users/Admin/kiarash works/kiarash git codes/MirMap&Motive_HeavyPhase_IntermediateV1/AUTO_GOAL_ORCHESTRATOR"
REQ = os.path.join(ORCH, "bridge", "request.json")
RES = os.path.join(ORCH, "bridge", "response.json")
PROGRESS = os.path.join(ORCH, "state", "progress.json")
HEARTBEAT = os.path.join(ORCH, "state", "heartbeat.json")
THROTTLE = os.path.join(ORCH, "state", "throttle_state.json")
ACTION_LOG = os.path.join(ORCH, "logs", "action_log.jsonl")
DOSSIER = os.path.join(ORCH, "memory", "LIVING_DOSSIER.md")

POLL_SEC = 2
HB_SEC = 30
running = True
last_req_hash = ""

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

def hash_file(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return ""

def log_action(action_type, details):
    """LAW88: Timestamped JSONL logging"""
    entry = {"timestamp": now(), "type": action_type, "details": details}
    try:
        with open(ACTION_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print("[LOG ERR] " + str(e))

def append_dossier(text):
    """Append to LIVING_DOSSIER.md (LAW88)"""
    try:
        os.makedirs(os.path.dirname(DOSSIER), exist_ok=True)
        with open(DOSSIER, "a", encoding="utf-8") as f:
            f.write("\n---\n\n[" + now() + "]\n\n" + text + "\n")
    except Exception:
        pass

def heartbeat_loop():
    """LAW92: Heartbeat every 30 seconds"""
    while running:
        try:
            write_json(HEARTBEAT, {
                "last_beat": now(),
                "orchestrator_pid": os.getpid(),
                "status": "RUNNING"
            })
        except Exception:
            pass
        time.sleep(HB_SEC)

def execute_command(command, timeout=120):
    """Execute PowerShell command from WSL via powershell.exe"""
    log_action("EXEC_START", {"cmd_preview": command[:200]})
    start_t = time.time()
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )
        elapsed = round(time.time() - start_t, 2)
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout[:8000],
            "stderr": result.stderr[:3000],
            "elapsed_sec": elapsed
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "TIMEOUT after " + str(timeout) + "s", "elapsed_sec": timeout}
    except Exception as e:
        return {"exit_code": -1, "stdout": "", "stderr": str(e), "elapsed_sec": 0}

def verify_evidence(result, criteria):
    """LAW80: Evidence-Based Verification - minimum 3 independent checks"""
    if not criteria:
        return "NEEDS_ANALYSIS", {"reason": "no_criteria_in_request"}

    evidence = {}
    passed = 0
    total = 0

    # Check: exit_code
    if "exit_code" in criteria:
        total += 1
        exp = criteria["exit_code"]
        act = result["exit_code"]
        ok = (act == exp)
        evidence["exit_code"] = {"expected": exp, "actual": act, "pass": ok}
        if ok:
            passed += 1

    # Check: stdout_contains
    if "stdout_contains" in criteria:
        for text in criteria["stdout_contains"]:
            total += 1
            found = text in result["stdout"]
            evidence["stdout_contains:" + text[:50]] = {"expected": text[:50], "found": found, "pass": found}
            if found:
                passed += 1

    # Check: stderr_empty
    if criteria.get("stderr_empty", False):
        total += 1
        clean = len(result["stderr"].strip()) == 0
        evidence["stderr_empty"] = {"expected": True, "actual": clean, "pass": clean}
        if clean:
            passed += 1

    # Check: file_exists (Windows paths auto-converted to WSL)
    if "file_exists" in criteria:
        for fpath in criteria["file_exists"]:
            total += 1
            wsl_p = fpath.replace("C:\\", "/mnt/c/").replace("\\", "/")
            exists = os.path.exists(wsl_p)
            evidence["file:" + os.path.basename(fpath)] = {"path": fpath, "exists": exists, "pass": exists}
            if exists:
                passed += 1

    # Check: content_contains
    if "content_contains" in criteria:
        for item in criteria["content_contains"]:
            total += 1
            fpath = item.get("file", "")
            text = item.get("text", "")
            wsl_p = fpath.replace("C:\\", "/mnt/c/").replace("\\", "/")
            try:
                with open(wsl_p, "r", encoding="utf-8") as f:
                    content = f.read()
                found = text in content
            except Exception:
                found = False
            evidence["content:" + os.path.basename(fpath)] = {"text": text[:50], "found": found, "pass": found}
            if found:
                passed += 1

    # Verdict
    if total == 0:
        return "NEEDS_ANALYSIS", evidence
    if passed == total:
        return "VERIFIED_SUCCESS", evidence
    if passed >= 1:
        return "PARTIAL", evidence
    return "FAILED", evidence

def process_request(req):
    """Process one bridge request: execute + verify + respond"""
    command = req.get("command", "")
    goal_id = req.get("goal_id", "UNKNOWN")
    criteria = req.get("success_criteria", {})

    if not command:
        log_action("EMPTY_CMD", {"goal_id": goal_id})
        return

    print("\n[" + now() + "] NEW REQUEST | Goal: " + goal_id)
    print("  Command: " + command[:120])
    append_dossier("## REQUEST | Goal: " + goal_id + "\nCommand: `" + command[:200] + "`")

    # Execute
    result = execute_command(command)
    print("  Exit Code: " + str(result["exit_code"]))
    print("  Time: " + str(result["elapsed_sec"]) + "s")

    # Verify
    verdict, evidence = verify_evidence(result, criteria)
    print("  Verdict: " + verdict)

    # Count evidence passes
    ev_pass = sum(1 for v in evidence.values() if isinstance(v, dict) and v.get("pass"))
    ev_total = len([v for v in evidence.values() if isinstance(v, dict)])
    print("  Evidence: " + str(ev_pass) + "/" + str(ev_total) + " passed")

    # Write response
    response = {
        "status": "COMPLETED",
        "goal_id": goal_id,
        "exit_code": result["exit_code"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "evidence": evidence,
        "verdict": verdict,
        "elapsed_sec": result["elapsed_sec"],
        "timestamp": now()
    }
    write_json(RES, response)

    # Log
    log_action("RESULT", {
        "goal_id": goal_id,
        "verdict": verdict,
        "exit_code": result["exit_code"],
        "evidence": str(ev_pass) + "/" + str(ev_total)
    })

    append_dossier("## RESULT | Goal: " + goal_id + "\n**Verdict: " + verdict + "**\nExit: " + str(result["exit_code"]) + "\nEvidence: " + str(ev_pass) + "/" + str(ev_total))

    # Update progress
    progress = read_json(PROGRESS) or {}
    progress["current_goal"] = goal_id
    progress["iteration"] = progress.get("iteration", 0) + 1
    progress["last_action"] = verdict
    progress["timestamp"] = now()
    write_json(PROGRESS, progress)

def check_resume():
    """LAW83: Resume from crash"""
    hb = read_json(HEARTBEAT)
    if hb and hb.get("status") == "RUNNING":
        last = hb.get("last_beat", "")
        if last:
            try:
                from datetime import datetime as dt
                last_dt = dt.strptime(last, "%Y-%m-%d %H:%M:%S")
                diff = (dt.now() - last_dt).total_seconds()
                if diff < 120:
                    print("[RESUME] Heartbeat was " + str(int(diff)) + "s ago - possible crash detected!")
                    throttle = read_json(THROTTLE) or {}
                    level = throttle.get("current_level", 0) + 1
                    throttle["current_level"] = level
                    throttle["last_crash_timestamp"] = now()
                    throttle["crash_count_total"] = throttle.get("crash_count_total", 0) + 1
                    write_json(THROTTLE, throttle)
                    print("[THROTTLE] Increased to Level " + str(level))
                    append_dossier("## CRASH DETECTED\nThrottle increased to Level " + str(level))
                    log_action("CRASH_RESUME", {"throttle_level": level})
            except Exception:
                pass

    progress = read_json(PROGRESS)
    if progress and progress.get("current_goal"):
        print("[RESUME] Active goal: " + str(progress["current_goal"]))
        print("[RESUME] Iteration: " + str(progress.get("iteration", 0)))
        return True
    return False

def main():
    global running, last_req_hash

    print("=" * 60)
    print("  WSL ORCHESTRATOR v1.0")
    print("  " + now())
    print("  Bridge: " + REQ)
    print("=" * 60)

    if not os.path.exists(ORCH):
        print("[FATAL] Directory not found: " + ORCH)
        sys.exit(1)

    # Resume check
    check_resume()

    # Start heartbeat
    hb_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    hb_thread.start()
    print("[HB] Heartbeat started (" + str(HB_SEC) + "s)")

    log_action("START", {"pid": os.getpid()})
    append_dossier("# ORCHESTRATOR STARTED\nPID: " + str(os.getpid()))

    # Main bridge loop
    print("[BRIDGE] Watching for requests every " + str(POLL_SEC) + "s...")
    print("[BRIDGE] Waiting for Hermes...\n")

    try:
        while running:
            current_hash = hash_file(REQ)
            if current_hash and current_hash != last_req_hash:
                req = read_json(REQ)
                if req and req.get("status") == "NEW":
                    process_request(req)
                    req["status"] = "PROCESSED"
                    write_json(REQ, req)
                    last_req_hash = hash_file(REQ)
            time.sleep(POLL_SEC)
    except KeyboardInterrupt:
        print("\n[STOP] Shutting down...")
    finally:
        running = False
        log_action("STOP", {"timestamp": now()})
        append_dossier("## ORCHESTRATOR STOPPED\n" + now())
        write_json(HEARTBEAT, {"last_beat": now(), "orchestrator_pid": None, "status": "IDLE"})
        print("[STOP] Done.")

if __name__ == "__main__":
    main()
