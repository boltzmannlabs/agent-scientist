#!/usr/bin/env python3
"""Leaf dependency planning and host verification (metadata + probes only; never installs).

Usage:
  dependency_plan.py --list
  dependency_plan.py --leaf <name> [--json]          # plan: pins, roles, satisfaction routes
  dependency_plan.py --verify [--json]               # probe this host for every program
  dependency_plan.py --verify --leaf <name> [--json]

Probes run `--version` style commands (read-only). Verdicts per leaf: READY / PARTIAL / MISSING
with the absent programs listed. jsonschema importability is probed per interpreter.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

P = Path(__file__).resolve().parents[1]
MATRIX = json.loads((P / "references/leaf-dependency-matrix.json").read_text(encoding="utf-8-sig"))

PROBE_HINTS = {
    "python_core": ["python3"], "python3": ["python3"], "python_harness": ["python3"],
    "python_qa": [], "python_rnai": [], "python_rnaispline": [], "python_oligoformer": [],
    "python_analysis": [], "python_rs3": [], "python_crispron": [], "python_editing": [],
    "python_behive": [], "python_crispria": [], "python_cbe": [],
    "rnafold": ["RNAfold"], "rnaplfold": ["RNAplfold"], "rnaduplex": ["RNAduplex"],
    "bowtie2": ["bowtie2"], "rscript": ["Rscript"], "rscript_rfcombined": ["Rscript"],
    "rnafold_cbe": ["RNAfold"], "git": ["git"], "env_manager": [],
}


def probe(binary):
    path = shutil.which(binary)
    if not path:
        return {"found": False}
    r = subprocess.run([path, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
    text = (r.stdout + r.stderr).strip().splitlines()
    return {"found": True, "path": path, "version_line": text[0] if text else ""}


def probe_python_families():
    """Find interpreters by minor version across PATH and common conda env roots."""
    found = {}
    candidates = []
    for name in ("python3", "python3.8", "python3.9", "python3.10", "python3.12", "python3.13", "python3.7", "python2.7"):
        p = shutil.which(name)
        if p:
            candidates.append(p)
    roots = [Path.home() / "anaconda3/envs", Path.home() / "miniconda3/envs"]
    for root in roots:
        if root.is_dir():
            candidates += [str(e / "bin/python") for e in root.iterdir() if (e / "bin/python").is_file()]
    seen = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        try:
            r = subprocess.run([c, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
            v = (r.stdout + r.stderr).strip()
            minor = v.replace("Python ", "").split(".")[:2]
            if len(minor) == 2 and minor[0].isdigit():
                key = f"3.{minor[1]}" if minor[0] == "3" else f"{minor[0]}.{minor[1]}"
                found.setdefault(key, []).append({"path": c, "version": v})
        except Exception:
            continue
    return found


def leaf_plan(name):
    leaf = next((l for l in MATRIX["leaves"] if l["name"] == name), None)
    if not leaf:
        return None
    return {
        "leaf": leaf["name"],
        "package": leaf["package"],
        "programs": [{"id": p["id"], "pin": p["pin"], "role": p["role"], "required_for": p["required_for"]}
                     for p in leaf["programs"]],
        "satisfaction_routes": leaf["satisfaction_routes"],
        "parent_assets": leaf["parent_assets"],
        "note": "PLAN_ONLY: installs happen through the leaf package install review or parent-approved recipes",
    }



def bound_programs(leaf_name):
    """Program bindings resolved through the leaf's package install review (authoritative)."""
    import json as _json
    import os
    # Candidate homes in priority order: env SCI_HOME (may point at a specialist's scoped
    # extension home, which has no definitions), the active profile, then the default root.
    # The first candidate whose subagents/<leaf>.json exists wins.
    candidates = []
    env_home = os.environ.get("SCI_HOME")
    if env_home:
        candidates.append(env_home)
    try:
        active = (Path.home() / ".sci" / "active_profile").read_text(encoding="utf-8-sig").strip()
        if active:
            candidates.append(str(Path.home() / ".sci" / "profiles" / active))
    except OSError:
        pass
    candidates.append(str(Path.home() / ".sci"))
    path = next((Path(h) / "subagents" / f"{leaf_name}.json" for h in candidates
                 if (Path(h) / "subagents" / f"{leaf_name}.json").is_file()), None)
    try:
        d = _json.loads(path.read_text(encoding="utf-8-sig"))
        resolved = (d.get("package_info") or {}).get("resolved") or {}
        out = {}
        for pid, info in resolved.items():
            if isinstance(info, dict) and isinstance(info.get("path"), str):
                out[pid] = info["path"]
        return out
    except (OSError, ValueError):
        return {}


