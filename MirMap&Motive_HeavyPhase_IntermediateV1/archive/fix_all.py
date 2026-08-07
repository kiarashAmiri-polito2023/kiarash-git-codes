# Python exact-replacement fixer
import py_compile, sys, os

launch_path = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1\agents\launch_session.py"
copilot_path = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1\agents\co_pilot_agent.py"

# --- Fix co_pilot_agent.py ---
with open(copilot_path, 'r', encoding='utf-8') as f:
    co = f.read()

if 'HAS_ENTITY = False for report generation' in co:
    co = co.replace('HAS_ENTITY = False for report generation', 'HAS_ENTITY = False\\n\\n# Try to import knowledge_engine for report generation')
    with open(copilot_path, 'w', encoding='utf-8') as f:
        f.write(co)
    print('[FIXED] co_pilot_agent.py: stray text removed')
else:
    print('[SKIP] co_pilot_agent.py: already clean or different')

# --- Fix launch_session.py ---
with open(launch_path, 'r', encoding='utf-8') as f:
    txt = f.read()

# Fix 1: Broken import block (roslibpy nested with mir_command_logger)
broken_import = '''        try:
            import roslibpy
try:
    from mir_command_logger import MirCommandLogger
    HAS_CMD_LOGGER = True
except ImportError:
    HAS_CMD_LOGGER = False
        except ImportError:'''

good_import = '''        try:
            import roslibpy
        except ImportError:'''
# Actually we need the correct import placement. Let's do a simpler approach:
# Replace the broken nested block with correct separate imports.

# More robust: find and replace the exact broken snippet
broken_snippet = '''        try:
            import roslibpy
try:
    from mir_command_logger import MirCommandLogger
    HAS_CMD_LOGGER = True
except ImportError:
    HAS_CMD_LOGGER = False
        except ImportError:'''

# We replace with clean roslibpy try, then add command logger import separately before class or at top
good_snippet = '''        try:
            import roslibpy
            HAS_ROSLIBPY = True
        except ImportError:
            HAS_ROSLIBPY = False
try:
    from mir_command_logger import MirCommandLogger
    HAS_CMD_LOGGER = True
except ImportError:
    HAS_CMD_LOGGER = False
        except ImportError:
            print("[SLAM] WARNING: roslibpy not installed.")
            return False'''

# Actually that might double the except. Let's inspect and replace carefully.
# Given previous snapshot, the broken part is inside try_connect. Let's replace just the broken lines inside that method.

# Fix 2: Broken print statements with literal newlines
txt = txt.replace('print("\\n[pipeline] Stage: Entity Registry rebuild...")', 
                  'print("\\n[pipeline] Stage: Entity Registry rebuild...")')  # This won't help if literal newline exists.
# Instead, replace the literal multiline print patterns:
txt = txt.replace('print("\\n\\n[pipeline] Stage: Entity Registry rebuild...")', 'print("\\n[pipeline] Stage: Entity Registry rebuild...")')

# Let's use exact multiline replacements based on snapshot:
txt = txt.replace('        print("\\n[pipeline] Stage: SLAM Auto-Naming...")', '        print("\\n[pipeline] Stage: SLAM Auto-Naming...")')
txt = txt.replace('        print("\\n[pipeline] Stage: CVAT Pre-Populator...")', '        print("\\n[pipeline] Stage: CVAT Pre-Populator...")')
txt = txt.replace('        print("\\n[pipeline] Stage: Robot Data Analyzer...")', '        print("\\n[pipeline] Stage: Robot Data Analyzer...")')

# Actually the snapshot shows broken literal newlines like:
#         print("
# [pipeline] Stage: ...")
# Let's replace those exact patterns if they exist.
txt = txt.replace('print("\\n\\n[pipeline]', 'print("\\n[pipeline]')

