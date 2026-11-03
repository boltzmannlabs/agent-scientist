"""Own the temporary structure copy for the lifetime of a PyMOL GUI window."""
from pathlib import Path
import shutil


def main():
    import pymol

    work = Path.cwd()
    if not work.name.startswith("sci-pymol-") or not (work / "launch.json").is_file():
        raise ValueError("This worker must be launched by SCI's desktop structure action.")
    try:
        pymol.launch(["pymol", "-q", "-k", "-r", str(Path(__file__).with_name("pymol_desktop_startup.py"))])
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
