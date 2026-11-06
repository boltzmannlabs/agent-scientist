"""Task-scoped admission around the EXISTING SDK scientific dispatcher.

The SDK's middleware framework skips callbacks that raise before ``next_call``.
This gate therefore returns an explicit blocked result for every local failure.
It does not install middleware globally, resolve keys, send HTTP, retry scientific
work or interpret molecular measurements. Register only in the assignment's
isolated host runtime. Normal upstream authentication/approval still applies.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile

from pilot.bridge import JOB_NAME, NodeAPIAdapter, _request
from workflow.session import native_status


CONNECTOR_TOOLS = {"boltzmann_upload", "boltzmann_submit", "boltzmann_status", "boltzmann_download"}
APPROVED_WARNING = "SMILES: smiles semantics are not verified by the generic CSV parser."


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _same(left, right):
    # Python treats bool/int as equal; scientific payload identity must not.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def _links(value, download_field=False):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _links(item, download_field or key in {"download_link", "download_url", "download_links", "download_urls"})
    elif isinstance(value, list):
        for item in value:
            yield from _links(item, download_field)
    elif download_field and isinstance(value, str) and value.startswith("https://"):
        yield value


def _name(request):
    return "smallmol-pilot-" + hashlib.sha256(request["request_id"].encode()).hexdigest()[:32]


class AdmissionGate:
    def __init__(self, session, *, warning_validator=None):
        self.session = session
        self.warning_validator = warning_validator or self._canonical_validation

    @staticmethod
    def _canonical_validation(stage, args):
        # Reuse canonical validators rather than treating allow_partial_validation
        # as approval of every future warning. This performs no HTTP/submission.
        if stage == "upload":
            from plugins.boltzmann.contracts import ContractStore
            from plugins.boltzmann.file_validation import validate_file
            rule = ContractStore().file_rule(JOB_NAME, "library_path")
            return validate_file(Path(args["local_path"]), rule, args["experiment_data"]).as_dict()
        from plugins.boltzmann.preflight import preflight_submission
        return preflight_submission(JOB_NAME, args["experiment_data"]).as_dict()

    def _check_warning_scope(self, approved, stage, args):
        if not approved:
            return
        report = self.warning_validator(stage, deepcopy(args))
        _require(isinstance(report, dict) and isinstance(report.get("warnings"), list)
                 and isinstance(report.get("errors"), list), "Current canonical validation required")
        _require(not report["errors"] and set(report["warnings"]) <= {APPROVED_WARNING},
                 "Validation contains errors or a warning outside the user's concrete approval")

    def _library(self, action):
        return next(lib for lib in self.session.spec["libraries"] if lib["id"] == action["library_id"])

    def _approved(self, library, arguments):
        requested = arguments.get("allow_partial_validation", False)
        _require(type(requested) is bool, "Partial-validation flag must be boolean")
        approved = library.get("approved_generic_smiles_warning", False)
        _require(type(approved) is bool, "Host warning approval must be boolean")
        _require(not requested or approved, "This library has no host-approved SMILES warning")
        return approved

    def _adapter(self, next_call, tracker, *, approved=False):
        def call(name, args):
            _require(not tracker["called"], "Downstream call is single-use")
            tracker["called"] = True
            raw = next_call(args)
            tracker["raw"] = raw
            return raw
        return NodeAPIAdapter(call, allow_partial_validation=approved)

    def _save(self, action, kind, value, state):
        try:
            return self.session.receipt(action["action_key"], kind, value, state)
        except Exception:
            self._emergency(action, kind, value)
            raise

    def _emergency(self, action, kind, value):
        # Best-effort private receipt retention if the DB fails AFTER dispatch.
        # Durable upload/submission intent already exists; never retry the call.
        try:
            folder = Path(self.session.spec["artifact_directory"])
            fd, name = tempfile.mkstemp(prefix="receipt-recovery-", suffix=".json", dir=folder)
            with os.fdopen(fd, "w") as stream:
                os.fchmod(stream.fileno(), 0o600)
                json.dump({"assignment_id": self.session.assignment_id, "action_key": action["action_key"],
                           "kind": kind, "value": value}, stream, sort_keys=True, allow_nan=False)
                stream.flush(); os.fsync(stream.fileno())
            return name
        except Exception:
            return None

    def _upload(self, args, next_call, tracker):
        _require(set(args) <= {"job_name", "input_field", "local_path", "experiment_data", "allow_partial_validation"},
                 "Unexpected upload fields")
        _require(args.get("job_name") == JOB_NAME and args.get("input_field") == "library_path",
                 "Only the assigned CReM library input may be uploaded")
        path = Path(args["local_path"]).expanduser().absolute()
        libraries = [lib for lib in self.session.spec["libraries"]
                     if Path(lib["csv_path"]).expanduser().absolute() == path]
        _require(len(libraries) == 1, "Uploaded library is not registered for this assignment")
        library = libraries[0]
        approved = self._approved(library, args)
        payload = args.get("experiment_data")
        _require(isinstance(payload, dict), "Scientific upload payload required")
        parents = [c for c in self.session.report()["candidates"] if c["representation"] == payload.get("ref_mol")]
        _require(len(parents) == 1, "Generation parent must match one exact registered representation")
        expected = {**self.session.spec["objective"]["generation_parameters"], "ref_mol": parents[0]["representation"]}
        _require(_same(payload, expected), "Original property objective was changed")
        self._check_warning_scope(approved, "upload", args)
        action = self.session.reserve(parents[0]["id"], library["id"])
        tracker.update(action=action, phase="upload")
        self._save(action, "upload_intent", {"operation": "upload", "state": "uploading"}, "uploading")
        result = self._adapter(next_call, tracker, approved=approved).upload(action["request"])
        uploaded = result.get("status") == "uploaded" and not result.get("error")
        state = "uploaded" if uploaded else ("upload_blocked" if result.get("status") in {
            "approval_required", "not_started", "blocked"} else "upload_unknown")
        self._save(action, "upload", result, state)
        shown = deepcopy(result)
        shown["workflow_action_key"] = action["action_key"]
        if uploaded:
            shown["workflow_next_submit"] = {"job_name": JOB_NAME,
                "experiment_data": {**expected, "library_path": result["s3_path"]},
                "experiment_name": _name(action["request"]), "allow_partial_validation": approved}
        return shown

    def _submit(self, args, next_call, tracker):
        _require(set(args) <= {"job_name", "experiment_data", "experiment_name", "allow_partial_validation"},
                 "Unexpected submit fields")
        _require(args.get("job_name") == JOB_NAME, "Scientific job is outside this assignment")
        matches = []
        for action in self.session.attempts():
            upload = action.get("upload", {})
            if upload.get("status") != "uploaded" or upload.get("error"):
                continue
            expected, _ = _request(action["request"], verify_file=False)
            expected["library_path"] = upload.get("s3_path")
            if _same(args.get("experiment_data"), expected):
                matches.append(action)
        _require(len(matches) == 1, "Submit requires one matching original successful upload")
        action = matches[0]
        tracker.update(action=action, phase="submit")
        _require(action["state"] == "uploaded", "This action was already submitted or has an unresolved outcome")
        _require(args.get("experiment_name", _name(action["request"])) == _name(action["request"]),
                 "Use the host-generated experiment name from the upload result")
        approved = self._approved(self._library(action), args)
        _request(action["request"], verify_file=True)
        self._check_warning_scope(approved, "submit", args)
        self.session.assert_submission_allowed(action["action_key"])
        self._save(action, "submit_intent", {"operation": "submit", "state": "submitting"}, "submitting")
        result = self._adapter(next_call, tracker, approved=approved).submit(action["request"], action["upload"])
        accepted = result.get("status") == "accepted" and not result.get("error")
        state = "accepted" if accepted else "submit_unknown"
        self._save(action, "submit", result, state)
        self.session.record_action(action, "accepted" if accepted else "unknown", result.get("doc_id"))
        return {**result, "workflow_action_key": action["action_key"]}

    def _status(self, args, next_call, tracker):
        _require(set(args) == {"job_name", "doc_id"} and args["job_name"] == JOB_NAME,
                 "Status requires the assigned job and original job ID")
        matches = [action for action in self.session.attempts() if action.get("submit", {}).get("doc_id") == args["doc_id"]]
        _require(len(matches) == 1 and bool(args["doc_id"]), "Job ID does not belong to this assignment")
        action = matches[0]
        tracker.update(action=action, phase="status")
        result = self._adapter(next_call, tracker).status(action["request"], action["submit"])
        _require(result.get("doc_id", args["doc_id"]) == args["doc_id"]
                 and result.get("job_name", JOB_NAME) == JOB_NAME, "Returned status has a different job identity")
        observed = native_status(result)
        terminal = action["state"] in {"failed", "complete"}
        state = action["state"] if terminal or observed == "unknown" else {
            "completed": "results_ready", "pending": "accepted", "failed": "failed"}[observed]
        self._save(action, "monitor", result, state)
        if observed == "failed" and not terminal:
            self.session.record_action(action, "failed", args["doc_id"])
        shown = {**result, "workflow_action_key": action["action_key"], "workflow_state": state}
        if observed == "completed" and not terminal:
            shown["workflow_download_folder"] = str(Path(self.session.spec["artifact_directory"]) / action["action_key"])
        return shown

    def _download(self, args, next_call, tracker):
        _require(set(args) == {"download_url", "output_folder"}, "Explicit download reference and private output folder required")
        matches = [action for action in self.session.attempts()
                   if action["state"] == "results_ready"
                   and native_status(action.get("monitor", {})) == "completed"
                   and args["download_url"] in set(_links(action.get("monitor", {})))]
        _require(len(matches) == 1, "Download reference is not from an owned completed job")
        action = matches[0]
        tracker.update(action=action, phase="download")
        folder = Path(args["output_folder"]).expanduser()
        allowed = Path(self.session.spec["artifact_directory"]) / action["action_key"]
        _require(folder.is_absolute() and folder.resolve().is_relative_to(allowed.resolve()),
                 "Download folder must be the private per-action folder returned by status")
        _require(not any(path.is_symlink() for path in (folder, *folder.parents)), "Symlink download paths are not admitted")
        result = self._adapter(next_call, tracker).download(args["download_url"], folder)
        paths = result.get("output_paths", [])
        _require(isinstance(paths, list), "Download returned malformed output paths")
        manifest = []
        if not result.get("error") and not result.get("errors"):
            for name in paths:
                path = Path(name)
                _require(not path.is_symlink() and path.is_file() and path.resolve().is_relative_to(folder.resolve()),
                         "Downloaded output is outside its original private folder")
                manifest.append({"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        state = "downloaded" if manifest else "results_ready"
        self._save(action, "download", {**result, "_workflow_manifest": manifest}, state)
        return {**result, "workflow_action_key": action["action_key"], "workflow_state": state,
                "workflow_note": "Downloaded bytes require host molecular assessment; job success is not scientific objective success"}

    def __call__(self, **kwargs):
        name, args, next_call = kwargs.get("tool_name"), kwargs.get("args"), kwargs.get("next_call")
        if name not in CONNECTOR_TOOLS and name != "leadopt_campaign":
            return next_call(args)
        tracker = {"called": False, "raw": None, "action": None, "phase": name}
        try:
            _require(isinstance(args, dict) and callable(next_call), "Valid existing host dispatcher required")
            if name == "leadopt_campaign":
                _require(set(args) <= {"operation", "campaign_id", "payload"}
                         and args.get("operation") in {"progress", "report", "status"}
                         and args.get("campaign_id") == self.session.campaign_id
                         and args.get("payload", {}) == {}, "Only current-campaign read operations are available to the specialist")
                tracker["called"] = True
                return next_call(args)
            return {"boltzmann_upload": self._upload, "boltzmann_submit": self._submit,
                    "boltzmann_status": self._status, "boltzmann_download": self._download}[name](args, next_call, tracker)
        except Exception:
            action, called, phase = tracker["action"], tracker["called"], tracker["phase"]
            if action is not None and called:
                evidence = {"error": "Connector or receipt association did not complete; preserve the original attempt",
                            "raw_returned_receipt": tracker["raw"], "downstream_called": True}
                if phase in {"upload", "submit"}:
                    try:
                        self._save(action, "dispatch_error", evidence, "unknown")
                    except Exception:
                        pass
                else:
                    # Observation/artifact transport failure does not determine
                    # or overwrite the existing scientific job's state.
                    self._emergency(action, phase + "_error", evidence)
            return {"error": ("Scientific operation outcome is unresolved; reconcile the original attempt without resubmitting"
                              if called and phase in {"upload", "submit"} else "Task-scoped operation blocked or observation unavailable; no automatic retry"),
                    "status": "unknown" if called and phase in {"upload", "submit"} else "blocked",
                    "stage": "workflow_admission", "safe_to_retry": False,
                    "downstream_called": called,
                    "workflow_action_key": action["action_key"] if action is not None else None}


def install(ctx, session):
    """Register in the owning isolated runtime; callers retain the registration."""
    gate = AdmissionGate(session)
    def middleware(**kwargs):
        result = gate(**kwargs)
        if kwargs.get('tool_name') in CONNECTOR_TOOLS | {'leadopt_campaign'} and isinstance(result, dict):
            return json.dumps(result, allow_nan=False)
        return result
    return ctx.register_middleware("tool_execution", middleware)
