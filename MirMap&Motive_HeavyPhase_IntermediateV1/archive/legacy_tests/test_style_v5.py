import os, json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

BASE = r"D:\kiarash\kiarash git codes\MirMap&Motive_HeavyPhase_IntermediateV1"
ARCHIVE = os.path.join(BASE, "Visual_Archives")
os.makedirs(ARCHIVE, exist_ok=True)

# Publication style
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 11,
    "axes.linewidth": 1.0,
    "axes.edgecolor": "black",
    "figure.dpi": 100,
    "savefig.dpi": 300,
})
OKABE_BLUE = "#0072B2"
OKABE_ORANGE = "#E69F00"

with open(os.path.join(BASE, "models", "qwen3_vla_mir100_lora_v2", "training_history.json"), "r", encoding="utf-8") as f:
    hist = json.load(f)

epochs = [e["epoch"] for e in hist["epochs"]]
losses = [e["loss"] for e in hist["epochs"]]

fig, ax = plt.subplots(figsize=(6, 4))
ax.plot(epochs, losses, marker="o", color=OKABE_BLUE, linewidth=2, markersize=7, markerfacecolor="white", markeredgewidth=2)
ax.set_yscale("log")
ax.set_xlabel("Training Epoch")
ax.set_ylabel("Cross-Entropy Loss (log scale)")
ax.set_title("QLoRA Fine-tuning Convergence", fontsize=12, fontweight="bold")
ax.grid(True, which="both", linestyle=":", alpha=0.5)
ax.text(0.02, 0.98, "(a)", transform=ax.transAxes, fontsize=13, fontweight="bold", va="top")
for e, l in zip(epochs, losses):
    ax.annotate(f"{l:.3f}", (e, l), textcoords="offset points", xytext=(0, 10), ha="center", fontsize=8)

fig.text(0.5, -0.05,
    "Figure 1. Training loss trajectory of Qwen3-VL-2B under label-masked QLoRA fine-tuning\n"
    "(source: training_history.json, 6 epochs, real values).",
    ha="center", fontsize=9, style="italic", wrap=True)

out = os.path.join(ARCHIVE, "TEST_Figure1_LossCurve.png")
fig.savefig(out, bbox_inches="tight", dpi=300)
print("SAVED:", out)
print("Loss values used (REAL, from file):", losses)
