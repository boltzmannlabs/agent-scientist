"""Package entry point for the complete standalone publication-calibrated skill."""
import importlib.util
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'skills/publication-calibrated-crispr/scripts/policy.py'
spec=importlib.util.spec_from_file_location('publication_policy',p)
assert spec is not None and spec.loader is not None
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
if __name__=='__main__':raise SystemExit(module.main())
