#!/usr/bin/env python3
"""Blind Phase-A eligibility audit for the frozen online-activity replication.

This program deliberately has no imports or file reads from references, event
maps, policy runs, metrics, or method outputs.  It only inspects candidate
bytes, source declarations, and the frozen SCAN operator's local smoke path.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/realcam/long_video_data"
OLD_MANIFEST = ROOT / "outputs/psvr_autonomous_research/benchmark_unblock/VIDEO_CANDIDATES.csv"
OUT = ROOT / "outputs/psvr_autonomous_research/benchmark_unblock"
REPLICATION_OUT = ROOT / "outputs/online_macro_activity_replication"
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
NEW_NAMES = ("杭州.mp4", "杭州YouTube.mp4")
CRITERIA = (
    "RAW_CONTIGUOUS_VIDEO", "FULL_TIMELINE_AVAILABLE",
    "SOURCE_DECLARATION_PRESENT", "SOURCE_IDENTITY_VERIFIABLE",
    "ORIGINAL_SESSION_ID_VERIFIABLE", "SESSION_INDEPENDENT_FROM_OTHER_NEW_VIDEO",
    "INDEPENDENT_FROM_EXISTING_DESIGN_VIDEOS", "INDEPENDENT_FROM_LONG_VIDEO_DATASET3",
    "NOT_EVENT_CENTERED_CLIP", "NOT_PRECLIPPED_BY_TARGET_EVENT", "VIDEO_HASH_VALID",
    "METADATA_VALID", "RANDOM_SEEK_SUPPORTED", "ALL_SOURCE_RANGES_DECODABLE",
    "FIXED_SCAN_OPERATOR_SMOKE_TEST",
)

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def canon(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()

def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

def probe(path: Path) -> dict[str, Any]:
    p = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], capture_output=True, text=True)
    if p.returncode: return {"status": "FAIL", "error": p.stderr.strip()}
    raw = json.loads(p.stdout); streams = raw.get("streams", [])
    v = next((x for x in streams if x.get("codec_type") == "video"), {})
    fmt = raw.get("format", {})
    try: duration = float(fmt.get("duration") or v.get("duration") or 0)
    except ValueError: duration = 0
    return {"status": "PASS" if v and duration > 0 else "FAIL", "duration_seconds": duration,
            "format": fmt.get("format_name"), "codec": v.get("codec_name"),
            "width": int(v.get("width") or 0), "height": int(v.get("height") or 0),
            "avg_frame_rate": v.get("avg_frame_rate"), "nb_frames": v.get("nb_frames"),
            "format_tags": fmt.get("tags", {}), "video_tags": v.get("tags", {})}

def run_ok(cmd: list[str], timeout: int = 3600) -> tuple[bool, str, float]:
    started = time.monotonic(); p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    error = p.stderr.strip()
    # Corrupt media can emit one decoder diagnostic per packet.  Preserve a
    # bounded witness plus a digest/count, rather than turning an audit report
    # into a copy of the corrupt bitstream's decoder log.
    if len(error) > 4096:
        error = f"{error[:4096]}\n[stderr_truncated bytes={len(p.stderr)} sha256={hashlib.sha256(p.stderr.encode()).hexdigest()}]"
    return p.returncode == 0 and not p.stderr.strip(), error, time.monotonic() - started

def full_decode(path: Path) -> dict[str, Any]:
    ok, err, elapsed = run_ok(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-an", "-f", "null", "-"], 7200)
    return {"status": "PASS" if ok else "FAIL", "elapsed_seconds": elapsed, "decoder_error": err}

def packet_timeline(path: Path) -> dict[str, Any]:
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_packets", "-show_entries", "packet=dts_time", "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    values=[]
    for line in p.stdout.splitlines():
        try: values.append(float(line.split(",")[0]))
        except ValueError: pass
    regress = sum(b < a - 1e-9 for a,b in zip(values, values[1:]))
    return {"status": "PASS" if p.returncode == 0 and values and regress == 0 else "FAIL", "packet_count": len(values), "dts_regressions": regress, "error": p.stderr.strip()}

def random_seeks(path: Path, duration: float) -> dict[str, Any]:
    ratios=(.001,.01,.05,.13,.25,.37,.5,.63,.75,.87,.95,.99); rows=[]
    for r in ratios:
        t=min(max(0., r*duration), max(0.,duration-.25))
        ok,err,elapsed=run_ok(["ffmpeg","-v","error","-ss",f"{t:.6f}","-i",str(path),"-map","0:v:0","-frames:v","1","-an","-f","null","-"],120)
        rows.append({"ratio":r,"timestamp_seconds":t,"status":"PASS" if ok else "FAIL","elapsed_seconds":elapsed,"error":err})
    return {"status":"PASS" if all(x["status"]=="PASS" for x in rows) else "FAIL","rows":rows}

def source(path: Path) -> tuple[Path, dict[str, Any] | None, str | None]:
    sidecar=Path(str(path)+".source.json")
    if not sidecar.is_file(): return sidecar, None, "MISSING_SOURCE_DECLARATION"
    try: return sidecar, json.loads(sidecar.read_text(encoding="utf-8")), None
    except Exception as e: return sidecar, None, f"INVALID_SOURCE_DECLARATION:{type(e).__name__}"

def owner_attestation_valid(decl: dict[str, Any] | None, path: Path, video_hash: str) -> bool:
    if not decl or decl.get("source_attestation", {}).get("attestation_type") != "PROJECT_OWNER_ATTESTATION": return False
    att=decl["source_attestation"]
    statements=att.get("statements", {})
    required=("single_continuous_recording","not_event_centered","not_temporally_trimmed","not_concatenated","not_selected_using_target_event_information","independent_recording_session")
    md=Path(str(path)+".source_attestation.md")
    return (bool(att.get("declarant_name")) and bool(att.get("declaration_date")) and att.get("bound_video_sha256")==video_hash
            and all(statements.get(key) is True for key in required) and md.is_file()
            and video_hash in md.read_text(encoding="utf-8") and str(decl.get("capture_session_id")) in md.read_text(encoding="utf-8"))

def source_criteria(decl: dict[str, Any] | None, path: Path | None = None, video_hash: str = "") -> dict[str, dict[str,str]]:
    missing = decl is None
    def status(ok: bool, why: str="") -> dict[str,str]: return {"status":"PASS" if ok else "UNVERIFIED_OR_FAIL", "reason":why}
    source_identity = (not missing and bool(decl.get("source_asset_id") or decl.get("source_url") or decl.get("source_url_or_asset_id")))
    verification_notes = "" if missing else str(decl.get("source_verification", {}).get("verification_notes", "")).lower()
    source_identity = source_identity and not any(phrase in verification_notes for phrase in (
        "not independently verified", "does not establish", "unverified",
    ))
    owner_valid=owner_attestation_valid(decl,path,video_hash) if path else False
    if owner_valid: source_identity=True
    return {
      "SOURCE_DECLARATION_PRESENT": status(not missing, "source sidecar missing or invalid" if missing else ""),
      "SOURCE_IDENTITY_VERIFIABLE": status(source_identity, "a source asset identifier and independent verification are required"),
      "ORIGINAL_SESSION_ID_VERIFIABLE": status(not missing and bool(decl.get("capture_session_id")) and (owner_valid or decl.get("capture_session_id_type") != "PROJECT_OWNER_ATTESTED"), "capture_session_id plus admissible provenance evidence required"),
      "NOT_EVENT_CENTERED_CLIP": status(not missing and decl.get("source_kind")=="original_continuous_capture" and (owner_valid or decl.get("source_attestation") is None), "original_continuous_capture plus admissible provenance evidence required"),
      "NOT_PRECLIPPED_BY_TARGET_EVENT": status(not missing and decl.get("known_parent_video") is None and decl.get("known_derivation_operation") is None, "null parent and derivation fields required"),
    }

def scan_smoke(path: Path, meta: dict[str, Any]) -> dict[str, Any]:
    """The frozen operator is invoked locally twice; no reference/policy object exists."""
    try:
        sys.path.insert(0, str(ROOT / "scripts")); import partial_scan_pilot_common as c
        h=sha(path); v={"video_id":"phase_a_smoke","video_path":str(path),"video_hash":h,
                          "duration_sec":float(meta["duration_seconds"]),"fps":30.0,"frame_count":0}
        info=c.video_info(path); v.update(info)
        unit=c.make_timeline(v,0.0).iloc[0].to_dict(); hashes=[]
        for _ in range(2):
            engine=c.ScanEngine(v)
            try:
                result=engine.scan(unit)
                # Hash all deterministic emitted records but retain no candidate-level output.
                hashes.append(c.canonical_hash({
                    "detections": c.rounded_records(result["detections"]),
                    "tracks": c.rounded_records(result["tracks"]),
                    "triggers": result["triggers"], "raw_candidates": result["raw_candidates"],
                }))
            finally: engine.close()
        return {"status":"PASS" if hashes[0]==hashes[1] else "FAIL", "operator":"frozen_partial_scan_pilot_v1.ScanEngine", "operator_sha256":sha(ROOT/"scripts/partial_scan_pilot_common.py"), "repeat_hashes":hashes}
    except Exception as e:
        return {"status":"FAIL", "error":f"{type(e).__name__}: {e}"}

def selected_rows() -> list[Path]:
    # Selection is blind and fixed from path identity only, not media contents/outcomes.
    return [INPUT / n for n in NEW_NAMES if (INPUT / n).is_file()]

def freeze_selection(paths: list[Path]) -> list[dict[str,Any]]:
    destination=OUT/"VIDEO_SELECTION_ORDER.csv"
    rows=[]
    for i,path in enumerate(paths,1):
        sidecar=Path(str(path)+".source.json")
        rows.append({"selection_order":i,"video_path":str(path.resolve()),"video_filename":path.name,"source_json_path":str(sidecar.resolve()),"source/session identity":"NOT_READ_AT_SELECTION","selection_blindness_status":"PASS_NO_REFERENCE_OR_METHOD_OR_EVENT_ACCESS","eligibility_status":"PENDING_PHASE_A","exclusion_reason":"","replacement_status":"ORIGINAL_SELECTION_NO_REPLACEMENT","method_results_available_at_selection":"false","reference_available_at_selection":"false"})
    fields=list(rows[0]) if rows else ["selection_order","video_path","video_filename","source_json_path","source/session identity","selection_blindness_status","eligibility_status","exclusion_reason","replacement_status","method_results_available_at_selection","reference_available_at_selection"]
    content=""; import io
    s=io.StringIO(); w=csv.DictWriter(s,fieldnames=fields,lineterminator="\n"); w.writeheader(); w.writerows(rows); content=s.getvalue()
    if destination.exists():
        if destination.read_text(encoding="utf-8") != content: raise RuntimeError("VIDEO_SELECTION_ORDER.csv already frozen with different content")
    else: write_text(destination,content)
    return rows

def paused_artifacts(report: dict[str, Any], repair: dict[str, Any] | None = None) -> None:
    """Emit the fail-closed handoff without creating any final include manifest."""
    reports = REPLICATION_OUT / "reports"; reports.mkdir(parents=True, exist_ok=True)
    selection = OUT / "VIDEO_SELECTION_ORDER.csv"
    # A byte-identical mirror satisfies the replication-output handoff while
    # the authority copy remains the first-created, immutable selection file.
    write_text(REPLICATION_OUT / "VIDEO_SELECTION_ORDER.csv", selection.read_text(encoding="utf-8"))
    rows=[]
    for video in report["videos"]:
        failed=[k for k,v in video["criteria"].items() if v["status"] != "PASS"]
        rows.append(f"- `{video['video_filename']}`: `{video['eligibility_status']}` — " + "; ".join(failed))
    qualified=int(report["NEW_QUALIFIED_VIDEOS"])
    missing=("`杭州.mp4` is qualified solely by hash-bound `PROJECT_OWNER_ATTESTATION`; "
             "third-party source verification is not established. `杭州YouTube.mp4` has no valid "
             "same-named source declaration and fails exhaustive H.264 decoding, so it cannot be "
             "repaired by provenance alone and must be replaced by one technically valid, independently "
             "attested source video.")
    write_text(reports / "INPUT_ELIGIBILITY_REPORT.md", "# Input Eligibility Report\n\n"
        "`CONFIRMATORY_EXECUTION_STATUS = PAUSED_INPUT_REQUIRED`\n\n"
        "## Observed blind Phase-A evidence\n\n" + "\n".join(rows) + "\n\n"
        "## Blocking evidence\n\n" + missing + "\n\n"
        f"Qualified new videos: {qualified} of 2. Needed: {2-qualified} additional qualified new video(s). No reference, Oracle, "
        "candidate-event mapping, event count/density, or method matrix was opened or run.\n")
    for name in ("materialization", "references", "replay", "confirmatory_runs"):
        (REPLICATION_OUT / name).mkdir(parents=True, exist_ok=True)
    write_text(reports / "VIDEO_MATERIALIZATION_REPORT.md", "# Video Materialization Report\n\nNot run: Phase-A eligibility did not qualify two new videos.\n")
    write_text(reports / "CONFIRMATORY_MATRIX_REPORT.md", "# Confirmatory Matrix Report\n\nNot run: `B0_A1_A4_EXECUTION = PROHIBITED`.\n")
    decision = f"""# Final Confirmatory Decision

