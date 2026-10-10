# Model weights

| File | Used for | Source |
|------|----------|--------|
| `yolov8n.pt` | People, vehicles, animals, bags, bottles + tracking | Ultralytics COCO, downloaded automatically |
| `yolov8n-pose.pt` | Falls and fights (body keypoints) | Ultralytics COCO-pose, downloaded automatically |
| `weights/fire_smoke.pt` | Fire / smoke | Community model from Hugging Face (`python download_weights.py`) |
| `weights/smoking.pt` | Smoking (cigarettes) | Community model from Hugging Face (`python download_weights.py`) |

If a fire or smoking file is missing, that detector simply stays off. Nothing else is affected.

You can replace any file with your own YOLOv8/YOLO11 model, for example one fine-tuned on
footage from campus cameras, which will be far more accurate than public weights.
Class names must contain `fire`/`smoke`/`flame` (fire model) or `cig`/`smok`/`vape` (smoking model).

Licences: Ultralytics models are AGPL-3.0. Check each Hugging Face model card before use.
