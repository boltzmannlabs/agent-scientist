"""Profile-owned upload evidence, with durable capacity reservations and job pins."""

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import math
import os
import re
import shutil
import time
import uuid

from sci_cli.plugins_state import PluginState, _locked_plugin_state
from sci_constants import mkdir_under_sci_home
from utils import atomic_json_write, atomic_write_bytes, fsync_directory

LIMIT_BYTES = 256 * 1024 * 1024
RETENTION_SECONDS = 30 * 24 * 60 * 60
REFERENCE_BYTES = 16 * 1024
GUIDANCE = ("Run `sci boltzmann-receipts status`, then `sci boltzmann-receipts cleanup`. "
            "Poll known jobs to confirm their outcomes. Active, unresolved, and legacy-history receipts "
            "cannot be cleaned automatically; reconcile them with support. Do not delete state.json or retry uploads blindly.")


class ReceiptStorageError(RuntimeError):
    pass


def _encode(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _timestamp(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _receipt_key(value):
    return (isinstance(value, str) and value.startswith("upload:") and 7 < len(value) <= 128
            and ".." not in value and re.fullmatch(r"[A-Za-z0-9_.:-]+", value))


class ReceiptStore:
    def __init__(self):
        # Bind once to the caller's scope, including work continuing after a timeout.
        self.state = PluginState("boltzmann")
        self.state_path = self.state.path
        self.root = self.state_path.parent / "upload-receipts-v1"

    @contextmanager
    def _locked(self):
        try:
            for path in (self.root.parent.parent, self.root.parent, self.root):
                if path.is_symlink():
                    raise ReceiptStorageError("Receipt storage must not use symbolic links.")
            mkdir_under_sci_home(self.root)
            os.chmod(self.root, 0o700)
            lock = self.root / ".ledger.lock"
            if any(p.is_symlink() for p in (lock, self.state_path,
                                           self.state_path.with_name(".state.json.lock"))):
                raise ReceiptStorageError("Receipt lock must not be a symbolic link.")
            with _locked_plugin_state(self.root / "ledger"):
                os.chmod(lock, 0o600)
                # An interrupted atomic writer leaves only an uncommitted scratch file.
                for path in self.root.glob(".receipt-*.tmp"):
                    path.unlink()
                yield
        except ReceiptStorageError:
            raise
        except (OSError, ValueError, RuntimeError) as exc:
            # Never echo JSON payloads or service credentials from exception strings.
            code = f", errno={exc.errno}" if isinstance(exc, OSError) else ""
            raise ReceiptStorageError(f"Receipt storage operation failed ({type(exc).__name__}{code}). "
                                      "An earlier atomic step may have completed; inspection/retry is recoverable. "
                                      + GUIDANCE) from exc

    def _rows(self):
        rows = {}
        for path in self.root.glob("*.json"):
            if path.is_symlink() or not path.is_file() or path.stat().st_size > LIMIT_BYTES:
                raise ReceiptStorageError("Unsafe or oversized receipt record; cleanup stopped. " + GUIDANCE)
            row = json.loads(path.read_text(encoding="utf-8-sig"))
            if (not isinstance(row, dict) or row.get("version") != 1 or row.get("id") != path.stem
                    or row.get("kind") not in {"upload", "submission"}
                    or type(row.get("capacity")) is not int or row["capacity"] != path.stat().st_size
                    or not _timestamp(row.get("created"))):
                raise ReceiptStorageError("Malformed receipt record; cleanup stopped. " + GUIDANCE)
            if row["kind"] == "upload":
                valid = (isinstance(row.get("receipt"), dict) and type(row.get("legacy_unknown")) is bool
                         and row.get("state") in {"reserved", "uploaded"}
                         and ("uploaded_at" not in row or _timestamp(row["uploaded_at"]))
                         and (row["state"] == "reserved" and "key" in row or
                              _receipt_key(row.get("key"))))
            else:
                valid = (isinstance(row.get("receipts"), list)
                         and all(isinstance(r, str) for r in row["receipts"])
                         and row.get("state") in {"unknown", "running", "terminal"}
                         and isinstance(row.get("job"), str)
                         and "doc_id" in row and (row["doc_id"] is None or isinstance(row["doc_id"], str))
                         and "terminal_at" in row
                         and (row["state"] != "terminal" or _timestamp(row.get("terminal_at"))))
            if not valid:
                raise ReceiptStorageError("Malformed receipt lifecycle; cleanup stopped. " + GUIDANCE)
            rows[row["id"]] = row
        return rows

    def _write(self, row):
        encoded = _encode(row)
        if len(encoded) > row["capacity"]:
            raise ReceiptStorageError("Receipt exceeded its reserved space; retained reservation is protected. " + GUIDANCE)
        path = self.root / (row["id"] + ".json")
        if path.is_symlink():
            raise ReceiptStorageError("Receipt record must not be a symbolic link.")
        atomic_write_bytes(path, encoded + b" " * (row["capacity"] - len(encoded)),
                           tmp_prefix=".receipt-", mode=0o600, fsync_dir=True)

    def _reserve(self, row, extra):
        row.update(version=1, capacity=0)
        row["capacity"] = len(_encode(row)) + extra + 128
        sizes = [p.stat().st_size for p in self.root.iterdir() if p.is_file()]
        used = sum(sizes)
        if used + row["capacity"] > LIMIT_BYTES:
            raise ReceiptStorageError(f"Receipt capacity unavailable: {used} bytes used, "
                                      f"{row['capacity']} required, {LIMIT_BYTES} limit. No external action started. " + GUIDANCE)
        # Preserve replacement headroom for the largest outstanding reservation,
        # not just this request: many small uploads must not strand a large one.
        headroom = max([row["capacity"], *sizes])
        if shutil.disk_usage(self.root).free < row["capacity"] + headroom + 1024 * 1024:
            raise ReceiptStorageError("Insufficient disk space for the receipt and its atomic replacement. " + GUIDANCE)
        # The padded slot physically occupies the reservation before any external action.
        self._write(row)
        return row["id"]

    def _legacy(self):
        if self.state_path.is_symlink():
            raise ReceiptStorageError("Legacy plugin state must not be a symbolic link.")
        if not self.state_path.exists():
            return {}
        data = json.loads(self.state_path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ReceiptStorageError("Malformed legacy plugin state; migration stopped. " + GUIDANCE)
        return data

    def _migrate(self):
        with _locked_plugin_state(self.state_path):
            data = self._legacy()
            keys = [key for key in data if key.startswith("upload:")]
            rows = self._rows()
            for key in keys:
                if not _receipt_key(key) or not isinstance(data[key], dict):
                    raise ReceiptStorageError("Malformed legacy upload entry; migration stopped without deleting it. " + GUIDANCE)
                identity = "legacy-" + hashlib.sha256(key.encode()).hexdigest()
                existing = rows.get(identity)
                if existing:
                    if existing["key"] != key or existing["receipt"] != data[key]:
                        raise ReceiptStorageError("Legacy receipt migration conflict; both copies retained. " + GUIDANCE)
                    continue
                self._reserve({"id": identity, "kind": "upload", "key": key,
                               "state": "uploaded", "created": time.time(), "legacy_unknown": True,
                               "receipt": data[key]}, 1024)
            if keys:
                # All destinations are durable before the one atomic source removal.
                # A crash before this write leaves idempotent, verifiable duplicate copies.
                for key in keys:
                    del data[key]
                atomic_json_write(self.state_path, data, mode=0o600, fsync_dir=True)
            return len(keys)

    def migrate(self):
        with self._locked():
            return self._migrate()

    @staticmethod
    def _retirement(row, submissions):
        if row["state"] != "uploaded":
            return None, "upload outcome unresolved"
        if row["legacy_unknown"]:
            return None, "legacy job history unknown"
        linked = [r for r in submissions if row["id"] in r["receipts"]]
        if any(r["state"] != "terminal" for r in linked):
            return None, "linked submission running or unresolved"
        since = max([row.get("uploaded_at", row["created"]), *(r["terminal_at"] for r in linked)])
        return since + RETENTION_SECONDS, None

    def _cleanup(self, rows):
        now = time.time()
        submissions = [r for r in rows.values() if r["kind"] == "submission"]
        removed = []
        for row in rows.values():
            if row["kind"] != "upload":
                continue
            expires, _ = self._retirement(row, submissions)
            if expires is not None and now >= expires:
                (self.root / (row["id"] + ".json")).unlink()
                removed.append(row["id"])
        remaining = set(rows) - set(removed)
        for row in submissions:
            if row["state"] == "terminal" and not any(r in remaining for r in row["receipts"]):
                (self.root / (row["id"] + ".json")).unlink()
        if removed:
            fsync_directory(self.root)
        return removed

    def cleanup(self):
        with self._locked():
            self._migrate()
            return self._cleanup(self._rows())

    def reserve_upload(self, receipt):
        with self._locked():
            self._migrate()
            self._cleanup(self._rows())
            return self._reserve({"id": uuid.uuid4().hex, "kind": "upload", "state": "reserved",
                                  "key": None, "receipt": deepcopy(receipt), "created": time.time(),
                                  "legacy_unknown": False}, 2 * REFERENCE_BYTES + 4096)

    def complete_upload(self, identity, key, storage, receipt):
        with self._locked():
            if len(_encode(storage)) > REFERENCE_BYTES:
                raise ReceiptStorageError("Upload returned an oversized reference; reservation retained. " + GUIDANCE)
            row = self._rows().get(identity)
            if not row or row["kind"] != "upload":
                raise ReceiptStorageError("Reserved upload record is unavailable; finalization stopped. " + GUIDANCE)
            row.update(state="uploaded", key=key, storage_path=storage, receipt=receipt, uploaded_at=time.time())
            self._write(row)

    def find(self, key):
        with self._locked():
            self._migrate()
            matches = [r for r in self._rows().values()
                       if r["kind"] == "upload" and r["state"] == "uploaded" and r["key"] == key]
            row = max(matches, key=lambda r: r["created"], default=None)
            return (row["receipt"], row["id"]) if row else (None, None)

    def get(self, key):
        return self.find(key)[0]

    def begin_submission(self, job, identities, experiment_name=""):
        if not identities:
            return None
        with self._locked():
            self._migrate()
            rows = self._rows()
            if any(i not in rows or rows[i]["kind"] != "upload" for i in identities):
                raise ReceiptStorageError("An input receipt expired before submission; validate the input again. No job submitted.")
            return self._reserve({"id": uuid.uuid4().hex, "kind": "submission", "job": job,
                                  "experiment_name": experiment_name,
                                  "doc_id": None, "state": "unknown", "receipts": sorted(set(identities)),
                                  "created": time.time(), "terminal_at": None}, REFERENCE_BYTES + 4096)

    def accept_submission(self, attempt, doc_id):
        if not attempt:
            return
        with self._locked():
            if not isinstance(doc_id, str) or not doc_id or len(_encode(doc_id)) > REFERENCE_BYTES:
                raise ReceiptStorageError("Submission returned no bounded job ID; its receipts remain protected. " + GUIDANCE)
            row = self._rows().get(attempt)
            if not row or row["kind"] != "submission":
                raise ReceiptStorageError("Reserved submission record is unavailable; job linking stopped. " + GUIDANCE)
            row.update(doc_id=doc_id, state="running")
            self._write(row)

    def observe(self, job, doc_id, result):
        with self._locked():
            self._migrate()
            rows = self._rows()
            for row in rows.values():
                if row["kind"] != "submission" or row["job"] != job or row["doc_id"] != doc_id:
                    continue
                terminal = (isinstance(result, dict) and result.get("job_terminal_confirmed") is True
                            and result.get("job_name") == job and result.get("doc_id") == doc_id
                            and str(result.get("status", "")).lower().strip() in
                            {"completed", "success", "100%completed", "failed", "error", "cancelled", "canceled"}
                            and not result.get("timeout") and not result.get("authorization_required"))
                if terminal:
                    row.update(state="terminal", terminal_at=row["terminal_at"] if row["terminal_at"] is not None else time.time())
                else:
                    row.update(state="unknown", terminal_at=None)
                self._write(row)
            self._cleanup(rows)

    def inspect(self):
        with self._locked():
            rows = self._rows()
            with _locked_plugin_state(self.state_path):
                legacy = sum(k.startswith("upload:") for k in self._legacy())
            submissions = [r for r in rows.values() if r["kind"] == "submission"]
            records = []
            for row in rows.values():
                summary = {k: row[k] for k in ("id", "kind", "state", "capacity", "created", "legacy_unknown",
                                               "job", "doc_id", "receipts", "terminal_at", "experiment_name") if k in row}
                if row["kind"] == "upload":
                    summary["eligible_after"], summary["protected_reason"] = self._retirement(row, submissions)
                records.append(summary)
            return {"directory": str(self.root), "limit_bytes": LIMIT_BYTES,
                    "used_bytes": sum(p.stat().st_size for p in self.root.iterdir() if p.is_file()),
                    "retention_days": RETENTION_SECONDS // 86400, "legacy_entries_pending_migration": legacy,
                    "records": records}
