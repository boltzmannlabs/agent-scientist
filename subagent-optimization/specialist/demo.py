"""Prepare an artificial assignment and validate a canned answer. No model runs."""
import json
from specialist.advisor import prepare, accept
from specialist.fixtures import source, canned_answer


if __name__ == "__main__":
    snapshot = source()
    assignment = prepare(snapshot)
    advice = canned_answer(assignment["input_digest"])
    print(json.dumps({"scope": "Artificial handoff and canned response only; no model or scientific execution",
                      "invocation_status": assignment["status"],
                      "eligible_libraries": assignment["packet"]["eligible_library_ids"],
                      "context_characters": len(assignment["request"]["context"]),
                      "receipt": accept(assignment, advice, snapshot)}, indent=2))
