"""Durable investigation integration; reuse leadopt_env, never submit science here.

The extra tables hold operational intent/receipts. Candidate/observation/decision
records remain in the existing environment, in the same private database.
"""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
import math
from pathlib import Path
from pilot.bridge import BINDING, JOB_NAME, _request, require_property_models


def digest(x):
    return hashlib.sha256(
        json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def native_status(receipt):
    status = str(receipt.get("service_status") or receipt.get("status") or "").lower()
    if status in {"success", "completed", "complete", "succeeded"} and not receipt.get(
        "error"
    ):
        return "completed"
    if status in {"pending", "queued", "accepted", "running", "processing"}:
        return "pending"
    if status in {"failed", "failure", "cancelled", "canceled"} and not receipt.get(
        "error"
    ):
        return "failed"
    return "unknown"


class WorkflowSession:
    def __init__(self, store, assignment_id):
        self.store, self.assignment_id = store, assignment_id
        with store._db() as db:
            row = db.execute(
                "SELECT spec FROM smallmol_assignments WHERE id=?", (assignment_id,)
            ).fetchone()
        if row is None:
            raise KeyError("Unknown assignment")
        self.spec = json.loads(row[0])
        self.campaign_id = self.spec["campaign_id"]
        if self.report()["task_digest"] != self.spec["task_digest"]:
            raise ValueError("Stored task no longer matches the assignment")

    @classmethod
    def create(cls, store, spec, task):
        spec = deepcopy(spec)
        for key in (
            "assignment_id",
            "campaign_id",
            "reference",
            "objective",
            "assessor",
            "libraries",
            "limits",
            "artifact_directory",
        ):
            if not spec.get(key):
                raise ValueError("Missing assignment field: " + key)
        require_property_models(spec["objective"]["generation_parameters"])
        objective, assessor = spec["objective"], spec["assessor"]
        if any(
            type(objective.get(k)) not in (int, float)
            or not math.isfinite(objective[k])
            for k in (
                "target_min",
                "target_max",
                "qed_min_exclusive",
                "similarity_min_exclusive",
            )
        ):
            raise ValueError("Finite numerical scientific bounds required")
        if any(
            assessor["reference"][k] != spec["reference"][k]
            for k in ("id", "form_id", "representation")
        ):
            raise ValueError("Assessor and assignment reference differ")
        if (
            objective["target_min"] != assessor["target_min"]
            or objective["target_max"] != assessor["target_max"]
            or objective["qed_min_exclusive"] != assessor["baseline"]["qed"]
            or objective["similarity_min_exclusive"] != 0.7
        ):
            raise ValueError("Objective and supported assessor rules differ")
        selection = {
            "global_models": [
                {
                    "name": "Lipophilicity",
                    "min_threshold": objective["target_min"],
                    "max_threshold": objective["target_max"],
                }
            ]
        }
        if objective["generation_parameters"] != selection:
            raise ValueError(
                "This assessor requires the exact matching Lipophilicity objective"
            )
        from pilot.property_assessment import PlatformPropertyAssessor

        PlatformPropertyAssessor(assessor).baseline_check()
        if not spec.get("observation_signatures"):
            raise ValueError("Explicit task evidence signatures required")
        expected_bounds = {
            "lipophilicity": (objective["target_min"], objective["target_max"]),
            "qed": (math.nextafter(objective["qed_min_exclusive"], math.inf), None),
            "lead_similarity": (
                math.nextafter(objective["similarity_min_exclusive"], math.inf),
                None,
            ),
        }
        constraints = task.get("constraints", [])
        if len(constraints) != 3 or {c["endpoint"] for c in constraints} != set(
            expected_bounds
        ):
            raise ValueError(
                "Task must contain exactly the supported scientific constraints"
            )
        for c in constraints:
            if (c.get("minimum"), c.get("maximum")) != expected_bounds[c["endpoint"]]:
                raise ValueError("Task/assessor constraint mismatch")
            if any(
                c.get(k) != v
                for k, v in spec["observation_signatures"][c["endpoint"]].items()
            ):
                raise ValueError("Task and evidence signatures differ")
        for key, minimum in (("max_scientific_submissions", 0), ("max_episodes", 1)):
            if (
                type(spec["limits"].get(key)) is not int
                or spec["limits"][key] < minimum
            ):
                raise ValueError("Explicit submission/episode allowance required")
        if datetime.fromisoformat(spec["limits"]["deadline_utc"]).tzinfo is None:
            raise ValueError("Timezone-aware deadline required")
        if task.get("allowed_jobs") != [JOB_NAME]:
            raise ValueError("This workflow supports CReM only")
        reference = next(
            (
                c
                for c in task.get("starting_candidates", [])
                if c["id"] == spec["reference"]["id"]
            ),
            None,
        )
        if reference is None or any(
            reference[k] != spec["reference"][k]
            for k in ("id", "form_id", "representation")
        ):
            raise ValueError("Original reference mismatch")
        for endpoint, expected in assessor["baseline"].items():
            signature = spec["observation_signatures"][endpoint]
            evidence = [
                o
                for o in task.get("initial_observations", [])
                if o.get("candidate_id") == reference["id"]
                and o.get("form_id") == reference["form_id"]
                and o.get("endpoint") == endpoint
                and o.get("status") == "completed"
                and o.get("qualifier") == "="
                and all(o.get(k) == v for k, v in signature.items())
            ]
            if not evidence or any(
                type(o.get("value")) not in (int, float) or o["value"] != expected
                for o in evidence
            ):
                raise ValueError(
                    "Task baseline evidence differs from the frozen assessor"
                )
        publication = Path(__file__).resolve().parents[2]
        artifacts = Path(spec["artifact_directory"]).resolve()
        if artifacts.is_relative_to(publication) or store.path.is_relative_to(
            publication
        ):
            raise ValueError("Keep private artifacts/DB outside publication checkout")
        spec["artifact_directory"] = str(artifacts)
        seen = set()
        library_ids = set()
        for lib in spec["libraries"]:
            p = Path(lib["csv_path"])
            if (
                p.is_symlink()
                or not p.is_file()
                or hashlib.sha256(p.read_bytes()).hexdigest() != lib["content_sha256"]
            ):
                raise ValueError("Library identity changed")
            if lib["content_sha256"] in seen or lib["id"] in library_ids:
                raise ValueError("Aliased libraries")
            seen.add(lib["content_sha256"])
            library_ids.add(lib["id"])
        spec["task_digest"] = digest(task)
        with store._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS smallmol_assignments(id TEXT PRIMARY KEY,campaign TEXT UNIQUE NOT NULL,spec TEXT NOT NULL,episodes INTEGER NOT NULL DEFAULT 0,blockers TEXT NOT NULL DEFAULT '[]')"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS smallmol_attempts(assignment TEXT NOT NULL,action_key TEXT NOT NULL,data TEXT NOT NULL,PRIMARY KEY(assignment,action_key))"
            )
            encoded = json.dumps(spec, sort_keys=True, allow_nan=False)
            old = db.execute(
                "SELECT spec FROM smallmol_assignments WHERE id=?",
                (spec["assignment_id"],),
            ).fetchone()
            if old and old[0] != encoded:
                raise ValueError("Immutable assignment cannot be replaced")
            other = db.execute(
                "SELECT id FROM smallmol_assignments WHERE campaign=?",
                (spec["campaign_id"],),
            ).fetchone()
            if other and other[0] != spec["assignment_id"]:
                raise ValueError("Campaign already belongs to another assignment")
            db.execute(
                "INSERT OR IGNORE INTO smallmol_assignments(id,campaign,spec) VALUES(?,?,?)",
                (spec["assignment_id"], spec["campaign_id"], encoded),
            )
        artifacts.mkdir(parents=True, exist_ok=True, mode=0o700)
        report = store.dispatch("create", spec["campaign_id"], {"task": task})
        if report["task_digest"] != spec["task_digest"]:
            raise ValueError("Environment task digest mismatch")
        os.chmod(store.path, 0o600)
        return cls(store, spec["assignment_id"])

    def report(self):
        return self.store.dispatch("report", self.campaign_id)

    def attempts(self):
        with self.store._db() as db:
            return [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT data FROM smallmol_attempts WHERE assignment=? ORDER BY rowid",
                    (self.assignment_id,),
                )
            ]

    def receipt(self, key, kind, value, state):
        with self.store._db() as db:
            row = db.execute(
                "SELECT data FROM smallmol_attempts WHERE assignment=? AND action_key=?",
                (self.assignment_id, key),
            ).fetchone()
            if row is None:
                raise KeyError("Unknown action")
            action = json.loads(row[0])
            transitions = {
                "upload_intent": ({"reserved"}, {"uploading"}),
                "upload": (
                    {"uploading"},
                    {"uploaded", "upload_blocked", "upload_unknown"},
                ),
                "submit_intent": ({"uploaded"}, {"submitting"}),
                "submit": ({"submitting"}, {"accepted", "submit_unknown"}),
                "monitor": (
                    {
                        "accepted",
                        "results_ready",
                        "downloaded",
                        "complete",
                        "failed",
                        "unknown",
                        "submit_unknown",
                    },
                    {
                        "accepted",
                        "results_ready",
                        "downloaded",
                        "complete",
                        "failed",
                        "unknown",
                        "submit_unknown",
                    },
                ),
                "download": ({"results_ready"}, {"downloaded", "results_ready"}),
                "assessment": ({"downloaded"}, {"complete"}),
                "dispatch_error": (
                    {
                        "uploading",
                        "submitting",
                        "accepted",
                        "results_ready",
                        "downloaded",
                        "unknown",
                    },
                    {"unknown"},
                ),
            }
            if (
                kind not in transitions
                or action["state"] not in transitions[kind][0]
                or state not in transitions[kind][1]
            ):
                raise ValueError("Invalid execution receipt/state transition")
            if kind == "submit_intent" and datetime.now(
                timezone.utc
            ) >= datetime.fromisoformat(self.spec["limits"]["deadline_utc"]):
                raise ValueError(
                    "Assignment deadline reached before scientific dispatch"
                )
            if kind in {"upload", "submit", "monitor"}:
                _, binding = _request(action["request"], verify_file=False)
                if value.get(BINDING) != binding:
                    raise ValueError("Native receipt/request binding mismatch")
            known_job = action.get("submit", {}).get("doc_id")
            if kind == "monitor" and (
                value.get("doc_id") != known_job or value.get("job_name") != JOB_NAME
            ):
                raise ValueError("Monitor receipt belongs to another job")
            if action["state"] in {"complete", "failed"}:
                state = action["state"]
            action["receipts"].append(
                {"kind": kind, "at": now(), "value": deepcopy(value)}
            )
            action[kind] = deepcopy(value)
            action["state"] = state
            db.execute(
                "UPDATE smallmol_attempts SET data=? WHERE assignment=? AND action_key=?",
                (
                    json.dumps(action, sort_keys=True, allow_nan=False),
                    self.assignment_id,
                    key,
                ),
            )
        return action

    def candidates(self):
        report = self.report()
        result = []
        for c in report["candidates"]:
            obs = [o for o in report["observations"] if o["candidate_id"] == c["id"]]
            values = {}
            conflict = False
            for endpoint in ("lipophilicity", "qed", "lead_similarity"):
                signature = self.spec["observation_signatures"][endpoint]
                distinct = {
                    o["value"]
                    for o in obs
                    if o["endpoint"] == endpoint
                    and o["form_id"] == c["form_id"]
                    and all(o.get(k) == v for k, v in signature.items())
                    and o["status"] == "completed"
                    and o.get("qualifier") == "="
                    and o.get("value") is not None
                }
                values[endpoint] = next(iter(distinct)) if len(distinct) == 1 else None
                conflict |= len(distinct) > 1
            result.append(
                {
                    "candidate_id": c["id"],
                    "form_id": c["form_id"],
                    "representation": c["representation"],
                    "values": values,
                    "status": "unresolved" if conflict else "completed",
                    "property_prediction_conflict": conflict,
                    "evidence_ids": [o["id"] for o in obs],
                }
            )
        return result

    def search_view(self):
        from workflow.search import build_search_view

        view = build_search_view(
            self.candidates(),
            reference=self.spec["reference"],
            objective=self.spec["objective"],
            libraries=self.spec["libraries"],
            actions=self.attempts(),
        )
        with self.store._db() as db:
            blockers = json.loads(
                db.execute(
                    "SELECT blockers FROM smallmol_assignments WHERE id=?",
                    (self.assignment_id,),
                ).fetchone()[0]
            )
        view["evaluation_blockers"] = blockers
        view["assignment_frozen"] = bool(self.report().get("freezes"))
        if blockers or view["qualified_candidate_ids"] or view["assignment_frozen"]:
            view["eligible_actions"] = []
        if blockers:
            view["qualified_candidate_ids"] = []
            view["baseline"] = {
                "disposition": "need_information",
                "reason": "unresolved_evaluation_blockers",
                "action": None,
            }
        view["evidence_aggregation"] = (
            "Exact form/signature; identical repeats agree computationally, conflicts unresolved. Not independent predictor agreement or the environment default single-observation assessment."
        )
        return view

    def begin_episode(self):
        with self.store._db() as db:
            n = db.execute(
                "SELECT episodes FROM smallmol_assignments WHERE id=?",
                (self.assignment_id,),
            ).fetchone()[0]
            if datetime.now(timezone.utc) >= datetime.fromisoformat(
                self.spec["limits"]["deadline_utc"]
            ):
                raise ValueError("Deadline reached")
            if n >= self.spec["limits"]["max_episodes"]:
                raise ValueError("Episode allowance reached")
            db.execute(
                "UPDATE smallmol_assignments SET episodes=episodes+1 WHERE id=?",
                (self.assignment_id,),
            )
        return n + 1

    def reserve(self, parent_id, library_id):
        existing = next(
            (
                a
                for a in self.attempts()
                if a["parent_id"] == parent_id
                and a["library_id"] == library_id
                and a["state"] == "reserved"
            ),
            None,
        )
        if existing is not None:
            # No upload intent exists in this state. Restore only its local
            # environment check; keep the original identity and allowance slot.
            if datetime.now(timezone.utc) >= datetime.fromisoformat(
                self.spec["limits"]["deadline_utc"]
            ):
                raise ValueError("Deadline reached before recovering unsent work")
            view = self.search_view()
            if (
                view["evaluation_blockers"]
                or view["qualified_candidate_ids"]
                or view["assignment_frozen"]
            ):
                raise ValueError("Assignment is blocked or frozen")
            return self.recover_unsent_check(existing["action_key"])
        choice = next(
            (
                a
                for a in self.search_view()["eligible_actions"]
                if a["parent_candidate_id"] == parent_id
                and a["library_id"] == library_id
            ),
            None,
        )
        if choice is None:
            raise ValueError("Unavailable or repeated parent/library action")
        parent = next(c for c in self.report()["candidates"] if c["id"] == parent_id)
        lib = next(l for l in self.spec["libraries"] if l["id"] == library_id)
        request = {
            "request_id": digest([self.assignment_id, choice["action_key"]]),
            "library_csv_path": lib["csv_path"],
            "library_content_sha256": lib["content_sha256"],
            "reference": deepcopy(parent),
            "generation_parameters": deepcopy(
                self.spec["objective"]["generation_parameters"]
            ),
        }
        _request(request, verify_file=True)
        with self.store._db() as db:
            rows = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT data FROM smallmol_attempts WHERE assignment=?",
                    (self.assignment_id,),
                )
            ]
            if datetime.now(timezone.utc) >= datetime.fromisoformat(
                self.spec["limits"]["deadline_utc"]
            ):
                raise ValueError("Deadline reached")
            if len(rows) >= self.spec["limits"]["max_scientific_submissions"]:
                raise ValueError("Scientific-action reservation allowance reached")
            if any(
                a["state"] not in {"complete", "failed", "upload_blocked"} for a in rows
            ):
                raise ValueError("Resolve existing work first")
            action = {
                "action_key": choice["action_key"],
                "parent_id": parent_id,
                "library_id": library_id,
                "request": request,
                "state": "reserved",
                "created": now(),
                "receipts": [],
            }
            db.execute(
                "INSERT INTO smallmol_attempts VALUES(?,?,?)",
                (
                    self.assignment_id,
                    action["action_key"],
                    json.dumps(action, sort_keys=True),
                ),
            )
        self.recover_unsent_check(action["action_key"])
        return action

    def recover_unsent_check(self, key):
        action = next(a for a in self.attempts() if a["action_key"] == key)
        if action["state"] != "reserved":
            raise ValueError("Only known-unsent reservations can restore a check")
        self.store.dispatch(
            "check",
            self.campaign_id,
            {
                "id": "check-" + key,
                "job": JOB_NAME,
                "candidate_ids": [action["parent_id"]],
                "resource_requests": {"scientific_submission_attempts": 1},
                "question": "Investigate selected parent/library under unchanged original task rules",
            },
        )
        return action

    def assert_submission_allowed(self, key):
        view = self.search_view()
        if (
            view["evaluation_blockers"]
            or view["qualified_candidate_ids"]
            or view["assignment_frozen"]
        ):
            raise ValueError(
                "Assignment is solved or blocked; no further science is admitted"
            )
        with self.store._db() as db:
            if datetime.now(timezone.utc) >= datetime.fromisoformat(
                self.spec["limits"]["deadline_utc"]
            ):
                raise ValueError("Assignment deadline reached before submission")
            row = db.execute(
                "SELECT data FROM smallmol_attempts WHERE assignment=? AND action_key=?",
                (self.assignment_id, key),
            ).fetchone()
            if row is None or json.loads(row[0])["state"] != "uploaded":
                raise ValueError("Original uploaded action required")

    def record_action(self, action, status, job_id=None):
        payload = {
            "id": "action-" + digest([action["action_key"], status, job_id]),
            "attempt_id": action["action_key"],
            "job": JOB_NAME,
            "candidate_ids": [action["parent_id"]],
            "status": status,
            "check_id": "check-" + action["action_key"],
            "source": "Actual host connector receipt retained privately; candidate IDs are generation inputs",
        }
        if job_id:
            payload["job_id"] = job_id
        result = self.store.dispatch("action", self.campaign_id, payload)
        self.reconcile_usage()
        return result

    def reconcile_usage(self):
        """Idempotent accounting from retained dispatch evidence, not model estimates."""
        for action in self.attempts():
            if action.get("shared_prior"):
                continue
            intended = any(r["kind"] == "submit_intent" for r in action["receipts"])
            returned = bool(action.get("submit"))
            called_unknown = (
                action.get("dispatch_error", {}).get("downstream_called") is True
            )
            if intended and (returned or called_unknown):
                self.store.dispatch(
                    "usage",
                    self.campaign_id,
                    {
                        "id": "submission-" + action["action_key"],
                        "unit": "scientific_submission_attempts",
                        "amount": 1,
                        "category": "observed",
                        "scope": "campaign",
                        "attempt_id": action["action_key"],
                        "source": "One normal owning-connector dispatch attempt; acceptance and backend oracle work are separate",
                    },
                )

    def import_shared_prior(self, original_stage):
        """Bind an already completed common job; count it once, never resubmit it."""
        from workflow.search import action_identity

        request = deepcopy(original_stage["request"])
        _, binding = _request(request, verify_file=False)
        submitted, monitored = original_stage["submit"], original_stage["last_monitor"]
        if (
            submitted.get(BINDING) != binding
            or monitored.get(BINDING) != binding
            or not submitted.get("doc_id")
            or monitored.get("doc_id") != submitted["doc_id"]
            or native_status(monitored) != "completed"
            or original_stage.get("status") != "complete"
        ):
            raise ValueError("Original completed common-job receipts are required")
        if (
            request["generation_parameters"]
            != self.spec["objective"]["generation_parameters"]
        ):
            raise ValueError("Shared prior used another objective")
        parent = request["reference"]
        if any(
            parent[k] != self.spec["reference"][k]
            for k in ("id", "form_id", "representation")
        ):
            raise ValueError("Shared prior has another original reference")
        library = next(
            (
                l
                for l in self.spec["libraries"]
                if l["content_sha256"] == request["library_content_sha256"]
            ),
            None,
        )
        if library is None:
            raise ValueError("Shared prior library is not admitted")
        key = action_identity(
            parent,
            library,
            self.spec["objective"],
            original_reference=self.spec["reference"],
        )
        action = {
            "action_key": key,
            "parent_id": parent["id"],
            "library_id": library["id"],
            "request": request,
            "state": "complete",
            "created": now(),
            "shared_prior": True,
            "submit": deepcopy(submitted),
            "monitor": deepcopy(monitored),
            "assessment": {
                k: original_stage["batch"][k]
                for k in ("artifact_sha256", "raw_rows", "qualified_candidate_ids")
            },
            "receipts": [
                {
                    "kind": "imported_common_job",
                    "value": {
                        "original_stage_digest": digest(original_stage),
                        "job_id": submitted["doc_id"],
                    },
                }
            ],
        }
        with self.store._db() as db:
            old = db.execute(
                "SELECT data FROM smallmol_attempts WHERE assignment=? AND action_key=?",
                (self.assignment_id, key),
            ).fetchone()
            if old and not json.loads(old[0]).get("shared_prior"):
                raise ValueError("Cannot replace this assignment's own execution")
            if not old:
                if db.execute(
                    "SELECT 1 FROM smallmol_attempts WHERE assignment=?",
                    (self.assignment_id,),
                ).fetchone():
                    raise ValueError(
                        "Register common prior before new scientific actions"
                    )
                db.execute(
                    "INSERT INTO smallmol_attempts VALUES(?,?,?)",
                    (self.assignment_id, key, json.dumps(action, sort_keys=True)),
                )
        self.store.dispatch(
            "usage",
            self.campaign_id,
            {
                "id": "shared-common-" + key,
                "unit": "scientific_submission_attempts",
                "amount": 1,
                "category": "observed",
                "scope": "campaign",
                "source": "One pre-existing common job attributed equally; not a new submission",
                "attempt_id": key,
            },
        )
        self.store.dispatch(
            "usage",
            self.campaign_id,
            {
                "id": "shared-common-rows-" + key,
                "unit": "returned_rows",
                "amount": action["assessment"]["raw_rows"],
                "category": "observed",
                "scope": "campaign",
                "attempt_id": key,
                "source": "Pre-existing shared common CSV rows, counted once; not internal oracle calls",
            },
        )
        return action

    def finish(self, candidate_ids, reason):
        if any(
            a["state"] not in {"complete", "failed", "upload_blocked"}
            for a in self.attempts()
        ):
            raise ValueError(
                "Outstanding work must settle or be explicitly reconciled before terminal freezing"
            )
        view = self.search_view()
        if not reason or set(candidate_ids) - set(view["qualified_candidate_ids"]):
            raise ValueError(
                "Final selection must contain qualified candidates with a stopping reason"
            )
        payload = {
            "id": "final-" + digest([self.assignment_id, candidate_ids, reason]),
            "candidate_ids": candidate_ids,
            "rationale": "Host-checked selection; empty selection does not establish task success",
            "stopping_reason": reason,
        }
        return self.store.dispatch("freeze", self.campaign_id, payload)

    def complete_download(self, key):
        """Recoverable local processing of an original downloaded job artifact."""
        action = next(a for a in self.attempts() if a["action_key"] == key)
        if action["state"] == "complete":
            if not action.get("shared_prior"):
                self._record_returned_rows(key, action["assessment"])
            return action["assessment"]
        if (
            action["state"] != "downloaded"
            or native_status(action.get("monitor", {})) != "completed"
        ):
            raise ValueError("Original completed job and downloaded artifact required")
        manifest = action.get("download", {}).get("_workflow_manifest", [])
        files = [f for f in manifest if Path(f["path"]).suffix.lower() == ".csv"]
        if len(files) != 1:
            raise ValueError(
                "Exactly one identified CReM CSV required; do not guess an output"
            )
        artifact = files[0]
        if (
            hashlib.sha256(Path(artifact["path"]).read_bytes()).hexdigest()
            != artifact["sha256"]
        ):
            raise ValueError("Downloaded artifact changed")
        job_id = action["submit"]["doc_id"]
        result = self.import_csv(
            artifact["path"],
            {
                "artifact_sha256": artifact["sha256"],
                "source": "Original NodeAPI CReM job " + job_id,
                "action_key": key,
                "generation_parent_id": action["parent_id"],
                "request_digest": digest(action["request"]),
            },
            parent_id=action["parent_id"],
        )
        self.record_action(action, "completed", job_id)
        self._record_returned_rows(key, result)
        self.receipt(key, "assessment", result, "complete")
        return result

    def _record_returned_rows(self, key, result):
        self.store.dispatch(
            "usage",
            self.campaign_id,
            {
                "id": "rows-" + key,
                "unit": "returned_rows",
                "amount": result["raw_rows"],
                "category": "observed",
                "scope": "campaign",
                "attempt_id": key,
                "source": "Complete CSV rows including unresolved/invalid rows; not total backend oracle evaluations",
            },
        )

    def import_csv(self, path, provenance, parent_id=None):
        from pilot.property_assessment import PlatformPropertyAssessor

        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Regular result CSV required")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if provenance.get("artifact_sha256") != sha or not provenance.get("source"):
            raise ValueError("Exact artifact identity/source required")
        target = Path(self.spec["artifact_directory"]) / ("artifact-" + sha + ".csv")
        if not target.exists():
            with target.open("xb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(path.read_bytes())
        if hashlib.sha256(target.read_bytes()).hexdigest() != sha:
            raise ValueError("Artifact changed during intake")
        batch = PlatformPropertyAssessor(self.spec["assessor"]).assess_csv(target)
        if batch["artifact_sha256"] != sha:
            raise ValueError("Assessment used different artifact bytes")
        if batch["evaluation_blockers"]:
            with self.store._db() as db:
                old = json.loads(
                    db.execute(
                        "SELECT blockers FROM smallmol_assignments WHERE id=?",
                        (self.assignment_id,),
                    ).fetchone()[0]
                )
                db.execute(
                    "UPDATE smallmol_assignments SET blockers=? WHERE id=?",
                    (
                        json.dumps(sorted(set(old + batch["evaluation_blockers"]))),
                        self.assignment_id,
                    ),
                )
        existing = {c["id"]: c for c in self.report()["candidates"]}
        if parent_id is not None and parent_id not in existing:
            raise ValueError("Unknown generation parent")
        entries = {e["candidate"]["id"]: e for e in batch["cache"].values()}
        generated = {r["candidate_id"] for r in batch["rows"] if r["candidate_id"]}
        candidates = []
        observations = []
        for cid in sorted(generated):
            entry = entries[cid]
            c = entry["candidate"]
            record = existing.get(cid) or {
                k: c[k] for k in ("id", "form_id", "representation", "source")
            }
            if cid not in existing and parent_id is not None and cid != parent_id:
                record["parent_id"] = parent_id
            candidates.append(record)
            for e in entry["property_evidence"]:
                if e["artifact_sha256"] != sha:
                    continue
                observations.append(
                    {
                        "id": "obs-"
                        + digest([e["row_id"], "lipophilicity", provenance]),
                        "candidate_id": cid,
                        "form_id": c["form_id"],
                        "endpoint": "lipophilicity",
                        "value": e["reported_value"],
                        "qualifier": "="
                        if e["reported_value"] is not None
                        else "unknown",
                        "status": "completed"
                        if e["reported_value"] is not None
                        else "unknown",
                        **self.spec["observation_signatures"]["lipophilicity"],
                        "source": provenance["source"],
                        "artifact": sha,
                    }
                )
            for endpoint in ("qed", "lead_similarity"):
                observations.append(
                    {
                        "id": "obs-" + digest([sha, cid, endpoint, provenance]),
                        "candidate_id": cid,
                        "form_id": c["form_id"],
                        "endpoint": endpoint,
                        "value": entry["summary"]["values"][endpoint],
                        "qualifier": "=",
                        "status": "completed",
                        **self.spec["observation_signatures"][endpoint],
                        "source": provenance["source"],
                        "artifact": sha,
                    }
                )
        if candidates or observations:
            self.store.dispatch(
                "record_batch",
                self.campaign_id,
                {"candidates": candidates, "observations": observations},
            )
        result = {
            k: batch[k]
            for k in (
                "raw_rows",
                "invalid_rows",
                "unresolved_rows",
                "duplicate_rows",
                "qualified_candidate_ids",
                "evaluation_blockers",
                "artifact_sha256",
            )
        }
        target = Path(self.spec["artifact_directory"]) / ("intake-" + sha + ".json")
        target.write_text(
            json.dumps({"provenance": provenance, "diagnostics": result}, indent=2)
            + "\n"
        )
        os.chmod(target, 0o600)
        return result