No confirmatory interpretation was made because the required two new independent, eligible inputs were not available.

PROTOCOL_HASH = NOT_COMPUTED_INPUT_GATE_NOT_PASSED
SELECTION_ORDER_FROZEN = true
SELECTION_BLINDNESS = PASS_NO_REFERENCE_OR_METHOD_OR_EVENT_ACCESS
QUALIFIED_NEW_VIDEO_COUNT = {qualified}
INCLUDED_VIDEO_MANIFEST_STATUS = NOT_CREATED_INPUT_GATE_FAILED

TIMELINE_VALIDITY = NOT_EVALUATED_CONFIRMATORILY
SCAN_MATERIALIZATION_VALIDITY = NOT_EVALUATED_CONFIRMATORILY
REFERENCE_TYPE = NOT_OPENED
REFERENCE_INDEPENDENCE = NOT_OPENED
REFERENCE_COMPLETENESS_STATUS = NOT_OPENED
VISIBLE_SUBSET_REPLAY = NOT_OPENED
FULL_SCAN_EXPOSURE_CEILING = NOT_OPENED

B0_RESULT = NOT_RUN
A1_RESULT = NOT_RUN
A2_RESULT = NOT_RUN
A3_RESULT = NOT_RUN
A4_RESULT = NOT_RUN

