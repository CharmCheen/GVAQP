# Server Environment Setup for Real Frame-Level Experiments

## 1. Python Environment

```bash
# Create environment
conda create -n supg python=3.10 -y
conda activate supg

# Core dependencies
pip install numpy pandas scipy matplotlib pyarrow tqdm pyyaml

# PyTorch (match server CUDA version)
# Example for CUDA 12.1:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# YOLO and OpenCV
pip install ultralytics opencv-python

# Install SUPG in editable mode
pip install -e refe_repos/supg
```

## 2. Model Placement

Set environment variables:

```bash
export GARC_HOME=/path/to/project
export GARC_MODEL_DIR=${GARC_HOME}/models
export GARC_DATA_DIR=${GARC_HOME}/data
export GARC_OUTPUT_DIR=${GARC_HOME}/garc_eval/outputs
```

Place models:

```
$GARC_MODEL_DIR/yolo/yolov8n.pt    # proxy model (fast, small)
$GARC_MODEL_DIR/yolo/yolov8x.pt    # oracle model (slow, large)
```

YOLO models are auto-downloaded by ultralytics on first use,
or you can pre-download them:

```python
from ultralytics import YOLO
model = YOLO("yolov8n.pt")  # downloads to current dir
# Move to $GARC_MODEL_DIR/yolo/
```

## 3. Data Placement

```
$GARC_DATA_DIR/videos/sample.mp4    # source video
$GARC_DATA_DIR/frames/sample/       # extracted frames (auto-created)
$GARC_OUTPUT_DIR/real_frames/       # output directory (auto-created)
```

## 4. GT Labels (Optional)

If using ground-truth labels instead of a large oracle model,
prepare a CSV with columns `id,label`:

```csv
id,label
0,1
1,0
2,1
...
```

## 5. Recommended First-Run Configuration

| Component | Model | Notes |
|-----------|-------|-------|
| Proxy | YOLOv8n | Fast, ~6MB, good for screening |
| Oracle | YOLOv8x | Larger, more accurate |
| Oracle (alt) | GT labels | If available, avoids running oracle model |

Mask R-CNN can be added as a future oracle extension.
