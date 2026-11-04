"""Thin adapter over the existing profile-scoped Boltzmann tool dispatcher.

No HTTP client, key handling, retries, approval overrides or durable job state.
The owning runner must persist intent BEFORE calling upload/submit. Exceptions or
unusable responses after dispatch leave the outcome unknown, not confirmed failed.
Native receipts can contain signed references; keep them in private run state.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit


JOB_NAME = "Fragment_Based_Optimization"
BINDING = "_pilot_binding"


class AdapterError(ValueError):
    """Local pre-dispatch rejection: this adapter did not call the connector."""


class ReceiptError(RuntimeError):
    """A call occurred, but its response cannot establish a usable association."""


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _file_sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def require_property_models(parameters):
    """Require explicit property targets; preserve the caller's model/bounds.

    This admission check is not model availability, endpoint/unit qualification
    or complete platform schema validation. The existing connector owns those
    schema checks; the task owner must establish scientific objective alignment.
    """
    if not isinstance(parameters, dict) or set(parameters) - {"global_models", "custom_models"}:
        raise AdapterError("Supply documented global_models/custom_models selections; do not supply worker-managed attribute fields")
    if any(not isinstance(v, list) for v in parameters.values()):
        raise AdapterError("Property-model selections must be arrays")
    if not any(parameters.values()):
        raise AdapterError("Optimization requires at least one explicitly selected property model before upload or submission")
    for collection, identity in (("global_models", "name"), ("custom_models", "id")):
        for item in parameters.get(collection, []):
            if not isinstance(item, dict) or not _text(item.get(identity)):
                raise AdapterError("Each selected property model needs its documented name or authorized custom ID")
            if not {"min_threshold", "max_threshold"} <= item.keys():
                raise AdapterError("Supply explicit min_threshold/max_threshold values, including documented empty bounds")
    try:
        _digest(parameters)
    except (TypeError, ValueError):
        raise AdapterError("Property-model selections must be finite JSON") from None
    return deepcopy(parameters)


def _request(request, *, verify_file):
    if not isinstance(request, dict):
        raise AdapterError("Request must be an object")
    for name in ("request_id", "library_csv_path", "library_content_sha256"):
        if not _text(request.get(name)):
            raise AdapterError("Request is missing a required identity field")
    expected = request["library_content_sha256"]
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise AdapterError("A lowercase SHA-256 library identity is required")
    reference, extras = request.get("reference"), request.get("generation_parameters", {})
    if not isinstance(reference, dict) or not _text(reference.get("representation")):
        raise AdapterError("Original reference representation is required")
    if not isinstance(extras, dict) or set(extras) & {"ref_mol", "library_path", "experiment_name"}:
        raise AdapterError("Generation parameters cannot override reference, upload or experiment identity")
    if verify_file:
        require_property_models(extras)
    try:
        payload = deepcopy({**extras, "ref_mol": reference["representation"]})
        payload_sha = _digest(payload)
    except (TypeError, ValueError):
        raise AdapterError("Generation parameters must be finite JSON") from None
    if verify_file:
        path = Path(request["library_csv_path"]).expanduser()
        if path.is_symlink() or not path.is_file():
            raise AdapterError("An existing regular library file is required")
        try:
            actual = _file_sha(path)
        except OSError:
            raise AdapterError("Library could not be read before dispatch") from None
        if actual != expected:
            raise AdapterError("Library bytes changed; no connector call was made")
    binding = {"request_id": request["request_id"], "library_content_sha256": expected,
               "payload_sha256_without_storage": payload_sha, "job_name": JOB_NAME}
    return payload, binding


def _bound(receipt, binding):
    if not isinstance(receipt, dict) or receipt.get(BINDING) != binding:
        raise AdapterError("Receipt does not belong to the current frozen request")


class NodeAPIAdapter:
    def __init__(self, call_tool, *, allow_partial_validation=False):
        if not callable(call_tool):
            raise AdapterError("Existing connector dispatcher callback required")
        if type(allow_partial_validation) is not bool:
            raise AdapterError("Partial validation requires an explicit boolean from the authorized host")
        self.call_tool = call_tool
        # A validation warning or a general run request is not approval. The
        # owning host may set True only after the user reviews that warning and
        # explicitly approves best-effort execution through the normal connector.
        self.allow_partial_validation = allow_partial_validation
        self.active_host_instrumented = False

    @classmethod
    def from_active_host(cls, *, allow_partial_validation=False, **dispatch_context):
        """Use within the owning Agent Scientist runtime, with its normal grants.

        This does not set SCI_HOME, resolve credentials or enable a toolset. Pass
        the active host's session/tool grants when its dispatcher requires them.
        Middleware bypass flags are deliberately not accepted. The ordinary
        connector's partial-validation flag defaults to False; True requires the
        user's explicit approval of the concrete unchecked aspects first.
        """
        allowed = {"task_id", "tool_call_id", "session_id", "turn_id", "api_request_id",
                   "user_task", "enabled_tools", "enabled_toolsets", "disabled_toolsets"}
        if set(dispatch_context) - allowed:
            raise AdapterError("Unsupported dispatch context")
        from model_tools import handle_function_call
        instance = cls(lambda name, args: handle_function_call(name, args, **dispatch_context),
                       allow_partial_validation=allow_partial_validation)
        instance.active_host_instrumented = True
        return instance

    def _call(self, name, arguments, binding=None):
        # Do not catch callback exceptions: a request may have reached the service.
        raw = self.call_tool(name, deepcopy(arguments))
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError):
                raise ReceiptError("Connector returned non-JSON; outcome is unknown") from None
        if not isinstance(raw, dict) or not raw or BINDING in raw:
            raise ReceiptError("Connector returned an unusable receipt; outcome is unknown")
        try:
            _digest(raw)
        except (TypeError, ValueError):
            raise ReceiptError("Connector returned non-finite or non-JSON data; outcome is unknown") from None
        result = deepcopy(raw)
        if binding is not None:
            result[BINDING] = deepcopy(binding)
        return result

    def upload(self, request):
        payload, binding = _request(request, verify_file=True)
        result = self._call("boltzmann_upload", {
            "local_path": str(Path(request["library_csv_path"]).expanduser().absolute()),
            "job_name": JOB_NAME, "input_field": "library_path",
            "experiment_data": payload, "allow_partial_validation": self.allow_partial_validation}, binding)
        if result.get("status") == "uploaded" and not result.get("error"):
            storage = result.get("s3_path")
            if (result.get("sha256") != binding["library_content_sha256"] or not _text(storage)
                    or storage.startswith(("/", "~/", "file:"))):
                raise ReceiptError("Upload association was not established; do not repeat automatically")
        return result

    def submit(self, request, upload_receipt):
        payload, binding = _request(request, verify_file=True)
        _bound(upload_receipt, binding)
        storage = upload_receipt.get("s3_path")
        if (upload_receipt.get("status") != "uploaded" or upload_receipt.get("error")
                or upload_receipt.get("sha256") != binding["library_content_sha256"]
                or not _text(storage) or storage.startswith(("/", "~/", "file:"))):
            raise AdapterError("A matching successful native upload receipt is required")
        payload["library_path"] = storage
        # Deterministic identity is for trace association, not service idempotency.
        name = "smallmol-pilot-" + hashlib.sha256(request["request_id"].encode()).hexdigest()[:32]
        result = self._call("boltzmann_submit", {
            "job_name": JOB_NAME, "experiment_data": payload,
            "experiment_name": name, "allow_partial_validation": self.allow_partial_validation}, binding)
        if result.get("status") == "accepted" and not result.get("error"):
            if not _text(result.get("doc_id")) or result.get("job_name", JOB_NAME) != JOB_NAME:
                raise ReceiptError("Submit response lacks a matching job identity; reconcile before replacement")
        return result

    def status(self, request, submit_receipt):
        _, binding = _request(request, verify_file=False)
        _bound(submit_receipt, binding)
        if (not _text(submit_receipt.get("doc_id"))
                or submit_receipt.get("job_name", JOB_NAME) != JOB_NAME):
            raise AdapterError("A known matching job ID is required for read-only monitoring")
        # Even an unknown submit can be monitored if its original receipt contains
        # a known job ID. A polling error never determines that job's outcome.
        return self._call("boltzmann_status", {"job_name": JOB_NAME,
                                                "doc_id": submit_receipt["doc_id"]}, binding)

    def download(self, download_url, output_folder):
        if not _text(download_url):
            raise AdapterError("Native signed HTTPS download reference required")
        try:
            parsed = urlsplit(download_url)
        except ValueError:
            raise AdapterError("Invalid native download reference") from None
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise AdapterError("Native signed HTTPS download reference required")
        if not isinstance(output_folder, (str, Path)) or not str(output_folder).strip():
            raise AdapterError("Explicit private output folder required")
        return self._call("boltzmann_download", {"download_url": download_url,
                                                  "output_folder": str(output_folder)})
