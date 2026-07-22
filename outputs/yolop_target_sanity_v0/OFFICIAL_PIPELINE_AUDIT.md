# YOLOP Official Pipeline Audit

## Source Files Audited

| File | Purpose |
|------|---------|
| `lib/dataset/DemoDataset.py` | `LoadImages` class — video/image loading and letterbox |
| `lib/utils/augmentations.py` | `letterbox_for_img()` — scale-preserving resize with padding |
| `lib/models/YOLOP.py` | `MCnet` architecture, `get_net()` factory, YOLOP config |
| `lib/models/common.py` | `Detect` head with anchor-based decoding |
| `lib/models/common2.py` | Alternative `Detect` head (nn.Hardswish version) |
| `lib/core/general.py` | `non_max_suppression()`, `scale_coords()`, `xywh2xyxy()` |
| `lib/core/postprocess.py` | `morphological_process()`, `connect_lane()`, `fitlane()` |
| `lib/core/function.py` | Validation pipeline (end-to-end postprocessing reference) |
| `lib/utils/plot.py` | `show_seg_result()`, `plot_one_box()` |
| `tools/demo.py` | Main inference CLI |
| `export_onnx.py` | ONNX export with standalone MCnet |
| `test_onnx.py` | ONNX inference test |
| `hubconf.py` | Torch Hub entry point |
| `lib/config/default.py` | Training/evaluation config defaults |

---

## 1. Image Preprocessing

### Resize Method: LETTERBOX (Scale-Preserving Pad)

**File**: `lib/utils/augmentations.py:214-248`

```
r = min(new_h / old_h, new_w / old_w)    # smaller dimension ratio
new_unpad = (round(old_w * r), round(old_h * r))
dw, dh = new_shape - new_unpad           # padding
dw, dh = np.mod(dw, 32), np.mod(dh, 32)  # round to stride multiple
img = cv2.resize(img, new_unpad, cv2.INTER_AREA)
img = cv2.copyMakeBorder(img, top=dh/2, bottom=dh/2, left=dw/2, right=dw/2,
                         borderType=cv2.BORDER_CONSTANT, value=(114,114,114))
```

- **Pad color**: (114, 114, 114) — gray
- **Interpolation**: `cv2.INTER_AREA`
- **Stride alignment**: padding rounded to multiples of 32

### Normalization

**File**: `tools/demo.py:31-38`

```
normalize = transforms.Normalize(
    mean=[0.485, 0.456, 0.406],
    std=[0.229, 0.224, 0.225]
)
transform = transforms.Compose([transforms.ToTensor(), normalize])
```

**Critical finding**: The input is BGR (from `cv2.imread`), but ImageNet RGB mean/std is applied without BGR->RGB conversion. This means the blue channel is normalized with the R-channel mean and vice versa. The model was trained this way and expects BGR input with these normalization parameters.

### PyTorch vs ONNX channel handling

| Aspect | PyTorch (`demo.py`) | ONNX (`test_onnx.py`) |
|--------|---------------------|----------------------|
| Input format | BGR (cv2.imread) | BGR -> RGB (explicit conversion) |
| Normalization | ImageNet RGB means on BGR | ImageNet RGB means on RGB |
| Channel order to model | BGR (mismatched with mean labels) | RGB (matched with mean labels) |

Both paths work because the model was trained with the BGR-based pipeline. For this sanity audit, we use the ONNX path which explicitly converts BGR->RGB and applies matching normalization.

---

## 2. Model Architecture

**Architecture name**: `MCnet`  
**Config name**: `YOLOP`  

Three-head shared-encoder design:
- **Backbone**: Focus + 4× Conv+BottleneckCSP downsampling → SPP → PANet
- **Detection head**: PANet → 3-scale Detect (stride 8/16/32)
- **Drivable area seg head**: 4× upsample → Conv → 2-channel output (bg, drivable)
- **Lane line seg head**: 4× upsample → Conv → 2-channel output (bg, lane)

### Detect Head Anchors

| Scale | Stride | Feature Map | Anchors (w,h) |
|-------|--------|-------------|---------------|
| Small | 8 | 80×80 | [3,9], [5,11], [4,20] |
| Medium | 16 | 40×40 | [7,18], [6,39], [12,31] |
| Large | 32 | 20×20 | [19,50], [38,81], [68,157] |

**nc = 1** (one class: vehicle)

### Number of detections per scale

| Input size | Scale 0 (stride 8) | Scale 1 (stride 16) | Scale 2 (stride 32) | Total |
|------------|---------------------|---------------------|---------------------|-------|
| 320×320 | 3 × 40×40 = 4800 | 3 × 20×20 = 1200 | 3 × 10×10 = 300 | 6300 |
| 640×640 | 3 × 80×80 = 19200 | 3 × 40×40 = 4800 | 3 × 20×20 = 1200 | 25200 |
| 1280×1280 | 3 × 160×160 = 76800 | 3 × 80×80 = 19200 | 3 × 40×40 = 4800 | 100800 |

---

## 3. Detection Decoding

**File**: `lib/models/common.py:188-217`

Raw output per prediction: `[tx, ty, tw, th, obj, cls]` (6 values)

