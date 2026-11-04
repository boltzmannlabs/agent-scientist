"""Trusted PyMOL startup recipe; structure data never becomes command text."""
import json
import os
from pathlib import Path


def main():
    from pymol import cmd

    work = Path.cwd()
    manifest = json.loads((work / "launch.json").read_text(encoding="utf-8-sig"))
    suffix = manifest["suffix"]
    if suffix not in {".pdb", ".cif", ".mmcif"}:
        raise ValueError("Unsupported structure format")
    cmd.set("max_threads", 2)
    cmd.load(str(work / ("structure" + suffix)), "structure", format="pdb" if suffix == ".pdb" else "cif")
    atoms = cmd.count_atoms("structure")
    if not atoms:
        raise ValueError("No atoms found")
    cmd.hide("everything", "all")
    cmd.show("cartoon", "polymer")
    cmd.show("sticks", "organic")
    if not cmd.count_atoms("polymer"):
        cmd.show("sticks", "all")
    cmd.color("cyan", "structure")
    cmd.orient("structure")
    cmd.set_title("structure", 1, manifest["name"])
    (work / "ready.tmp").write_text(json.dumps({"atoms": atoms, "version": cmd.get_version()[0]}), encoding="utf-8")

    (work / "ready.tmp").replace(work / "ready.json")
    with open(os.devnull, "wb") as sink:
        os.dup2(sink.fileno(), 2)


# PyMOL's `run` executes -r scripts in its global `pymol` namespace.
if __name__ in {"__main__", "pymol"}:
    main()
