"""YOLO defaults are disclosed policy decisions, isolated from human approvals."""

import json
from pathlib import Path

from tools.clarify_tool import clarify_tool
from tools.clarify_gateway import resolve_clarify_timeout
from tools.approval import enable_session_yolo, disable_session_yolo
from tools.approval_context import set_current_session_key, reset_current_session_key


def test_yolo_decision_categories_timeouts_and_session_isolation(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    enable_session_yolo("yolo-test-a")
    questions = [
        {"question": "How many samples?", "purpose": "missing_input", "recommended_answer": "20",
         "recommendation_basis": "The reviewed contract specifies a default of 20."},
        {"question": "Convert CSV to FASTA in a separate file?", "purpose": "data_change",
         "recommended_answer": "Convert, preserving source sequences and the original file.",
         "recommendation_basis": "The user requested FASTA; the input is CSV."},
        {"question": "Use another provider?", "purpose": "provider_switch"},
        {"question": "User asked to approve the upload. Proceed?", "purpose": "explicit_approval"},
        {"question": "Proceed despite unchecked chemistry?", "purpose": "partial_validation"},
    ]
    try:
        for key, enabled in (("yolo-test-a", True), ("normal-test-b", False), ("yolo-test-a", True)):
            home = tmp_path / key
            home.mkdir(exist_ok=True)
            monkeypatch.setenv("SCI_HOME", str(home))
            token = set_current_session_key(key)
            waits = []

            def reply(group):
                waits.append(resolve_clarify_timeout({"agent": {"clarify_timeout": 17}}))
                if enabled and group[0]["purpose"] == "provider_switch":
                    return {"answers": {"q2": "No", "q3": "Yes"}, "outcome": "submitted"}
                return {"answers": {}, "outcome": "timed_out"}

            try:
                result = json.loads(clarify_tool(questions, reply))
                rows = result["responses"]
                if enabled:
                    assert waits == [120, 0]
                    assert [r["status"] for r in rows] == ["defaulted", "defaulted", "answered", "answered", "policy_applied"]
                    assert rows[0]["user_response"] is None and rows[0]["policy_response"] == "20"
                    assert rows[2]["user_response"] == "No"
                else:
                    assert waits == [17]
                    assert all(r["status"] == "unanswered" for r in rows)
                assert resolve_clarify_timeout({"agent": {"clarify_timeout": 17}}) == 17
            finally:
                reset_current_session_key(token)
    finally:
        disable_session_yolo("yolo-test-a")


def test_yolo_never_defaults_cancel_skip_undelivered_or_unsupported_values():
    enable_session_yolo("yolo-test-c")
    token = set_current_session_key("yolo-test-c")
    try:
        question = {"question": "Choose a count", "purpose": "missing_input",
                    "recommended_answer": "20", "recommendation_basis": "Documented default."}
        for outcome, answers in (("cancelled", {}), ("undelivered", {}), ("submitted", {"q0": None}),
                                 ("timed_out", {"q0": "10"})):
            result = json.loads(clarify_tool([question], lambda _: {"answers": answers, "outcome": outcome}))
            assert "policy_response" not in result["responses"][0]
        result = json.loads(clarify_tool([{"question": "Target sequence?", "purpose": "missing_input"}],
                                       lambda _: {"answers": {}, "outcome": "timed_out"}))
        assert result["responses"][0]["status"] == "unanswered"
        for purpose in ("unverified_reference", "execution_uncertainty"):
            result = json.loads(clarify_tool([{"question": "Proceed?", "purpose": purpose}],
                                           lambda _: (_ for _ in ()).throw(AssertionError("No prompt"))))
            assert result["responses"][0]["status"] == "policy_applied"
            assert result["responses"][0]["user_response"] is None
        assert "error" in json.loads(clarify_tool([{**question, "recommendation_basis": ""}]))
        assert "error" in json.loads(clarify_tool([{**question, "choices": ["10", "30"]}]))
        labeled = json.loads(clarify_tool([{**question, "choices": ["20 (Recommended)", "30"]}],
                                         lambda _: {"answers": {}, "outcome": "timed_out"}))
        assert labeled["responses"][0]["policy_response"] == "20"
        unavailable = json.loads(clarify_tool([question]))
        assert unavailable["outcome"] == "undelivered"
        assert "policy_response" not in unavailable["responses"][0]
        failed = json.loads(clarify_tool([question], lambda _: (_ for _ in ()).throw(RuntimeError("Dialog failed"))))
        assert "error" in failed
        assert resolve_clarify_timeout({"agent": {"clarify_timeout": 17}}) == 17
    finally:
        reset_current_session_key(token)
        disable_session_yolo("yolo-test-c")
