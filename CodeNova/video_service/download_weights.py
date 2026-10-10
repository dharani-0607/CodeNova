"""Download public pretrained weights for the extra detectors.

Usage (from the video_service folder, with its virtualenv active):
    python download_weights.py

- yolov8n.pt and yolov8n-pose.pt (COCO, by Ultralytics) download automatically
  the first time the service runs; this script fetches them up front too.
- Fire/smoke and smoking weights are community models on Hugging Face. They were
  chosen from public listings and have NOT been validated on Amrita cameras. Check
  each model card's licence and test them on your own footage before relying on them.
  You can swap in any YOLOv8/11 .pt file: put it at weights/fire_smoke.pt or
  weights/smoking.pt (class names must contain "fire"/"smoke" or "cig"/"smok").
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEIGHTS = HERE / "weights"

# (target file, [(hugging face repo, filename), ...] tried in order)
CANDIDATES = {
    "fire_smoke.pt": [
        ("Priyanshu-68/yolov8-cctv-tracking-models", "fire_detector_best.pt"),
        ("raidavid/yolov8_fire_and_smoke", "weights/best.pt"),
    ],
    "smoking.pt": [
        ("basant18/Smoking-detection-YOLO26s", "weights/best.pt"),
        ("Beehzod/smoking-detection-finetuned", "best.pt"),
    ],
}


def fetch_hf(target: str) -> bool:
    from huggingface_hub import hf_hub_download

    for repo, filename in CANDIDATES[target]:
        try:
            path = hf_hub_download(repo_id=repo, filename=filename)
        except Exception as exc:  # noqa: BLE001
            print(f"  - {repo}/{filename}: not available ({type(exc).__name__})")
            continue
        dest = WEIGHTS / target
        shutil.copy(path, dest)
        if check(dest):
            print(f"  ✓ {target} <- {repo}/{filename}")
            return True
        dest.unlink(missing_ok=True)
    return False


def check(path: Path) -> bool:
    try:
        from ultralytics import YOLO

        names = YOLO(str(path)).names
        print(f"    classes: {names}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"    could not load with ultralytics: {exc}")
        return False


def main() -> int:
    WEIGHTS.mkdir(exist_ok=True)
    print("Base models (COCO detection + pose):")
    from ultralytics import YOLO

    for name in ("yolov8n.pt", "yolov8n-pose.pt"):
        YOLO(name)  # downloads into the current folder if missing
        print(f"  ✓ {name}")
    ok = True
    for target in CANDIDATES:
        print(f"{target}:")
        if (WEIGHTS / target).exists():
            print("  already present, skipping")
            continue
        if not fetch_hf(target):
            ok = False
            print(f"  ✗ no candidate worked. Detector stays off until you place a model at weights/{target}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
