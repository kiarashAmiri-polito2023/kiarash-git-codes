import os,sys,json,time,urllib.request,urllib.error
from datetime import datetime

ROOT = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
print("="*60)
print("R41.1 GITHUB SOTA REAL SCAN")
print("Reading actual repos from GitHub API")
print("="*60)

# Load token if exists
token = ""
tkp = os.path.join(ROOT, ".secrets", "github.key")
if os.path.exists(tkp):
    with open(tkp, "r", encoding="utf-8-sig") as f:
        token = f.read().strip()
    print("GitHub token: loaded")
else:
    print("GitHub token: NONE (rate limit 60/hr)")

# 20 real SOTA repos relevant to MiR100 VLA Navigation Safety
REPOS = [
    "google-deepmind/rt-x",
    "octo-models/octo",
    "OpenVLA/openvla",
    "Physical-Intelligence/pi0",
    "lerobot/lerobot",
    "ros-planning/navigation2",
    "cartographer-project/cartographer",
    "facebookresearch/habitat-lab",
    "NVIDIA/IsaacGymEnvs",
    "ARISE-Initiative/robosuite",
    "google-deepmind/mujoco",
    "ros2/ros2",
    "SteveMacenski/slam_toolbox",
    "MIT-SPARK/Kimera-VIO",
    "ethz-asl/rovioli",
    "facebookresearch/detr",
    "ultralytics/ultralytics",
    "nvidia-isaac-ros/isaac_ros_visual_slam",
    "robotics-united/robot-safety",
    "huggingface/transformers",
]

def gh_api(url):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "MiR100-Audit")
    if token:
        req.add_header("Authorization", "token " + token)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)[:80]}

results = []
dims_extracted = set()

for i, repo in enumerate(REPOS):
    print("\n[{}/20] {} ...".format(i+1, repo))
    time.sleep(1)
    
    # 1: Repo info
    info = gh_api("https://api.github.com/repos/" + repo)
    if "error" in info:
        print("  SKIP: " + info["error"])
        results.append({"repo": repo, "ok": False, "err": info["error"]})
        continue
    
    stars = info.get("stargazers_count", 0)
    lang = info.get("language", "unknown")
    topics = info.get("topics", [])
    desc = info.get("description", "")[:80]
    updated = info.get("updated_at", "")[:10]
    
    # 2: File tree (root level)
    tree = gh_api("https://api.github.com/repos/" + repo + "/git/trees/HEAD?recursive=0")
    root_files = []
    has_dirs = {}
    if "tree" in tree:
        for item in tree["tree"]:
            root_files.append(item["path"])
            if item["type"] == "tree":
                has_dirs[item["path"]] = True
    
    # 3: Extract dimensions from structure
    dims = []
    checks = {
        "has_docker": "Dockerfile" in root_files or "docker" in str(root_files).lower(),
        "has_ci": any(".github" in f or ".gitlab-ci" in f or ".travis" in f for f in root_files),
        "has_tests": "test" in has_dirs or "tests" in has_dirs,
        "has_docs": "docs" in has_dirs or "doc" in has_dirs,
        "has_config": any(f.endswith(".yaml") or f.endswith(".yml") or f.endswith(".toml") for f in root_files),
        "has_requirements": any("requirements" in f or "setup.py" in f or "pyproject" in f for f in root_files),
        "has_license": "LICENSE" in root_files or "LICENCE" in root_files,
        "has_readme": "README.md" in root_files or "README.rst" in root_files,
        "has_models": "models" in has_dirs or "checkpoints" in has_dirs or "weights" in has_dirs,
        "has_dataset": "data" in has_dirs or "dataset" in has_dirs,
        "has_training": "train" in has_dirs or "training" in has_dirs or "scripts" in has_dirs,
        "has_eval": "eval" in has_dirs or "evaluation" in has_dirs or "benchmark" in has_dirs,
        "has_ros": "launch" in has_dirs or "urdf" in has_dirs or "msg" in has_dirs,
        "has_safety": "safety" in str(root_files).lower() or "safe" in str(root_files).lower(),
        "has_vla": "vla" in desc.lower() or "vision" in desc.lower() or "language" in desc.lower(),
        "has_navigation": "nav" in desc.lower() or "slam" in desc.lower() or "path" in desc.lower(),
        "has_sim": "sim" in has_dirs or "gym" in has_dirs or "env" in has_dirs,
        "has_pretrained": "pretrained" in str(root_files).lower() or "checkpoint" in str(root_files).lower(),
        "has_config_yaml": any(f.endswith(".yaml") for f in root_files),
        "has_python": lang == "Python",
    }
    
    for k, v in checks.items():
        if v:
            dims.append(k)
            dims_extracted.add(k)
    
    r = {
        "repo": repo,
        "ok": True,
        "stars": stars,
        "lang": lang,
        "topics": topics[:5],
        "desc": desc,
        "updated": updated,
        "root_files": len(root_files),
        "dims": dims,
        "dim_count": len(dims),
    }
    results.append(r)
    print("  stars={} lang={} dims={}/20 files={}".format(stars, lang, len(dims), len(root_files)))

# Summary
print("\n" + "="*60)
print("SCAN SUMMARY")
print("="*60)
ok_count = sum(1 for r in results if r.get("ok"))
print("Repos scanned: {}/20".format(ok_count))
print("Unique dimensions extracted: {}".format(len(dims_extracted)))
print("Dimensions: " + str(sorted(dims_extracted)))

# Save
rp = os.path.join(ROOT, "R41_1_github_sota_scan.json")
with open(rp, "w", encoding="utf-8") as f:
    json.dump({"repos": results, "dims": sorted(dims_extracted), "ts": datetime.now().isoformat()}, f, indent=2)
print("\nSAVED: " + rp)
