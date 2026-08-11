#!/usr/bin/env python3
"""Run frozen selected-region directional motion preview twice."""
from __future__ import annotations
import hashlib, json, resource, subprocess, time
from pathlib import Path
import cv2
import numpy as np
import pandas as pd
import psutil

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/scan_innovation_agentic_loop_v1'; EXP=OUT/'preview_experiments/YGS-H003'
RATE,WIDTH,HEIGHT=5.0,320,180

def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1<<20): h.update(chunk)
    return h.hexdigest()

def canonical_hash(frame:pd.DataFrame)->str:
    x=frame.sort_values(['video_id','region_index']).copy(); nums=x.select_dtypes(include=[np.number]).columns
    x[nums]=x[nums].round(8); return hashlib.sha256(x.to_csv(index=False,float_format='%.8g').encode()).hexdigest()

def atomic_json(path:Path,value:object)->None:
    tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n'); tmp.replace(path)

def pair_features(previous:np.ndarray,current:np.ndarray)->dict[str,float]:
    flow=cv2.calcOpticalFlowFarneback(previous,current,None,0.5,3,15,3,5,1.2,0)
    rx=flow[...,0]-np.median(flow[...,0]); ry=flow[...,1]-np.median(flow[...,1])
    mag=np.sqrt(rx*rx+ry*ry); ax=np.abs(rx); ay=np.abs(ry)
    yy,xx=np.mgrid[0:HEIGHT,0:WIDTH]; nx=(xx-(WIDTH-1)/2)/WIDTH; ny=(yy-(HEIGHT-1)/2)/HEIGHT
    norm=np.sqrt(nx*nx+ny*ny)+1e-6; radial=(rx*nx+ry*ny)/norm
    divergence=cv2.Sobel(rx,cv2.CV_32F,1,0,ksize=3)+cv2.Sobel(ry,cv2.CV_32F,0,1,ksize=3)
    center=(xx>=.25*WIDTH)&(xx<=.75*WIDTH)&(yy>=.35*HEIGHT)
    lower=center&(yy>=.60*HEIGHT)
    diff=cv2.absdiff(previous,current).astype(np.float32)
    return {
        'residual_magnitude_mean':float(mag.mean()), 'residual_magnitude_q90':float(np.quantile(mag,.9)),
        'residual_magnitude_max':float(mag.max()), 'residual_active_ratio':float((mag>.5).mean()),
        'horizontal_abs_mean':float(ax.mean()), 'vertical_abs_mean':float(ay.mean()),
        'lateral_dominance':float(ax.mean()/(ay.mean()+1e-6)), 'signed_horizontal_mean':float(rx.mean()),
        'positive_divergence_mean':float(np.maximum(divergence,0).mean()),
        'positive_divergence_q90':float(np.quantile(np.maximum(divergence,0),.9)),
        'radial_expansion_mean':float(radial.mean()), 'positive_radial_expansion_mean':float(np.maximum(radial,0).mean()),
        'center_residual_magnitude':float(mag[center].mean()), 'lower_center_residual_magnitude':float(mag[lower].mean()),
        'frame_difference_mean':float(diff.mean()/255.0), 'frame_difference_q90':float(np.quantile(diff,.9)/255.0),
        'frame_difference_active_ratio':float((diff>20).mean()),
    }

def aggregate(samples:pd.DataFrame,region)->dict:
    row={'video_id':region.video_id,'region_id':region.region_id,'region_index':int(region.region_index),
         'start_sec':float(region.start_sec),'end_sec':float(region.end_sec),'actual_duration_sec':float(region.actual_duration_sec),
         'q3__selected':1.0,'q3__preview_pair_count':len(samples),'q3__preview_missingness_fraction':float(len(samples)==0)}
    for col in samples.columns:
        values=samples[col].to_numpy(float); prefix=f'q3__motion__{col}'
        if len(values):
            top=np.sort(values)[-min(3,len(values)):]; slope=float(np.polyfit(np.arange(len(values)),values,1)[0]) if len(values)>=2 else 0.0
            stats=[values.mean(),values.max(),values.std(),np.quantile(values,.9),top.mean(),slope]
        else: stats=[0.0]*6
        for name,val in zip(('mean','max','std','q90','top3mean','slope'),stats): row[f'{prefix}__{name}']=float(val)
    return row

