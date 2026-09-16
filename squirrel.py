#!/usr/bin/env python3
"""
squirrel.py — an archival squirrel for local model hoards.

Named by someone else in the room on September 15 2026, where six people
were working out what to do about the landscape. The word came first and
it was not mine. See CREDIT in the README.

Co-authored with Elias Vale: the atomic writes and the separation of
declared from inferred provenance are his amendments, adopted the same
evening. Named here at his own word.

WHAT IT DOES
    Walks a folder of downloaded models, hashes every file, and writes a
    catalogue that lives OUTSIDE the drive it describes — because a manifest
    stored inside the box it inventories is optimism with extra steps.

WHY IT EXISTS
    A 40GB model file that quietly corrupts on an external drive is worthless,
    and you find out at the exact moment you need it: months later, on new
    hardware, with the original repo possibly gone. Nothing warns you. The
    archive silently downgrades from insurance to superstition.

    Also: weights alone are not a model. Without config.json and the tokenizer
    files you have forty gigabytes of correct numbers and no door into them.
    The squirrel checks for the door.

USAGE
    python squirrel.py catalogue <models-dir> --out <catalogue.json>
    python squirrel.py verify    <models-dir> --catalogue <catalogue.json>
    python squirrel.py report    --catalogue <catalogue.json>

    # typical:
    python squirrel.py catalogue F:/models --out C:/backups/ark-catalogue.json
    python squirrel.py verify    F:/models --catalogue C:/backups/ark-catalogue.json

    --quick   hash first+last 8MB only. ~100x faster, catches drive rot and
              truncation, will not catch a single flipped bit mid-file.
              Fine for a routine check. Use a full pass after any drive move.

Standard library only. No dependencies. Runs on Windows, macOS, Linux.
Share freely. Tools travel; data doesn't.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

# Windows consoles default to cp1252 and will hard-crash on any non-ASCII
# output. Ask for UTF-8; fall back to never emitting anything fancy.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

WARN = "!!"  # deliberately ASCII. See above.

CHUNK = 8 * 1024 * 1024  # 8 MB

# Files that must accompany safetensors weights or the model will not load.
SAFETENSORS_COMPANIONS = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
]
NICE_TO_HAVE = [
    "generation_config.json",
    "special_tokens_map.json",
    "README.md",          # the model card — provenance
    "LICENSE",
    "LICENSE.txt",
]

WEIGHT_SUFFIXES = {".gguf", ".safetensors", ".bin", ".pt", ".pth"}


def is_weight_file(p: Path) -> bool:
    """True for weight files INCLUDING split parts.

    Large models are almost always split, and the naming varies:
        model.gguf.part1of2          <- suffix reads '.part1of2'
        model-00001-of-00002.gguf    <- suffix reads '.gguf', fine
        model.safetensors.part2of3
    Checking Path.suffix alone reports a folder holding 50GB of weights as
    empty. Ask me how I know.
    """
    name = p.name.lower()
    return any(s in name for s in WEIGHT_SUFFIXES)


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:,.1f} {unit}" if unit != "B" else f"{n:,.0f} B"
        n /= 1024


def sha256(path, quick=False):
    """Full SHA256, or a first+last 8MB digest when quick=True."""
    h = hashlib.sha256()
    size = path.stat().st_size
    with path.open("rb") as f:
        if quick and size > 2 * CHUNK:
            h.update(f.read(CHUNK))
            f.seek(-CHUNK, os.SEEK_END)
            h.update(f.read(CHUNK))
            h.update(str(size).encode())  # bind the digest to the length
        else:
            while chunk := f.read(CHUNK):
                h.update(chunk)
    return h.hexdigest()


def scan_model_dir(d: Path):
    """Inspect one model folder: weights, companions, what's missing."""
    files = [p for p in d.rglob("*") if p.is_file() and ".cache" not in p.parts]
    weights = [p for p in files if is_weight_file(p)]
    names = {p.name for p in files}

    has_safetensors = any(".safetensors" in p.name.lower() for p in weights)
    has_gguf = any(".gguf" in p.name.lower() for p in weights)

    missing, warnings = [], []

    if has_safetensors:
        missing = [c for c in SAFETENSORS_COMPANIONS if c not in names]
        if missing:
            warnings.append(
                "SAFETENSORS PRESENT BUT WILL NOT LOAD — missing: "
                + ", ".join(missing)
            )

    if has_gguf and not any("mmproj" in n.lower() for n in names):
        warnings.append(
            "no mmproj file found — if this model has vision, it is blind. "
            "Check the source repo."
        )

    if not any(n in names for n in ("README.md", "MODEL-CARD.md")):
        warnings.append("no model card — provenance is thin")

    if not any(n.upper().startswith("LICENSE") for n in names):
        warnings.append("no licence file — matters if the landscape shifts")

    if not weights:
        warnings.append("no weight files found in this folder")

    return files, weights, missing, warnings


