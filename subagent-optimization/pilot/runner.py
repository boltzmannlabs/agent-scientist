"""Fresh conditional decision pilot; frozen inputs, native receipts, fixed assessment.

Scientific execution stays in the existing connector. Importing CSV/advice can
exercise local processing, but cannot manufacture native-agent execution proof.
Private state lives in an explicit run directory, separate from old campaigns.
"""
from contextlib import contextmanager
from copy import deepcopy
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile

from pilot.bridge import AdapterError, BINDING, JOB_NAME, NodeAPIAdapter, require_property_models
from pilot.context import build_context
from prototype.library_options.coverage import plan
from specialist.advisor import ANSWER_FIELDS, TEXT_FIELDS, LIST_FIELDS, parse_answer


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def assessor_class(config):
    kind = config.get("kind", "pinned_drd2")
    if kind == "pinned_drd2":
        from pilot.assessment import PinnedAssessor
        return PinnedAssessor
    if kind == "platform_lipophilicity_rdkit_v1":
        from pilot.property_assessment import PlatformPropertyAssessor
        return PlatformPropertyAssessor
    raise ValueError("Unsupported frozen assessor kind")


def atomic_json(path, value):
    raw = json.dumps(value, indent=2, allow_nan=False) + "\n"
    fd, temporary = tempfile.mkstemp(prefix=".pilot-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class PilotRun:
    def __init__(self, directory, assessor=None):
        self.directory = Path(directory).resolve()
        self.protocol = json.loads((self.directory / "protocol.json").read_text())
        self.assessor = assessor

    @classmethod
    def create(cls, protocol, directory, *, evidence_mode="development", assessor=None, runtime_identity=None):
        require(evidence_mode in {"development", "fixture"}, "Explicit development/fixture mode required")
        if evidence_mode == "development":
            require_property_models(protocol.get("generation_parameters"))
        if evidence_mode == "development" and assessor is not None:
            require(type(assessor) is assessor_class(protocol["assessor"]),
                    "Development requires the exact assessor declared by the frozen task")
        caps = ("max_unique_candidate_evaluations", "max_credits", "max_reasoning_calls", "max_reasoning_tokens")
        require(all(protocol.get("resources", {}).get(k) is None for k in caps),
                "Numerical caps are not implemented by this first runner; do not claim they are enforced")
        if runtime_identity is not None:
            require(isinstance(runtime_identity, dict) and set(runtime_identity) == {"model", "provider"}
                    and all(isinstance(v, str) and v for v in runtime_identity.values()), "Nonsecret model/provider identity required")
        directory = Path(directory).resolve()
        require(not directory.exists(), "Use a fresh run directory; do not overwrite a campaign")
        bundle = Path(__file__).resolve().parents[1]
        publication_root = bundle.parent if (bundle.parent / ".git").exists() else bundle
        require(evidence_mode == "fixture" or not directory.is_relative_to(publication_root),
                "Keep private development run receipts/artifacts outside the publication checkout")
        directory.mkdir(parents=True, mode=0o700)
        (directory / "artifacts").mkdir(mode=0o700)
        frozen = deepcopy(protocol)
        frozen["evidence_mode"] = evidence_mode
        frozen["runtime_identity"] = deepcopy(runtime_identity)
        frozen["implementation_sha256"] = {
            str(p.relative_to(bundle)): file_sha(p) for p in
            [bundle / "pilot" / f for f in ("runner.py", "protocol.py", "assessment.py", "bridge.py", "native.py", "context.py",
                                           "property_assessment.py", "property_protocol.py")]
            + [bundle / "prototype/library_audit/audit.py", bundle / "prototype/library_options/coverage.py", bundle / "specialist/advisor.py"]}
        atomic_json(directory / "protocol.json", frozen)
        atomic_json(directory / "state.json", {
            "protocol_digest": digest(frozen), "stages": {}, "decisions": {}, "reasoning_attempts": [],
            "evidence_mode": evidence_mode})
        run = cls(directory, assessor)
        with run._state() as state:
            run._add_stage(state, "common", frozen["initial_library_id"])
        return run

    @contextmanager
    def _state(self):
        with (self.directory / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            frozen = json.loads((self.directory / "protocol.json").read_text())
            state = json.loads((self.directory / "state.json").read_text())
            require(digest(frozen) == state["protocol_digest"] == digest(self.protocol), "Frozen protocol changed")
            for name, stage in state["stages"].items():
                require(name == "common" or name in frozen["arms"], "Stage outside frozen pilot")
                if name == "common":
                    library_id = frozen["initial_library_id"]
                else:
                    decision = state["decisions"].get(name, {})
                    advice = decision.get("advice", {})
                    require(decision.get("status") == "validated_advice"
                            and advice.get("disposition") == "recommend",
                            "Follow-up stage requires its validated library recommendation")
                    library_id = advice.get("library_id")
                require(stage["request"] == self._expected_request(state, name, library_id),
                        "Stored request differs from frozen reference/library/settings")
            try:
                yield state
            finally:
                atomic_json(self.directory / "state.json", state)
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _save(self, state):
        atomic_json(self.directory / "state.json", state)

    def _implementation(self):
        bundle = Path(__file__).resolve().parents[1]
        for relative, expected in self.protocol["implementation_sha256"].items():
            require(file_sha(bundle / relative) == expected, "Pilot implementation changed; freeze a new protocol before new execution")

    def _expected_request(self, state, stage_id, library_id):
        lib = next((x for x in self.protocol["libraries"] if x["id"] == library_id), None)
        require(lib is not None, "Library outside frozen menu")
        request = {"protocol_digest": state["protocol_digest"], "stage_id": stage_id,
                   "library_id": library_id, "library_csv_path": lib["csv_path"],
                   "library_content_sha256": lib["content_sha256"],
                   "reference": self.protocol["reference"],
                   "generation_parameters": self.protocol["generation_parameters"]}
        request["request_id"] = digest(request)
        return request

    def _add_stage(self, state, stage_id, library_id):
        require(stage_id not in state["stages"], "Stage already exists")
        request = self._expected_request(state, stage_id, library_id)
        state["stages"][stage_id] = {"request": request, "status": "ready", "receipts": [],
                                     "output": None, "batch": None}

    def _assessor(self):
        if self.assessor is None:
            self.assessor = assessor_class(self.protocol["assessor"])(self.protocol["assessor"])
        if self.protocol["evidence_mode"] == "development":
            require(type(self.assessor) is assessor_class(self.protocol["assessor"]),
                    "Fixture or mismatched assessor cannot enter a development run")
            require(self.assessor.config == self.protocol["assessor"], "Assessor settings differ from the frozen task")
        return self.assessor

    def _scorer_kind(self):
        return self.protocol["assessor"].get("kind", "pinned_drd2")

    def _connector(self, state, adapter):
        if state["evidence_mode"] == "development":
            require(type(adapter) is NodeAPIAdapter and adapter.active_host_instrumented,
                    "Development execution requires the instrumented active-host connector; injected callbacks are not live proof")

    def next(self):
        with self._state() as state:
            common = state["stages"]["common"]
            if common["status"] != "complete":
                return {"phase": "common_observations", "stage_status": common["status"],
                        "request": common["request"], "scientific_execution": "existing NodeAPI connector only"}
            if common["batch"].get("evaluation_blockers"):
                return {"phase": "evaluation_blocked", "agent_comparison_exercised": False,
                        "blockers": common["batch"]["evaluation_blockers"]}
            if common["batch"]["qualified_candidate_ids"]:
                return {"phase": "no_remaining_decision", "agent_comparison_exercised": False,
                        "qualifying_ids": common["batch"]["qualified_candidate_ids"]}
            return {"phase": "conditional_decisions", "arms": {
                arm: {"decision": state["decisions"].get(arm, {}).get("status", "not_requested"),
                      "stage": state["stages"].get(arm, {}).get("status", "not_created")}
                for arm in self.protocol["arms"]}}

    def dispatch(self, stage_id, adapter):
        """One upload/submit progression, with durable pre-call markers and no retries."""
        with self._state() as state:
            self._implementation()
            self._connector(state, adapter)
            stage = state["stages"][stage_id]
            require(stage["status"] in {"ready", "uploaded"}, "Existing attempt must be reconciled; no replacement was sent")
            request = stage["request"]
            if stage["status"] == "ready":
                stage["status"] = "uploading"; self._save(state)
                try:
                    receipt = adapter.upload(request)
                except AdapterError:
                    stage["status"] = "blocked_before_upload"
                    raise
                except Exception:
                    stage["status"] = "upload_unknown"
                    raise RuntimeError("Upload outcome unknown; original attempt retained, no automatic retry") from None
                stage["receipts"].append({"kind": "upload", "value": receipt})
                stage["upload"] = receipt
                if receipt.get("status") != "uploaded" or receipt.get("error"):
                    stage["status"] = "upload_unknown" if receipt.get("status") == "unknown" else "upload_blocked"
                    return deepcopy(receipt)
                stage["status"] = "uploaded"; self._save(state)
            stage["status"] = "submitting"; self._save(state)
            try:
                receipt = adapter.submit(request, stage["upload"])
            except AdapterError:
                stage["status"] = "blocked_before_submit"
                raise
            except Exception:
                stage["status"] = "submit_unknown"
                raise RuntimeError("Submission outcome unknown; original attempt retained, no automatic retry") from None
            stage["receipts"].append({"kind": "submit", "value": receipt})
            stage["submit"] = receipt
            stage["status"] = ("accepted" if receipt.get("status") == "accepted" and not receipt.get("error")
                               else "submit_unknown")
            return deepcopy(receipt)

    def monitor(self, stage_id, adapter):
        with self._state() as state:
            self._connector(state, adapter)
            stage = state["stages"][stage_id]
            require(stage.get("submit", {}).get("doc_id"), "No confirmed job identity; reconcile without guessing an ID")
            try:
                receipt = adapter.status(stage["request"], stage["submit"])
            except Exception:
                stage["receipts"].append({"kind": "monitor_error", "value": "Observation unavailable; science state unchanged"})
                raise RuntimeError("Monitoring failed; existing scientific state is unchanged") from None
            stage["receipts"].append({"kind": "monitor", "value": receipt})
            require(not receipt.get("doc_id") or receipt["doc_id"] == stage["submit"]["doc_id"],
                    "Observation contains a different job ID; existing science state is unchanged")
            require(not receipt.get("job_name") or receipt["job_name"] == JOB_NAME,
                    "Observation contains a different job name; existing science state is unchanged")
            stage["last_monitor"] = receipt
            if not receipt.get("error"):
                status = str(receipt.get("status", "")).lower()
                if status == "completed" and stage["status"] in {"accepted", "submit_unknown", "submitting"}:
                    stage["status"] = "accepted"
                elif status == "failed" and stage["status"] in {"accepted", "submit_unknown", "submitting"}:
                    stage["status"] = "failed"
            return deepcopy(receipt)

    def reconcile(self, stage_id, original_submit_receipt):
        """Attach an authoritative original receipt, never create a replacement operation."""
        with self._state() as state:
            stage = state["stages"][stage_id]
            require(stage["status"] in {"submitting", "submit_unknown"}, "No ambiguous original submission to reconcile")
            receipt = original_submit_receipt
            binding = stage.get("upload", {}).get(BINDING)
            require(binding and receipt.get(BINDING) == binding and receipt.get("doc_id")
                    and receipt.get("job_name", JOB_NAME) == JOB_NAME, "Original request/job binding required")
            require(receipt.get("status") in {"accepted", "unknown"}, "An explicit negative receipt cannot confirm acceptance")
            require(receipt.get("status") != "accepted" or not receipt.get("error"), "Error receipt cannot confirm acceptance")
            stage["receipts"].append({"kind": "reconciliation", "value": deepcopy(receipt)})
            stage["submit"] = deepcopy(receipt)
            stage["status"] = "accepted" if receipt["status"] == "accepted" else "submit_unknown"

    def ingest(self, stage_id, csv_path, receipt):
        """Snapshot and assess a complete artifact, retaining all rows and original receipts."""
        with self._state() as state:
            stage = state["stages"][stage_id]; request = stage["request"]
            require(stage["status"] not in {"uploading", "upload_unknown", "submitting", "submit_unknown"},
                    "Reconcile uncertain dispatch before importing output")
            require(stage["status"] != "failed", "Failed job cannot supply a completed result without reconciliation")
            require(receipt.get("request_id") == request["request_id"]
                    and receipt.get("library_content_sha256") == request["library_content_sha256"], "Artifact request/library binding mismatch")
            require(receipt.get("status") == "completed" and receipt.get("complete_output") is True
                    and receipt.get("job_name") == JOB_NAME and isinstance(receipt.get("doc_id"), str)
                    and receipt["doc_id"], "Complete named-job output declaration required")
            kind = receipt.get("evidence_kind")
            require(kind in {"fixture", "imported_nodeapi_artifact", "existing_connector_runtime"}, "Explicit scientific evidence kind required")
            require(kind != "fixture" or state["evidence_mode"] == "fixture", "Fixture results cannot enter a development run")
            if stage.get("submit"):
                require(receipt["doc_id"] == stage["submit"]["doc_id"], "Artifact belongs to another job")
            if kind == "existing_connector_runtime":
                monitor = stage.get("last_monitor", {})
                require(stage.get("submit") and not monitor.get("error")
                        and str(monitor.get("status", "")).lower() == "completed",
                        "Connector-recorded completion required; imported JSON alone is insufficient")
            source = Path(csv_path)
            require(source.is_file() and not source.is_symlink(), "Regular downloaded CSV required")
            raw = source.read_bytes(); sha = hashlib.sha256(raw).hexdigest()
            require(sha == receipt.get("artifact_sha256"), "Downloaded bytes changed")
            if stage["status"] == "complete":
                require(stage["output"]["artifact_sha256"] == sha and stage["output"]["receipt_digest"] == digest(receipt),
                        "Completed stage cannot be replaced with different output")
                return deepcopy(stage["batch"])
            destination = self.directory / "artifacts" / (stage_id + "-" + sha + ".csv")
            if destination.exists():
                require(file_sha(destination) == sha, "Retained artifact changed")
            else:
                with destination.open("xb") as f:
                    os.fchmod(f.fileno(), 0o600); f.write(raw)
            stage["output"] = {"artifact_sha256": sha, "csv_path": str(destination),
                               "receipt": deepcopy(receipt), "receipt_digest": digest(receipt), "evidence_kind": kind}
            stage["status"] = "processing"; self._save(state)
            cache = {} if stage_id == "common" else deepcopy(state["stages"]["common"]["batch"]["cache"])
            try:
                self._implementation()
                batch = self._assessor().assess_csv(destination, cache)
                require(batch.get("artifact_sha256") == sha, "Assessment refers to different input bytes")
                require(state["evidence_mode"] == "fixture" or batch.get("scorer_kind") == self._scorer_kind(),
                        "Development needs fixed-scorer evidence")
            except Exception:
                stage["status"] = "processing_failed"
                raise
            stage["batch"] = batch; stage["status"] = "complete"
            return deepcopy(batch)

    def recover(self, stage_id):
        """Reprocess the retained local snapshot; never upload, submit or poll science."""
        with self._state() as state:
            stage = state["stages"][stage_id]
            require(stage["status"] in {"processing", "processing_failed", "complete"} and stage.get("output"),
                    "No retained output for local recovery")
            output = deepcopy(stage["output"])
        return self.ingest(stage_id, output["csv_path"], output["receipt"])

    def _packet(self, state, arm):
        require(arm in self.protocol["arms"], "Unknown comparison arm")
        common = state["stages"]["common"]
        require(common["status"] == "complete", "Common observations are not ready")
        require(not common["batch"].get("evaluation_blockers"), "Common assessment has unresolved evaluation blockers")
        require(not common["batch"]["qualified_candidate_ids"], "Task already succeeded; no remaining decision")
        remaining = [x["id"] for x in self.protocol["libraries"] if x["id"] != self.protocol["initial_library_id"]]
        require(len(remaining) >= 2, "No meaningful remaining library choice")
        packet = {"schema_version": 1, "protocol_digest": state["protocol_digest"],
                  "task_type": self.protocol["task_type"], "reference": self.protocol["reference"],
                  "rules": self.protocol["rules"], "baseline": self.protocol["assessor"]["baseline"],
                  "scientific_guidance": self.protocol["scientific_guidance"],
                  "eligible_library_ids": remaining, "libraries": self.protocol["libraries"],
                  "resource_allowances": self.protocol["resources"],
                  "context_limits": self.protocol.get("context_limits", {"maximum_assignment_chars": 24000}),
                  "specialist_definition": self.protocol.get("specialist_definition"),
                  "edit_attribution": "unknown unless supported by separate checked evidence; do not invent isolated edits",
                  "advice_fields": sorted(ANSWER_FIELDS), "common_output_sha256": common["output"]["artifact_sha256"]}
        packet.update(build_context(common["batch"]))
        if self.protocol["arm_treatments"][arm]["provided_coverage_helper"]:
            packet["coverage_helper"] = plan(self.protocol["lookup_index"], [self.protocol["initial_library_id"]])
        packet["input_digest"] = digest(packet)
        return deepcopy(packet)

    def decision_context(self, arm):
        with self._state() as state:
            return self._packet(state, arm)

    def _decision(self, state, arm, answer, evidence_kind, runtime, usage):
        require(arm not in state["decisions"], "A decision has already been recorded")
        packet = self._packet(state, arm)
        require(isinstance(answer, dict) and set(answer) == ANSWER_FIELDS, "Exact advisory JSON contract required")
        digest(answer)
        require(type(answer["schema_version"]) is int and answer["schema_version"] == 1
                and answer["input_digest"] == packet["input_digest"]
                and answer["scientific_claim"] == "hypothesis_only", "Advice identity/claim mismatch")
        require(isinstance(answer["disposition"], str)
                and answer["disposition"] in {"recommend", "need_information", "no_action"}, "Unknown disposition")
        require(all(isinstance(answer[k], str) for k in TEXT_FIELDS), "Explanation fields must be text")
        for field in LIST_FIELDS:
            value = answer[field]
            require(isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)
                    and len(value) == len(set(value)), "Invalid advisory list: " + field)
        ids = {r["candidate_id"] for r in common_summaries(packet) if r.get("status") == "completed"}
        require((set(answer["supporting_ids"]) | set(answer["counterexample_ids"])) <= ids, "Unknown evidence citation")
        require(answer["limitations"], "Limitations must be explicit")
        if answer["disposition"] == "recommend":
            require(answer["library_id"] in packet["eligible_library_ids"]
                    and all(answer[k].strip() for k in TEXT_FIELDS)
                    and (answer["supporting_ids"] or answer["counterexample_ids"])
                    and not answer["information_requests"], "Complete evidence-linked eligible recommendation required")
        else:
            require(answer["library_id"] is None and answer["hypothesis"].strip(), "Abstention cannot select a library")
            require(answer["disposition"] != "need_information" or answer["information_requests"], "Name missing information")
        native = evidence_kind == "native_agent_runtime"
        fixture = evidence_kind == "fixture" and state["evidence_mode"] == "fixture"
        route = (not self.protocol["arm_treatments"][arm]["specialist"]
                 or (native and runtime.get("specialist_invoked") is True
                     and runtime.get("specialist_name") == self.protocol["routing_policy"]["specialist_name"])
                 or (fixture and runtime.get("specialist_invoked") is True))
        status = "validated_advice" if route else "routing_failure"
        state["decisions"][arm] = {"status": status, "advice": deepcopy(answer), "evidence_kind": evidence_kind,
                                    "runtime": deepcopy(runtime), "usage": deepcopy(usage), "packet_digest": packet["input_digest"]}
        if route and answer["disposition"] == "recommend":
            self._add_stage(state, arm, answer["library_id"])
        return deepcopy(state["decisions"][arm])

    def import_decision(self, arm, answer, *, usage=None):
        with self._state() as state:
            return self._decision(state, arm, answer, "imported_policy_decision", {}, usage or {"total_parent_child_usage": "unknown"})

    def invoke(self, arm, driver):
        """Instrumented driver only. Imported advice cannot claim this route."""
        from pilot.native import NativeDecisionDriver, FixtureDecisionDriver
        require(isinstance(driver, (NativeDecisionDriver, FixtureDecisionDriver)), "Instrumented native/fixture driver required")
        with self._state() as state:
            self._implementation()
            require(not isinstance(driver, FixtureDecisionDriver) or state["evidence_mode"] == "fixture", "Fixture driver forbidden in development runs")
            require(arm not in state["decisions"], "Decision already recorded")
            if isinstance(driver, NativeDecisionDriver) and state["evidence_mode"] != "fixture":
                require(self.protocol.get("runtime_identity") and driver.runtime_identity == self.protocol["runtime_identity"],
                        "Register matching nonsecret model/provider identity when freezing, before outcomes")
            packet = self._packet(state, arm)
            attempt = {"arm": arm, "packet_digest": packet["input_digest"], "status": "in_progress", "usage": "unknown"}
            require(not any(x["arm"] == arm and x["status"] == "in_progress" for x in state["reasoning_attempts"]), "Existing reasoning call unresolved")
            state["reasoning_attempts"].append(attempt); self._save(state)
            try:
                result = driver.choose(arm, packet)
                decision = self._decision(state, arm, result["advice"], result["evidence_kind"], result["runtime"], result["usage"])
            except Exception:
                attempt["status"] = "failed_or_unknown"
                raise
            attempt["status"] = "completed"; attempt["usage"] = result["usage"]
            return decision

    def report(self):
        with self._state() as state:
            common = state["stages"]["common"]
            no_choice = (common.get("batch") is not None and not common["batch"].get("evaluation_blockers")
                         and bool(common["batch"]["qualified_candidate_ids"]))
            common_effort = None if common["batch"] is None else counters(common["batch"])
            arms = {}
            for arm in self.protocol["arms"]:
                decision = state["decisions"].get(arm); stage = state["stages"].get(arm)
                batch = stage.get("batch") if stage else None
                arms[arm] = {"status": "not_exercised_common_success" if no_choice else (stage["status"] if stage else (decision["status"] if decision else "not_exercised")),
                             "decision_evidence_kind": decision["evidence_kind"] if decision else None,
                             "initial_effort_attributed": common_effort,
                             "followup_effort": counters(batch) if batch else None,
                             "evaluation_blockers": batch.get("evaluation_blockers", []) if batch else [],
                             "qualified_candidate_ids": batch["qualified_candidate_ids"] if batch else [],
                             "reasoning_usage": decision["usage"] if decision else "unknown"}
            actual = {name: {"status": s["status"], "execution_source": s.get("output", {}).get("evidence_kind") if s.get("output") else None,
                             "evaluation_blockers": s["batch"].get("evaluation_blockers", []) if s.get("batch") else [],
                             "effort": counters(s["batch"]) if s.get("batch") else None} for name, s in state["stages"].items()}
            exercised = (state["evidence_mode"] == "development" and not no_choice and all(state["decisions"].get(a, {}).get("evidence_kind") == "native_agent_runtime"
                         and state["decisions"][a]["status"] == "validated_advice" for a in self.protocol["arms"]))
            verified_science = (common.get("output") is not None
                                and common["output"]["evidence_kind"] == "existing_connector_runtime"
                                and isinstance(common.get("batch"), dict)
                                and not common["batch"].get("evaluation_blockers")
                                and common["batch"].get("scorer_kind") == self._scorer_kind())
            complete_outcomes = all(
                (state["decisions"].get(a, {}).get("advice", {}).get("disposition") in {"need_information", "no_action"})
                or (a in state["stages"] and state["stages"][a]["status"] == "complete"
                    and state["stages"][a]["output"]["evidence_kind"] == "existing_connector_runtime"
                    and not state["stages"][a]["batch"].get("evaluation_blockers")
                    and state["stages"][a]["batch"].get("scorer_kind") == self._scorer_kind())
                for a in self.protocol["arms"])
            return {"protocol_digest": state["protocol_digest"], "scope": self.protocol["scope"],
                    "evidence_mode": state["evidence_mode"], "no_remaining_decision": no_choice,
                    "native_decision_comparison_exercised": exercised,
                    "complete_scientific_comparison": exercised and verified_science and complete_outcomes,
                    "comparison_controls": "model/provider checked; inference-setting/fresh-session equivalence and total compute remain unverified",
                    "qualified_causal_comparison": False,
                    "actual_scientific_stages_once_only": actual, "arms": arms,
                    "reference_qualification_effort": deepcopy(self.protocol.get("reference_qualification_effort")),
                    "reasoning_attempts": deepcopy(state["reasoning_attempts"]),
                    "internal_compute_and_credits": "unknown unless native receipts provide measured values",
                    "scientific_interpretation": "Descriptive development evidence; no experimental validation, holdout or general superiority established"}


def common_summaries(packet):
    return packet["observations"]["summaries"]


def counters(batch):
    return {k: batch.get(k) for k in ("raw_rows", "invalid_rows", "unresolved_rows", "duplicate_rows", "new_unique_candidate_evaluations", "baseline_model_evaluations", "reported_property_prediction_rows")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init"); init.add_argument("--run-dir", type=Path, required=True)
    init.add_argument("--task", choices=("drd2_reference", "lipophilicity"), required=True)
    init.add_argument("--generation-parameters", type=Path, required=True,
                      help="Explicit nonempty global_models/custom_models selection with bounds")
    init.add_argument("--baseline-record", type=Path, help="Verified property-reference artifact record for the Lipophilicity task")
    init.add_argument("--qualification", type=Path, help="Native reference qualification receipts for the Lipophilicity task")
    init.add_argument("--runtime-identity", type=Path, help="Nonsecret model/provider JSON, frozen before observations")
    for name in ("next", "report", "context", "ingest", "decide", "recover"):
        p = sub.add_parser(name); p.add_argument("--run-dir", type=Path, required=True)
        if name in {"context", "decide"}: p.add_argument("--arm", required=True)
        if name == "ingest":
            p.add_argument("--stage", required=True); p.add_argument("--csv", type=Path, required=True); p.add_argument("--receipt", type=Path, required=True)
        if name == "decide": p.add_argument("--advice", type=Path, required=True)
        if name == "recover": p.add_argument("--stage", required=True)
    args = parser.parse_args()
    if args.action == "init":
        from pilot.protocol import build_protocol
        params = json.loads(args.generation_parameters.read_text()) if args.generation_parameters else None
        identity = json.loads(args.runtime_identity.read_text()) if args.runtime_identity else None
        if args.task == "lipophilicity":
            require(args.baseline_record and args.qualification, "Lipophilicity requires the verified baseline record and qualification receipts")
            from pilot.property_protocol import build_property_protocol
            protocol = build_property_protocol(generation_parameters=params,
                                               baseline_record_path=args.baseline_record,
                                               qualification_path=args.qualification)
        else:
            protocol = build_protocol(generation_parameters=params)
        run = PilotRun.create(protocol, args.run_dir, runtime_identity=identity)
        result = run.next()
    else:
        run = PilotRun(args.run_dir)
        if args.action == "next": result = run.next()
        elif args.action == "report": result = run.report()
        elif args.action == "context": result = run.decision_context(args.arm)
        elif args.action == "ingest": result = run.ingest(args.stage, args.csv, json.loads(args.receipt.read_text()))
        elif args.action == "recover": result = run.recover(args.stage)
        else: result = run.import_decision(args.arm, parse_answer(args.advice.read_text()))
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