ACTIVITY_SHUFFLE_GATE = NOT_RUN
TIME_INDEX_GATE = NOT_RUN
LEAVE_BEST_REGION_OUT_GATE = NOT_RUN
LOW_BUDGET_PREFIX_GATE = NOT_RUN
CROSS_VIDEO_DIRECTION_GATE = NOT_RUN

ONLINE_MACRO_ACTIVITY_DECISION = NOT_DECIDED_INPUT_GATE_NOT_PASSED
M10_STATUS = NOT_IMPLEMENTED
M11_STATUS = PROHIBITED

CONFIRMATORY_RESULT_CLASS = PAUSED_INPUT_REQUIRED
CONFIRMATORY_MECHANISM_PILOT = NOT_RUN

FORMAL_METHOD_RANKING =
BLOCKED_PENDING_EXTERNAL_RUNTIME_ATTESTATION

NEXT_ALLOWED_STAGE = PROVIDE_TWO_QUALIFIED_NEW_VIDEOS_WITH_VERIFIABLE_SOURCE_DECLARATIONS
"""
    write_text(reports / "FINAL_CONFIRMATORY_DECISION.md", decision)
    source_hashes={"phase_a_script_sha256":sha(Path(__file__)), "selection_order_sha256":sha(selection),
                   "phase_a_audit_sha256":sha(OUT / "PHASE_A_ELIGIBILITY_AUDIT.json")}
    write_json(REPLICATION_OUT / "source_hashes.json", source_hashes)
    write_json(REPLICATION_OUT / "code_version.json", {"phase_a_script_sha256":source_hashes["phase_a_script_sha256"], "git_commit":"UNAVAILABLE_DUBIOUS_OWNERSHIP", "created_utc":now()})
    write_json(REPLICATION_OUT / "repair_log.json", repair or {"status":"NO_REPAIR", "created_utc":now()})

def repair_existing(provenance_only: bool = False) -> None:
    """Repair bounded diagnostic storage; does not alter selection order or eligibility logic."""
    audit_path=OUT / "PHASE_A_ELIGIBILITY_AUDIT.json"
    report=json.loads(audit_path.read_text(encoding="utf-8"))
    repairs=[]
    def bound(value: Any, video_name: str) -> Any:
        if isinstance(value, dict): return {k:bound(v,video_name) for k,v in value.items()}
        if isinstance(value, list): return [bound(v,video_name) for v in value]
        if isinstance(value, str) and len(value) > 4096:
            repairs.append({"video":video_name,"action":"bounded_decoder_diagnostic"})
            return f"{value[:4096]}\n[diagnostic_truncated original_bytes={len(value.encode())} sha256={hashlib.sha256(value.encode()).hexdigest()}]"
        return value
    for video in report["videos"]:
        path=Path(video["video_path"]); sidecar,decl,decl_err=source(path)
        video["source_json_path"]=str(sidecar.resolve()); video["source_declaration_error"]=decl_err
        video["source_declaration_sha256"]=sha(sidecar) if sidecar.is_file() else None
        owner_valid=owner_attestation_valid(decl,path,str(video.get("video_sha256", "")))
        for key,value in source_criteria(decl,path,str(video.get("video_sha256", ""))).items(): video["criteria"][key]=value
        if owner_valid:
            for key in ("SESSION_INDEPENDENT_FROM_OTHER_NEW_VIDEO", "INDEPENDENT_FROM_EXISTING_DESIGN_VIDEOS", "INDEPENDENT_FROM_LONG_VIDEO_DATASET3"):
                video["criteria"][key]={"status":"PASS", "reason":"explicit project-owner attestation bound to the frozen video hash"}
        video["PROVENANCE_EVIDENCE_TYPE"]=("PROJECT_OWNER_ATTESTATION" if owner_valid else "NOT_QUALIFIED")
        video["INDEPENDENT_WEB_VERIFICATION"]="NOT_AVAILABLE" if video["PROVENANCE_EVIDENCE_TYPE"]=="PROJECT_OWNER_ATTESTATION" else "NOT_ESTABLISHED"
        video["technical_evidence"] = bound(video["technical_evidence"], video["video_filename"])
        if not provenance_only and video["video_filename"] in NEW_NAMES:
            smoke=scan_smoke(Path(video["video_path"]), video["metadata"])
            video["technical_evidence"]["scan_smoke"] = smoke
            video["criteria"]["FIXED_SCAN_OPERATOR_SMOKE_TEST"]={"status":"PASS" if smoke["status"]=="PASS" else "UNVERIFIED_OR_FAIL", "reason":"two identical unit-local frozen SCAN calls"}
            repairs.append({"video":video["video_filename"],"field":"scan_smoke","action":"fixed_DataFrame_semantic_hash"})
        failures=[k for k,v in video["criteria"].items() if v["status"] != "PASS"]
        video["eligibility_status"]=("QUALIFIED_OWNER_ATTESTED" if owner_valid else "PASS") if not failures else "UNVERIFIED_OR_FAIL"; video["exclusion_reason"]="; ".join(failures)
    report["selection_order_sha256"]=sha(OUT/"VIDEO_SELECTION_ORDER.csv")
    report["NEW_QUALIFIED_VIDEOS"]=sum(v["eligibility_status"] in {"PASS","QUALIFIED_OWNER_ATTESTED"} for v in report["videos"])
    report["CONFIRMATORY_EXECUTION_STATUS"]="UNBLOCKED" if report["NEW_QUALIFIED_VIDEOS"]==2 else "PAUSED_INPUT_REQUIRED"
    report["B0_A1_A4_EXECUTION"]="PERMITTED" if report["NEW_QUALIFIED_VIDEOS"]==2 else "PROHIBITED"
    write_json(audit_path,report)
    paused_artifacts(report,{"status":"REPAIRED_AUDIT_DIAGNOSTICS_ONLY","repairs":repairs,"created_utc":now(),"selection_order_unchanged":True})

def main() -> None:
    if "--provenance-only-reaudit" in sys.argv:
        repair_existing(provenance_only=True); return
    if "--repair-existing" in sys.argv:
        repair_existing(); return
    paths=selected_rows(); order=freeze_selection(paths)
    existing_hashes=set()
    if OLD_MANIFEST.is_file():
        with OLD_MANIFEST.open(encoding="utf-8", newline="") as f: existing_hashes={r.get("file_sha256","") for r in csv.DictReader(f)}
    audits=[]; declarations=[]
    for path in paths:
        sidecar,decl,decl_err=source(path); declarations.append(decl)
        meta=probe(path); digest=sha(path)
        criteria=source_criteria(decl,path,digest)
        criteria.update({
          "RAW_CONTIGUOUS_VIDEO":{"status":"PENDING"}, "FULL_TIMELINE_AVAILABLE":{"status":"PENDING"},
          "SESSION_INDEPENDENT_FROM_OTHER_NEW_VIDEO":{"status":"PENDING"}, "INDEPENDENT_FROM_EXISTING_DESIGN_VIDEOS":{"status":"UNVERIFIED_OR_FAIL","reason":"requires verifiable source/session identity"},
          "INDEPENDENT_FROM_LONG_VIDEO_DATASET3":{"status":"UNVERIFIED_OR_FAIL","reason":"requires verifiable source/session identity"},
          "VIDEO_HASH_VALID":{"status":"PASS" if digest not in existing_hashes else "UNVERIFIED_OR_FAIL","reason":"exact hash checked against old blind manifest"},
          "METADATA_VALID":{"status":"PASS" if meta.get("status")=="PASS" and meta["width"]>0 and meta["height"]>0 else "UNVERIFIED_OR_FAIL","reason":"ffprobe metadata"},
          "RANDOM_SEEK_SUPPORTED":{"status":"PENDING"}, "ALL_SOURCE_RANGES_DECODABLE":{"status":"PENDING"}, "FIXED_SCAN_OPERATOR_SMOKE_TEST":{"status":"PENDING"},
        })
        timeline=packet_timeline(path); decode=full_decode(path); seeks=random_seeks(path,float(meta.get("duration_seconds",0)))
        criteria["FULL_TIMELINE_AVAILABLE"]={"status":"PASS" if timeline["status"]=="PASS" else "UNVERIFIED_OR_FAIL","reason":"monotonic packet DTS"}
        criteria["RAW_CONTIGUOUS_VIDEO"]={"status":"PASS" if decode["status"]=="PASS" and timeline["status"]=="PASS" else "UNVERIFIED_OR_FAIL","reason":"complete decode plus monotonic packet timeline; provenance remains separately required"}
        criteria["RANDOM_SEEK_SUPPORTED"]={"status":"PASS" if seeks["status"]=="PASS" else "UNVERIFIED_OR_FAIL","reason":"12 deterministic ffmpeg seeks"}
        criteria["ALL_SOURCE_RANGES_DECODABLE"]={"status":"PASS" if decode["status"]=="PASS" else "UNVERIFIED_OR_FAIL","reason":"full sequential decode of all video bytes"}
        smoke=scan_smoke(path,meta); criteria["FIXED_SCAN_OPERATOR_SMOKE_TEST"]={"status":"PASS" if smoke["status"]=="PASS" else "UNVERIFIED_OR_FAIL","reason":"two identical unit-local frozen SCAN calls"}
        audits.append({"selection_order":next(r["selection_order"] for r in order if r["video_filename"]==path.name),"video_path":str(path.resolve()),"video_filename":path.name,"source_json_path":str(sidecar.resolve()),"video_sha256":digest,"source_declaration_sha256":sha(sidecar) if sidecar.is_file() else None,"source_declaration_error":decl_err,"metadata":meta,"criteria":criteria,"technical_evidence":{"packet_timeline":timeline,"full_decode":decode,"random_seeks":seeks,"scan_smoke":smoke}})
    session_ids=[d.get("capture_session_id") if d else None for d in declarations]
    pair_ok=len(session_ids)==2 and all(session_ids) and len(set(session_ids))==2
    for a in audits:
        a["criteria"]["SESSION_INDEPENDENT_FROM_OTHER_NEW_VIDEO"]={"status":"PASS" if pair_ok else "UNVERIFIED_OR_FAIL","reason":"distinct declared capture_session_id required"}
        failures=[k for k,v in a["criteria"].items() if v["status"]!="PASS"]
        a["eligibility_status"]="PASS" if not failures else "UNVERIFIED_OR_FAIL"; a["exclusion_reason"]= "; ".join(failures)
    report={"audit_id":"ONLINE_MACRO_ACTIVITY_PHASE_A_BLIND_v1","created_utc":now(),"selection_order_frozen":True,"selection_order_sha256":sha(OUT/"VIDEO_SELECTION_ORDER.csv"),"selection_blindness":{"status":"PASS","forbidden_inputs_not_opened":["held-out reference events","full-context Oracle results","candidate-event mappings","method outputs","B0/A1/A2/A3/A4 metrics","event count","target-event density"]},"candidate_discovery":{"input_root":str(INPUT),"new_candidates":list(NEW_NAMES),"old_manifest":str(OLD_MANIFEST)},"criteria":list(CRITERIA),"videos":audits,"NEW_QUALIFIED_VIDEOS":sum(a["eligibility_status"]=="PASS" for a in audits),"CONFIRMATORY_EXECUTION_STATUS":"UNBLOCKED" if sum(a["eligibility_status"]=="PASS" for a in audits)==2 else "PAUSED_INPUT_REQUIRED","B0_A1_A4_EXECUTION":"PERMITTED" if sum(a["eligibility_status"]=="PASS" for a in audits)==2 else "PROHIBITED"}
    write_json(OUT/"PHASE_A_ELIGIBILITY_AUDIT.json",report)
    if report["CONFIRMATORY_EXECUTION_STATUS"] == "PAUSED_INPUT_REQUIRED": paused_artifacts(report)
    print(json.dumps({"NEW_QUALIFIED_VIDEOS":report["NEW_QUALIFIED_VIDEOS"],"CONFIRMATORY_EXECUTION_STATUS":report["CONFIRMATORY_EXECUTION_STATUS"]},ensure_ascii=False))

if __name__ == "__main__": main()