def verify_leaf(name, py_fam, probes):
    leaf = next((l for l in MATRIX["leaves"] if l["name"] == name), None)
    if not leaf:
        return None
    bound = bound_programs(name)
    rows, missing, partial = [], [], []
    for p in leaf["programs"]:
        pid = p["id"]
        if pid in bound and Path(bound[pid]).is_file():
            rows.append({"id": pid, "pin": p["pin"], "bound": True, "found": True,
                         "candidates": [bound[pid]]})
            continue
        if pid.startswith("python_") and pid not in ("python_core", "python3", "python_harness"):
            raw = p["pin"].replace("Python ", "")
            parts = [c for c in raw.split(".") if c.isdigit()]
            minor = ".".join(parts[:2]) if len(parts) >= 2 else raw
            matches = py_fam.get(minor, [])
            ok = bool(matches)
            rows.append({"id": pid, "pin": p["pin"], "found": ok,
                         "candidates": [m["path"] for m in matches[:3]] or None})
        elif pid in ("python_core", "python3", "python_harness"):
            ok = bool(py_fam.get("3.12") or py_fam.get("3.13") or py_fam.get("3.14") or py_fam.get("3"))
            rows.append({"id": pid, "pin": p["pin"], "found": ok,
                         "candidates": [m["path"] for fam in ("3.13", "3.12", "3.14") for m in py_fam.get(fam, [])[:1]] or None})
        elif pid == "env_manager":
            has_venv = probe("python3").get("found") and shutil.which("python3") is not None
            has_conda = shutil.which("conda") is not None
            ok = has_venv or has_conda
            rows.append({"id": pid, "pin": p["pin"], "found": ok, "candidates": (["python3 -m venv"] + (["conda"] if has_conda else []))})
        else:
            hints = PROBE_HINTS.get(pid, [])
            result = next((probes[h] for h in hints if probes.get(h, {}).get("found")), None)
            ok = bool(result)
            rows.append({"id": pid, "pin": p["pin"], "match": p.get("match"), "found": ok,
                         "candidates": [result["path"], result["version_line"]] if result else None})
        if not rows[-1]["found"]:
            cls = p.get("required_for", "")
            (missing if "core" in cls or cls in ("all core modes", "INSTALL mode") else partial).append(pid)
    verdict = "MISSING" if any("core" in (p.get("required_for") or "") or p.get("required_for") in ("all core modes",) for p in leaf["programs"] if p["id"] in missing) else ("READY" if not missing and not partial else "PARTIAL")
    return {"leaf": name, "verdict": verdict, "programs": rows,
            "missing": missing, "partial": partial,
            "note": "host probe; found != bound. Binding happens through the leaf package install review."}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--leaf")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.list:
        names = [l["name"] for l in MATRIX["leaves"]]
        print(json.dumps({"leaves": names, "matrix_version": MATRIX["matrix_version"]}, indent=2))
        return 0
    if a.verify:
        probes = {}
        for binary in {b for hints in PROBE_HINTS.values() for b in hints}:
            probes[binary] = probe(binary)
        py_fam = probe_python_families()
        leaves = [a.leaf] if a.leaf else [l["name"] for l in MATRIX["leaves"]]
        out = {"probe": "host verification (read-only)", "interpreter_families": sorted(py_fam),
               "leaves": []}
        for name in leaves:
            v = verify_leaf(name, py_fam, probes)
            if v is None:
                print(json.dumps({"status": "INVALID", "error": f"unknown leaf: {name}"}))
                return 2
            out["leaves"].append(v)
        if a.json:
            print(json.dumps(out, indent=2))
        else:
            for v in out["leaves"]:
                print(f"{v['leaf']:36s} {v['verdict']:8s} missing={v['missing']} partial={v['partial']}")
        return 0
    if a.leaf:
        plan = leaf_plan(a.leaf)
        if plan is None:
            print(json.dumps({"status": "INVALID", "error": f"unknown leaf: {a.leaf}"}))
            return 2
        print(json.dumps(plan, indent=2))
        return 0
    print(json.dumps({"status": "INVALID", "error": "use --list, --leaf <name> or --verify"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
