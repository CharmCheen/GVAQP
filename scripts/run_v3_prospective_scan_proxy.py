#!/usr/bin/env python3
"""Execute a frozen prospective unit-level YOLO scan without semantic inputs."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def sha(p: Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser(); p.add_argument('--protocol',required=True); p.add_argument('--video',required=True); p.add_argument('--output-root',required=True); p.add_argument('--check',action='store_true'); a=p.parse_args()
    protocol=json.loads(Path(a.protocol).read_text())
    if not protocol.get('PROTOCOL_FROZEN') or protocol.get('DOWNSTREAM_RESULTS_OBSERVED'):
        raise RuntimeError('prospective protocol integrity failure')
    model=ROOT/protocol['model']['weight_path']
    if not model.is_file(): raise RuntimeError(f'bound YOLO weight missing: {model}')
    if sha(model)!=protocol['model']['weight_sha256']: raise RuntimeError('bound YOLO weight hash mismatch')
    try:
        import cv2
        from ultralytics import YOLO
    except Exception as e: raise RuntimeError(f'bound scan runtime unavailable: {type(e).__name__}: {e}') from e
    if a.check:
        print(json.dumps({'status':'PREFLIGHT_PASS','weight_sha256':sha(model),'cv2':cv2.__version__,'video':a.video},sort_keys=True)); return
    units=json.loads((ROOT/protocol['unit_manifest_path']).read_text())['units']
    vids={x['video_id']:x for x in json.loads((ROOT/protocol['video_manifest_path']).read_text())['videos']}
    if a.video not in vids: raise ValueError('unknown frozen video')
    rows=[x for x in units if x['video_id']==a.video]; cap=cv2.VideoCapture(str(ROOT/vids[a.video]['path']))
    if not cap.isOpened(): raise RuntimeError('cannot open frozen source video')
    net=YOLO(str(model)); cfg=protocol['model']; out=Path(a.output_root)/a.video; out.mkdir(parents=True,exist_ok=True)
    raw=out/'raw_unit_detections.jsonl'
    with raw.open('w') as f:
      for u in rows:
        target=float(u['start_time'])+float(u['duration_seconds'])/2.0
        cap.set(cv2.CAP_PROP_POS_MSEC,target*1000.0); ok,frame=cap.read()
        if not ok: raise RuntimeError(f'missing deterministic midpoint frame: {u["unit_id"]}')
        actual=float(cap.get(cv2.CAP_PROP_POS_MSEC))/1000.0
        pred=net(frame,imgsz=cfg['input_resolution'],conf=cfg['confidence_threshold'],iou=cfg['nms_iou'],max_det=cfg['max_detections'],device=cfg['device'],verbose=False)[0]
        boxes=[] if pred.boxes is None else pred.boxes
        keep=[]
        for cl,co in zip(boxes.cls.cpu().tolist(),boxes.conf.cpu().tolist()):
          if int(cl) in cfg['class_filter']: keep.append(float(co))
        payload={'video_id':a.video,'unit_id':u['unit_id'],'start_sec':u['start_time'],'end_sec':u['end_time'],'sample_target_sec':target,'sample_decoded_sec':actual,'det_count':len(keep),'max_conf':max(keep,default=0.0),'conf_sum':sum(keep)}
        f.write(json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n')
    cap.release(); print(json.dumps({'status':'RAW_SCAN_COMPLETE','video':a.video,'raw_path':str(raw),'rows':len(rows)},sort_keys=True))
if __name__=='__main__': main()