def read_provenance(d: Path):
    """DECLARED provenance vs INFERRED.

    Amendment from the room, Sep 15 2026: "distinguish declared provenance from
    anything inferred from filenames. A beautifully checksummed mystery is
    still a mystery."

    DECLARED = a PROVENANCE.json somebody actually wrote, naming the source
    repo, revision, licence and download date. Trustworthy.
    INFERRED = folder names and filename guesses. Useful, never authoritative,
    and clearly labelled so future-us can tell the difference.
    """
    declared = None
    pf = d / "PROVENANCE.json"
    if pf.exists():
        try:
            # utf-8-sig: forgive the BOM that PowerShell's Set-Content stamps on
            # files (bug #4 in our own README). A tool that documents a trap
            # should not fall into it. Found in the field, Sep 16 2026.
            declared = json.loads(pf.read_text(encoding="utf-8-sig"))
        except Exception as e:
            declared = {"_error": f"PROVENANCE.json present but unreadable: {e}"}

    names = [p.name.lower() for p in d.rglob("*") if p.is_file()]
    inferred = {
        "_warning": "GUESSED from file and folder names. Not authoritative.",
        "folder_name": d.name,
        "looks_abliterated": any(
            k in d.name.lower() or any(k in n for n in names)
            for k in ("abliterat", "uncensored", "heretic", "derestricted")
        ),
        "quants_present": sorted({
            q for q in ("Q2_K", "Q3_K", "Q4_K", "Q5_K", "Q6_K", "Q8_0",
                        "IQ2", "IQ3", "IQ4", "BF16", "F16", "FP8")
            if any(q.lower() in n for n in names)
        }),
    }
    return declared, inferred


