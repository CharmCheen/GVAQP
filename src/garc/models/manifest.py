from pathlib import Path
import hashlib
import json

def sha256_file(path, chunk_size=1024 * 1024):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()

def manifest(path):
    p = Path(path)
    files = []
    for f in sorted(x for x in p.rglob("*") if x.is_file()):
        files.append({"path": str(f.relative_to(p)), "size_bytes": f.stat().st_size, "sha256": sha256_file(f)})
    return {"root": str(p), "file_count": len(files), "total_bytes": sum(x["size_bytes"] for x in files), "files": files}

def write_manifest(path, output):
    Path(output).write_text(json.dumps(manifest(path), indent=2) + "\n")