Decoding formulas:
```
cx = (sigmoid(tx) * 2 - 0.5 + grid_x) * stride
cy = (sigmoid(ty) * 2 - 0.5 + grid_y) * stride
w  = (sigmoid(tw) * 2)^2 * anchor_w
h  = (sigmoid(th) * 2)^2 * anchor_h
```

- Center offset range: [-0.5, 1.5] grid cells
- Size range: [0, 4] × anchor size
- **No sigmoid applied to raw det_out in ONNX** — sigmoid is applied inside the Detect head's forward during inference mode

**ONNX output format**: `det_out: (1, N, 6)` with columns `(cx, cy, w, h, obj_conf, cls_conf)`, all in model-input-space coordinates (0 to input_size).

---

## 4. NMS

**File**: `lib/core/general.py:98-185`

```
non_max_suppression(prediction, conf_thres=0.25, iou_thres=0.45)
```

Algorithm:
1. Filter by `obj_conf > conf_thres`
2. Final confidence = `obj_conf * cls_conf`
3. Convert cx,cy,w,h → x1,y1,x2,y2 (top-left, bottom-right corners)
4. Class-aware NMS: add `class_id * max_wh` offset to suppress only same-class boxes
5. `torchvision.ops.nms()` with `iou_thres`
6. Cap at 300 detections per image

**Default thresholds**: `conf_thres=0.25`, `iou_thres=0.45` (from demo.py)

---

## 5. Coordinate Restoration (scale_coords)

**File**: `lib/core/general.py:209-222`

```python
coords[:, [0,2]] -= pad[0]   # remove x padding from letterbox
coords[:, [1,3]] -= pad[1]   # remove y padding
coords[:, :4] /= gain         # divide by scale ratio
clip_coords(coords, img0_shape)
```

Where `gain = r` (scale ratio from letterbox) and `pad = (dw, dh)` (half-paddings).

---

## 6. Segmentation Postprocessing

### Drivable Area & Lane Line

In `tools/demo.py:117-130`:

```python
# Crop letterbox padding from seg output
da_predict = da_seg_out[:, :, pad_h:(H-pad_h), pad_w:(W-pad_w)]

# Resize to original image size (bilinear interpolation)
da_seg_mask = F.interpolate(da_predict, scale_factor=1/r, mode='bilinear')

# Argmax over 2 channels (0=bg, 1=foreground)
_, da_seg_mask = torch.max(da_seg_mask, 1)
```

- Crop padding → bilinear resize to original → argmax
- Same procedure for both drivable area and lane line
- **No morphological postprocessing** applied in demo (exists in `postprocess.py` but commented out)

---

## 7. Lane Quadratic Fitting (Available but Disabled in Demo)

**File**: `lib/core/postprocess.py:195-217`

`connect_lane()`:
1. `cv2.connectedComponentsWithStats` (8-connectivity)
2. Filter components with area > 400 pixels
3. `fitlane()` per component group

`fitlane()`:
1. Sample 30 equally-spaced y-coordinates through component bbox
2. For each y, find mean x of component pixels at that row
3. Fit 2nd-degree polynomial y→x via `np.polyfit`
4. Draw with `cv2.polylines`, thickness=15
5. Fallback: if component is more horizontal than vertical, fit x→y instead

---

## 8. Expected Output Semantics Summary

| Output Tensor | Shape | Semantics |
|---------------|-------|-----------|
| `det_out` | `(1, N, 6)` | Raw detection: `[cx, cy, w, h, obj_conf, cls_conf]` in input-space coords |
| `drive_area_seg` | `(1, 2, H, W)` | Per-pixel probabilities: channel 0 = bg, channel 1 = drivable area (sigmoid-applied) |
| `lane_line_seg` | `(1, 2, H, W)` | Per-pixel probabilities: channel 0 = bg, channel 1 = lane line (sigmoid-applied) |

---

## 9. Config Defaults

| Parameter | Value |
|-----------|-------|
| Image size (train/inference) | [640, 640] |
| Num seg classes | 2 |
| RGB color | False (BGR) |
| NMS conf threshold (demo) | 0.25 |
| NMS IoU threshold (demo) | 0.45 |
| NMS conf threshold (val) | 0.001 |
| NMS IoU threshold (val) | 0.6 |
| DA seg loss weight | 0.2 |
| LL seg loss weight | 0.2 |

---

## 10. Key Implementation Notes for Sanity Runner

1. **Preprocessing must match**: BGR→RGB, letterbox, normalize with [0.485,0.456,0.406] / [0.229,0.224,0.225]
2. **Detection decoding**: cx,cy,w,h are in model-input coordinates (not original image)
3. **Coordinate restoration**: subtract padding, divide by scale ratio
4. **Segmentation**: Sigmoid is already applied in model forward → values in [0,1] per channel
5. **Seg restoration**: crop padding, bilinear resize to original, argmax
6. **ONNX det_out**: raw values (cx,cy,w,h,obj_cls) — decode using anchor/grid logic matching Detect head
7. **Channel order for visualization**: model input is RGB, overlay drawing uses BGR (OpenCV)