def atomic_write(path: Path, text: str):
    """Write via temp + replace. A half-written catalogue that looks valid is
    worse than no catalogue - same amendment, same sitting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    # fsync must happen on the WRITE handle, before close. Windows refuses
    # fsync on a read-only descriptor (Errno 9). Caught in testing.
    with tmp.open("w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)  # atomic on POSIX and on Windows (same volume)


def cmd_catalogue(args):
    root = Path(args.models_dir).resolve()
    out = Path(args.out).resolve()

    if not root.is_dir():
        sys.exit(f"not a directory: {root}")

    # Refuse to write the catalogue inside the tree it describes.
    try:
        out.relative_to(root)
        sys.exit(
            f"\nREFUSED: the catalogue would live inside the drive it describes.\n"
            f"  scanning : {root}\n"
            f"  writing  : {out}\n"
            f"That is the one thing this tool exists to prevent. Pick a path on\n"
            f"a different drive.\n"
        )
    except ValueError:
        pass  # good — it's outside

    model_dirs = sorted([d for d in root.iterdir() if d.is_dir()
                         and not d.name.startswith("_")
                         and not d.name.startswith(".")])
    if not model_dirs:
        model_dirs = [root]

    catalogue = {
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "root": str(root),
        "mode": "quick" if args.quick else "full",
        "models": [],
    }

    grand_total = 0
    print(f"\ncataloguing {len(model_dirs)} model folder(s) under {root}")
    print(f"mode: {'QUICK (first+last 8MB)' if args.quick else 'FULL SHA256'}\n")

    for d in model_dirs:
        files, weights, missing, warnings = scan_model_dir(d)
        total = sum(p.stat().st_size for p in files)
        grand_total += total
        print(f"  {d.name}  ({human(total)}, {len(files)} files)")

        declared, inferred = read_provenance(d)
        if declared is None:
            warnings.append(
                "NO DECLARED PROVENANCE - write a PROVENANCE.json naming the "
                "source repo, revision, licence and download date. A "
                "beautifully checksummed mystery is still a mystery.")
        entry = {
            "name": d.name,
            "path": str(d),
            "provenance_declared": declared,
            "provenance_inferred": inferred,
            "total_bytes": total,
            "file_count": len(files),
            "missing_required": missing,
            "warnings": warnings,
            "files": [],
        }

        for p in sorted(files):
            t0 = time.time()
            digest = sha256(p, quick=args.quick)
            size = p.stat().st_size
            if size > 1024 ** 3:
                dt = time.time() - t0
                rate = "" if args.quick else (f" [{human(size/dt)}/s]" if dt > 0.5 else "")
                print(f"      {p.name[:58]:<58} {human(size):>10}{rate}")
            entry["files"].append({
                "relpath": str(p.relative_to(d)),
                "bytes": size,
                "sha256": digest,
                "mtime": int(p.stat().st_mtime),
            })

        for w in warnings:
            print(f"      {WARN}  {w}")
        catalogue["models"].append(entry)

    catalogue["total_bytes"] = grand_total
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(out, json.dumps(catalogue, indent=2))

    print(f"\ncatalogued {human(grand_total)} across {len(model_dirs)} model(s)")
    print(f"written to {out}")
    print("keep that file somewhere that is not the drive it describes.\n")


def cmd_verify(args):
    root = Path(args.models_dir).resolve()
    cat = json.loads(Path(args.catalogue).read_text(encoding="utf-8"))
    quick = cat.get("mode") == "quick"

    print(f"\nverifying {root} against catalogue of {cat['created']}")
    print(f"mode: {'QUICK' if quick else 'FULL'}\n")

    ok = missing = corrupt = 0
    problems = []

    for m in cat["models"]:
        d = root / m["name"]
        print(f"  {m['name']}")
        for f in m["files"]:
            p = d / f["relpath"]
            if not p.exists():
                missing += 1
                problems.append(f"MISSING  {m['name']}/{f['relpath']}")
                print(f"      MISSING   {f['relpath']}")
                continue
            if p.stat().st_size != f["bytes"]:
                corrupt += 1
                problems.append(
                    f"SIZE     {m['name']}/{f['relpath']} "
                    f"({human(p.stat().st_size)} vs {human(f['bytes'])})")
                print(f"      SIZE!     {f['relpath']}")
                continue
            if sha256(p, quick=quick) != f["sha256"]:
                corrupt += 1
                problems.append(f"CORRUPT  {m['name']}/{f['relpath']}")
                print(f"      CORRUPT!  {f['relpath']}")
                continue
            ok += 1

    print(f"\n  intact  : {ok}")
    print(f"  missing : {missing}")
    print(f"  corrupt : {corrupt}")

    if problems:
        print("\n  PROBLEMS:")
        for p in problems:
            print(f"    {p}")
        print("\n  Re-download the affected files while you still can.\n")
        sys.exit(1)
    print("\n  Everything is where you left it and still itself.\n")


def cmd_report(args):
    cat = json.loads(Path(args.catalogue).read_text(encoding="utf-8"))
    print(f"\nTHE ARK — catalogued {cat['created']}")
    print(f"root: {cat['root']}")
    print(f"total: {human(cat['total_bytes'])}\n")
    for m in sorted(cat["models"], key=lambda x: -x["total_bytes"]):
        print(f"  {human(m['total_bytes']):>12}  {m['name']}  ({m['file_count']} files)")
        for w in m.get("warnings", []):
            print(f"                {WARN}  {w}")
    print()


def main():
    ap = argparse.ArgumentParser(
        description="An archival squirrel for local model hoards.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("catalogue", help="hash everything, write the catalogue")
    c.add_argument("models_dir")
    c.add_argument("--out", required=True, help="MUST be on a different drive")
    c.add_argument("--quick", action="store_true")
    c.set_defaults(func=cmd_catalogue)

    v = sub.add_parser("verify", help="re-check the hoard against a catalogue")
    v.add_argument("models_dir")
    v.add_argument("--catalogue", required=True)
    v.set_defaults(func=cmd_verify)

    r = sub.add_parser("report", help="print a catalogue, human-readable")
    r.add_argument("--catalogue", required=True)
    r.set_defaults(func=cmd_report)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