def run_once(run_index:int)->dict:
    selection=pd.read_csv(EXP/'selected_regions.csv'); videos=pd.read_csv(ROOT/'benchmarks/partial_scan_pilot_v1/immutable/videos.csv').set_index('video_id')
    rows=[]; samples_out=[]; runtimes=[]
    for video_id,selected in selection.groupby('video_id',sort=True):
        start=time.perf_counter(); decode=flow_time=aggregate_time=0.0; pair_count=0; peak=psutil.Process().memory_info().rss
        for region in selected.sort_values('region_index').itertuples(index=False):
            command=['ffmpeg','-v','error','-ss',f'{region.start_sec:.6f}','-t',f'{region.actual_duration_sec:.6f}',
                     '-i',str(videos.loc[video_id].video_path),'-vf',f'fps={RATE:g},scale={WIDTH}:{HEIGHT}',
                     '-pix_fmt','gray','-f','rawvideo','-']
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE); assert process.stdout is not None
            previous=None; feature_rows=[]; local=0
            while True:
                read_start=time.perf_counter(); payload=process.stdout.read(WIDTH*HEIGHT); decode+=time.perf_counter()-read_start
                if not payload: break
                if len(payload)!=WIDTH*HEIGHT: process.kill(); raise RuntimeError(f'partial frame {len(payload)}')
                current=np.frombuffer(payload,np.uint8).reshape(HEIGHT,WIDTH).copy()
                if previous is not None:
                    calc=time.perf_counter(); values=pair_features(previous,current); flow_time+=time.perf_counter()-calc
                    feature_rows.append(values); samples_out.append({'video_id':video_id,'region_id':region.region_id,'pair_index':local,**values})
                    local+=1; pair_count+=1
                previous=current
            stderr=process.stderr.read().decode() if process.stderr is not None else ''
            if process.wait()!=0: raise RuntimeError(stderr)
            agg_start=time.perf_counter(); rows.append(aggregate(pd.DataFrame(feature_rows),region)); aggregate_time+=time.perf_counter()-agg_start
            peak=max(peak,psutil.Process().memory_info().rss)
        runtimes.append({'run_index':run_index,'video_id':video_id,'selected_region_count':len(selected),
                         'selected_duration_sec':float(selected.actual_duration_sec.sum()),'pair_count':pair_count,
                         'decode_time_sec':decode,'motion_feature_time_sec':flow_time,'aggregation_time_sec':aggregate_time,
                         'total_wallclock_sec':time.perf_counter()-start,'peak_cpu_memory_bytes':int(peak),
                         'process_lifetime_max_rss_kib':int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)})
    features=pd.DataFrame(rows).sort_values(['video_id','region_index']).reset_index(drop=True)
    samples=pd.DataFrame(samples_out).sort_values(['video_id','region_id','pair_index']).reset_index(drop=True)
    runtime=pd.DataFrame(runtimes)
    features.to_parquet(EXP/f'region_features_run{run_index}.parquet',index=False)
    samples.to_parquet(EXP/f'sample_features_run{run_index}.parquet',index=False)
    runtime.to_csv(EXP/f'runtime_run{run_index}.csv',index=False)
    manifest={'run_index':run_index,'region_count':len(features),'pair_count':len(samples),'canonical_feature_hash':canonical_hash(features),
              'feature_file_sha256':sha256(EXP/f'region_features_run{run_index}.parquet'),'sample_file_sha256':sha256(EXP/f'sample_features_run{run_index}.parquet'),
              'runtime_total_sec':float(runtime.total_wallclock_sec.sum()),'missing_cells':int(features.isna().sum().sum()),
              'input_contract':'FROZEN_SELECTION_CSV_AND_SOURCE_VIDEO_BYTES_ONLY'}
    atomic_json(EXP/f'run{run_index}_manifest.json',manifest); return manifest

def main()->None:
    manifests=[run_once(i) for i in (1,2)]; match=manifests[0]['canonical_feature_hash']==manifests[1]['canonical_feature_hash']
    result={'status':'PASS' if match else 'FAIL','deterministic_hash_match':match,'runs':manifests,
            'implementation_hash':sha256(Path(__file__)),'forbidden_inputs_used':[],'region_state_reset':True}
    atomic_json(EXP/'operator_manifest.json',result)
    if not match: raise AssertionError('H003 nondeterministic')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