# Fix 3: Broken try/except indent and slam_logger placement
bad_block = '''    if slam_ok:
        if cmd_logger is not None:
        try:
            cmd_logger.stop()
            cmd_logger.save_final()
        except Exception as e:
            print(f"[launch_session] cmd save error: {e}")
    
    slam_logger.save_final()'''
good_block = '''    if slam_ok:
        if cmd_logger is not None:
            try:
                cmd_logger.stop()
                cmd_logger.save_final()
            except Exception as e:
                print(f"[launch_session] cmd save error: {e}")
        slam_logger.save_final()'''

if bad_block in txt:
    txt = txt.replace(bad_block, good_block)
    print('[FIXED] launch_session.py: try/except indent + slam_logger placement')
else:
    # Try flexible: maybe spaces differ slightly
    if 'if cmd_logger is not None:' in txt and 'slam_logger.save_final()' in txt:
        # Manual line-based fix: ensure correct indentation
        lines = txt.splitlines(True)
        new_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # Find the broken pattern and fix
            if line.strip() == 'if cmd_logger is not None:':
                # Check next line indent
                if i+1 < len(lines) and lines[i+1].strip() == 'try:':
                    # This means try is at same indent as if -> wrong
                    new_lines.append(line)
                    # Replace next try line with indented try
                    new_lines.append('            try:\\n')
                    i += 1  # skip old try
                    # Now indent cmd_logger lines
                    i += 1
                    while i < len(lines) and (lines[i].strip().startswith('cmd_logger.') or lines[i].strip().startswith('except')):
                        if lines[i].strip().startswith('cmd_logger.'):
                            new_lines.append('                ' + lines[i].lstrip())
                        elif lines[i].strip().startswith('except'):
                            new_lines.append('            ' + lines[i].lstrip())
                            # Next line is print, indent it
                            if i+1 < len(lines) and 'print(' in lines[i+1]:
                                new_lines.append('                ' + lines[i+1].lstrip())
                                i += 1
                        i += 1
                    # Continue without adding old broken lines
                    continue
            new_lines.append(line)
            i += 1
        txt = ''.join(new_lines)
        print('[FIXED FLEXIBLE] launch_session.py: indent corrected manually')
    else:
        print('[SKIP/FLEX] launch_session.py: block not found, may be already fixed')

# Fix 4: Import block fix for roslibpy / mir_command_logger
# Based on snapshot, the broken nested import needs to be separated.
# Let's do a targeted replacement of the broken nested snippet.
broken_import_exact = '''    def try_connect(self):
        try:
            import roslibpy
try:
    from mir_command_logger import MirCommandLogger
    HAS_CMD_LOGGER = True
except ImportError:
    HAS_CMD_LOGGER = False
        except ImportError:
            print("[SLAM] WARNING: roslibpy not installed.")
            return False'''

good_import_exact = '''    def try_connect(self):
        try:
            import roslibpy
        except ImportError:
            print("[SLAM] WARNING: roslibpy not installed.")
            return False
try:
    from mir_command_logger import MirCommandLogger
    HAS_CMD_LOGGER = True
except ImportError:
    HAS_CMD_LOGGER = False'''

# Note: The import of mir_command_logger should probably be at module level, but this fixes syntax.
if broken_import_exact in txt:
    txt = txt.replace(broken_import_exact, good_import_exact)
    print('[FIXED] launch_session.py: import block syntax')
else:
    # Try to find and separate if close
    if 'import roslibpy' in txt and 'mir_command_logger' in txt:
        print('[INFO] launch_session.py: imports present but format differs; manual check recommended')
    else:
        print('[SKIP] launch_session.py: import block pattern not matched')

with open(launch_path, 'w', encoding='utf-8') as f:
    f.write(txt)

# --- Validate ---
for path in [launch_path, copilot_path]:
    try:
        py_compile.compile(path, doraise=True)
        print(f'[VALID] {os.path.basename(path)} syntax OK')
    except Exception as e:
        print(f'[FAIL] {os.path.basename(path)} syntax error: {e}')
