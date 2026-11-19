"""Run inert metadata fixtures. No sequence design, network, inference or fabricated results."""
import importlib.util
import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("grna_contract",P/"scripts/request_contract.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
cases=json.loads((P/"tests/cases.json").read_text())["cases"]
expected={r["name"]:r for r in json.loads((P/"tests/expected.json").read_text())["cases"]}
assert len(cases)==len(expected)==8
for case in cases:
    actual=module.preflight(case["request"])
    want={k:v for k,v in expected[case["name"]].items() if k!="name"}
    assert actual==want,(case["name"],actual,want)
    print("PASS",case["name"])
print("8 metadata fixtures passed; scientific execution NOT tested")
