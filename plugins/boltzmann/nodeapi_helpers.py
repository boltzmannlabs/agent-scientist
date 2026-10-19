# nodeapi_helpers.py — Boltzmann NodeAPI helpers + MongoDB logging layer.
# Token is passed explicitly by the caller.

import base64
import json
import os
import threading
import time
import uuid
import tempfile
import requests
from typing import Dict, Any, Optional
from urllib.parse import urlparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Per-conversation locks to prevent read-modify-write races.
# Keyed by conversation_id — different users/conv_ids never block each other.
_CONV_LOCKS: dict[str, threading.Lock] = {}
_CONV_LOCKS_MUTEX = threading.Lock()


def _get_conv_lock(conversation_id: str) -> threading.Lock:
    """Return (and cache) a per-conv_id lock.  Auto-cleaned on acquire."""
    with _CONV_LOCKS_MUTEX:
        if conversation_id not in _CONV_LOCKS:
            _CONV_LOCKS[conversation_id] = threading.Lock()
        return _CONV_LOCKS[conversation_id]

CONVERSATION_COLLECTION = "AgentConversationLogs"

_SUBMIT_URL = "https://nodeapis.boltzmann.co/api/submit-job"
_AUTH_CHECK_URL = "https://nodeapis.boltzmann.co/api/get-projects"
_FETCH_URL = "https://nodeapis.boltzmann.co/api/result"
_UPLOAD_URL = "https://nodeapis.boltzmann.co/api/fileUpload"
_DOC_FETCH_URL = "https://nodeapis.boltzmann.co/fetchdocdetails"
_BACKEND_UPDATE_URL = "https://nodeapis.boltzmann.co/backendupdate"
_TOOL_LOG_URL = "https://nodeapis.boltzmann.co/v5/tools/mongodb_fetcher"
_TOOL_LOG_COMPAT_URL = "https://nodeapis.boltzmann.co/v4/tools/mongodb_fetcher"

# Auth-blip resilience. Boltzmann's NodeAPI can intermittently reject a valid
# API key for short windows, then recover on its
# own.  A blip during a logging write used to drop/clobber entries (fetch
# returned None -> seeded an empty conversation -> uploaded over real data).
# We now retry auth failures so logging survives the blip, and signal
# _AUTH_FAILED (skip — never seed) only if it persists beyond the retry budget.
_AUTH_RETRY_ATTEMPTS = 5      # extra attempts after the first (6 total)
_AUTH_RETRY_DELAY = 3.0       # seconds between attempts (~15s ceiling)
_AUTH_FAILED = object()       # sentinel: persistent auth failure — caller must SKIP, never seed

# Percentage buffer added to every tool's base timeout (25%).
_BUFFER_PCT = 0.25
# Minimum buffer floor in seconds — short tools still get at least this.
_MIN_BUFFER_S = 15


def _apply_buffer(base_seconds: float) -> float:
    """Add 25% buffer with a 15 s minimum floor."""
    return base_seconds + max(base_seconds * _BUFFER_PCT, _MIN_BUFFER_S)


def _display_name(job_name: str) -> str:
    """Convert internal job_name to human-readable text for user-facing descriptions.

    >>> _display_name("Random_Antibody_Generation")
    'Random Antibody Generation'
    >>> _display_name("Function_Based_Enzyme_Generation")
    'Function Based Enzyme Generation'
    """
    return job_name.replace("_", " ")


# ── Tool timeout lookup ──────────────────────────────────────────────────────
#
# Every key is the EXACT job_name string the agent passes to boltzmann_submit.
# Values are either:
#   - a static float (seconds, already buffered), or
#   - a callable (experiment_data: dict) -> float (computes + buffers)
#
# Unknown tools fall back to BOLTZMANN_MAX_POLL_SECONDS (default 300 s).

def _tool_timeout(job_name: str, experiment_data: dict | None = None) -> float:
    """Return the per-tool poll timeout (seconds) for *job_name*.

    Parameters
    ----------
    job_name : str
        Exact tool name from the Boltzmann skill reference.
    experiment_data : dict | None
        The input payload originally passed to ``submit_request``.  Used to
        compute formula-based timeouts (e.g. n_samples scaling).  When None,
        formula tools fall back to a conservative estimate.

    Returns
    -------
    float
        Poll timeout in seconds (base time + 25 % buffer, ≥15 s floor).
    """
    data = experiment_data or {}

    # ---- Protein Engineering (BoltPro) ------------------------------------

    # (1) Random Antibody Generation – ~1 s / sample
    if job_name == "Random_Antibody_Generation":
        n = int(data.get("n_samples", 20))
        return _apply_buffer(n * 1.0)

    # (2) CDR Generator – ~0.6 s / sequence
    if job_name == "CDR_Generator":
        n = int(data.get("n_samples", 10))
        return _apply_buffer(n * 1.0)

    # (3) Backbone Generation – ~9.4 s / structure (multiples of 7)
    if job_name == "Backbone_Generation":
        n = int(data.get("n_samples", 7))
        return _apply_buffer(n * 9.5)

    # (4) Backbone → Sequence – depends on backbone count + seqs per backbone
    if job_name == "Antibody_Backbone_to_Sequence_Generation":
        # ~3 s base + ~1 s per sequence; conservative for unknown counts
        return _apply_buffer(102)  # 10 backbones × 10 seqs

    # (5) Enzyme Generation – ~60 s / structure
    if job_name == "Function_Based_Enzyme_Generation":
        n = int(data.get("n_samples", 10))
        return _apply_buffer(n * 60)

    # (6) Structure-Based Peptide Generation – ~12 s / structure
    if job_name == "Structure_based_peptide_generation":
        n = int(data.get("num_structures", 10))
        return _apply_buffer(n * 12)

    # (7) Peptide Property Prediction – ~4 s / sequence + 15 s base
    if job_name == "Peptide_Property_Prediction":
        n = int(data.get("n_sequences", 10))
        return _apply_buffer(n * 4 + 15)

    # (8) Boltz Structure Prediction – ~150 s / sequence (conservative)
    if job_name == "boltz_structure_prediction":
        n_prot = len(data.get("Protein_Sequences", []) or [])
        n_dna = len(data.get("DNA_Sequences", []) or [])
        n_rna = len(data.get("RNA_Sequences", []) or [])
        n = max(n_prot + n_dna + n_rna, 1)
        return _apply_buffer(n * 150)

    # (9) Evobind – ~145 s / peptide + 17 s base
    if job_name == "Evobind":
        n = int(data.get("num_peptides", 5))
        return _apply_buffer(17 + n * 145)

    # (10) Antibody Property Prediction – ~60 s (fixed)
    if job_name == "Antibody_Prediction":
        return _apply_buffer(60)

    # (11) Random Controlled Mutagenesis – ~0.6 s / sequence + 5 s
    if job_name == "Random_Controlled_Mutagenesis":
        n = int(data.get("n_samples", 10))
        return _apply_buffer(n * 0.6 + 5)

    # (12) Monomer Structure Prediction
    #     monomer:  ~200 s + 110 s / seq
    #     multimer: ~250 s + 225 s / complex
    if job_name == "Protein_Structure_Prediction":
        n = int(data.get("n_structures", 1)) or int(data.get("num_structures", 1)) or 1
        return _apply_buffer(250 + n * 225)  # conservative (multimer tier)

    # (13) MLDE (Directed Evolution) – ~10 s / sequence + 10 s
    if job_name == "mlde":
        n = int(data.get("n_sequences", 10))
        return _apply_buffer(n * 10 + 10)

    # (14) Prodigy (Binding Affinity) – ~3 s / sequence + 5 s
    if job_name == "Prodigy":
        n = int(data.get("n_sequences", 10))
        return _apply_buffer(n * 3 + 5)

    # (15) Unconditional Sampling – ~47 s (fixed)
    if job_name == "Uncondtional_Sampling":
        return _apply_buffer(47)

    # (16) Motif Scaffolding – ~14 s / structure + 10 s
    if job_name == "Motiff_Scaffolding":
        n = int(data.get("samples_per_target", 10))
        return _apply_buffer(n * 14 + 10)

    # (17) Ligand MPNN – ~6 s / sequence + 5 s
    if job_name == "Ligand_MPNN":
        n = int(data.get("num_sequences", 10))
        return _apply_buffer(n * 6 + 5)

    # (18) NetsolP (Solubility) – ~9 s / sequence + 5 s
    if job_name == "Netsolp":
        n = int(data.get("n_sequences", 10))
        return _apply_buffer(n * 9 + 5)

    # (19) Pep_Patch – ~60 s (fixed)
    if job_name == "Pep_Patch":
        return _apply_buffer(60)

    # (20) Cat_Pred (Catalyst) – ~8.6 s / sequence + 10 s
    if job_name == "Cat_Pred":
        n = int(data.get("n_sequences", 14))
        return _apply_buffer(n * 8.6 + 10)

    # (21) Clean (Enzyme Classification) – ~18 s / sequence + 5 s
    if job_name == "Clean":
        n = int(data.get("n_sequences", 10))
        return _apply_buffer(n * 18 + 5)

    # ---- Small Molecule (BoltChem) -----------------------------------------

    # (22) Property Prediction – no per-sample data; conservative 600 s base
    if job_name == "Property_Prediction":
        return _apply_buffer(600)

    # (23) AutoML – 15 + num_samples × 0.6
    if job_name == "automl":
        n = int(data.get("num_samples", 100))
        return _apply_buffer(15 + n * 0.6)

    # (24) Binding Site Prediction – max ~146 s for 80 pockets
    if job_name == "Binding_Site_Prediction":
        return _apply_buffer(146)

    # (25) Structure-Based Generator – 0.00000001×n² + 0.00024×n + 18
    if job_name == "Structure_Based_Generator":
        n = int(data.get("no_of_shapes", 1000))
        return _apply_buffer(0.00000001 * n * n + 0.00024 * n + 18)

    # (29) Pharmacophore Hypothesis – no formula; conservative 600 s
    if job_name == "Pharmacophore_Hypothesis":
        return _apply_buffer(600)

    # (30) Pharmacophore-Based Generator – 22 + num_molecules × 0.0017
    if job_name == "Pharmacophore_Based_Generator":
        n = int(data.get("num_molecules", 10_000))
        return _apply_buffer(22 + n * 0.0017)

    # (31) R-Group Enumeration – 30 + num_models × 5
    if job_name == "Molecule_Enumeration":
        n = int(data.get("num_models", 5))
        return _apply_buffer(30 + n * 5)

    # (32) Butina Clustering – 0.000869 × n + 11.59
    if job_name == "Butina_Clustering":
        n = int(data.get("num_smiles", 1_000))
        return _apply_buffer(0.000869 * n + 11.59)

    # (33) K-Means Clustering – 0.000183 × n + 10.60 (fixed-k); autok is
    #      ~0.000776 × n + 10.69 – use the larger coefficient
    if job_name == "K_Means_Clustering":
        n = int(data.get("num_smiles", 1_000))
        is_autok = str(data.get("no_of_clusters", "")).strip() in ("0", "auto")
        coeff = 0.000776 if is_autok else 0.000183
        return _apply_buffer(coeff * n + 10.69)

    # (34) Similarity Screening – 0.003 × n + 6
    if job_name == "Similarity_Screening":
        n = int(data.get("num_smiles", 10_000))
        return _apply_buffer(0.003 * n + 6)

    # (35) Pharmacophore Screening – no formula; conservative 600 s
    if job_name == "Pharmacophore_Screening":
        return _apply_buffer(600)

    # (36) Substructure Screening – 0.00000001×n² + 0.00024×n + 18
    if job_name == "Substructure_Screening":
        n = int(data.get("num_smiles", 1_000))
        return _apply_buffer(0.00000001 * n * n + 0.00024 * n + 18)

    # (37) Novelty Check – library-dependent
    #      ChEMBL:     18 + n×2.5
    #      SureChEMBL:  432.37 + n×25.47
    #      Enamine:    75.8 + n×1.5
    if job_name == "Novelty":
        n = int(data.get("num_smiles", 50))
        lib = str(data.get("library", "")).lower()
        if "surechembl" in lib:
            return _apply_buffer(432.37 + n * 25.47)
        if "enamine" in lib:
            return _apply_buffer(75.8 + n * 1.5)
        return _apply_buffer(18 + n * 2.5)  # ChEMBL default

    # (38) Lead Optimisation MCTS
    #      20 + 2.9×max(1, n_mols÷9) + 0.0075×n_mols
    if job_name == "Lead_Optimization_Mcts":
        n = int(data.get("n_mols", 100))
        return _apply_buffer(20 + 2.9 * max(1, n // 9) + 0.0075 * n)

    # Mars Plus – no measured formula; use the conservative generator timeout.
    if job_name == "Lead_Generation_Mars_Plus":
        return _apply_buffer(600)

    # (39) Lead Generation Reinvent
    #      21 + 7.7×max(1, n_mols÷100) + 0.036×n_mols
    if job_name == "Lead_Generation_Reinvent":
        n = int(data.get("n_mols", 1_000))
        return _apply_buffer(21 + 7.7 * max(1, n // 100) + 0.036 * n)

    # (40) Lead Generation Augmented
    #      hours = (M/500)×0.20×(1 + (attrs-3)×0.616) + 0.5
    if job_name == "Lead_Generation_Augmented":
        M = int(data.get("n_mols", 500))
        attrs = int(data.get("num_attributes", 3))
        hours = (M / 500) * 0.20 * (1 + max(attrs - 3, 0) * 0.616) + 0.5
        return _apply_buffer(hours * 3600)

    # Graph GA – no measured formula; use a conservative generator timeout.
    if job_name == "Lead_Generation_Graph_GA":
        return _apply_buffer(600)

    # (41) Fragment-Based Optimisation – 32 + n_unique_estimate×0.81
    if job_name == "Fragment_Based_Optimization":
        n = int(data.get("n_unique_estimate", 100))
        return _apply_buffer(32 + n * 0.81)

    # (42) DiffDock – ~330 s / SMILES
    if job_name == "Diffdock":
        n = int(data.get("n_smiles", 1))
        return _apply_buffer(n * 330)

    # Vina Flexible Docking – no measured formula; use a conservative timeout.
    if job_name == "Vina_Flexible_Docking":
        return _apply_buffer(600)

    # (44) MD OpenMM – conservative 1 hr
    if job_name == "MDS_openMM":
        return _apply_buffer(3_600)

    # (45) MD GROMACS – conservative 1 hr
    if job_name == "MDS_Gromacs":
        return _apply_buffer(3_600)

    # ---- Retrosynthesis (ReBolt) -------------------------------------------

    # (46) Retrosynthesis – 1-1.5 hr
    if job_name == "retrosynthesis":
        return _apply_buffer(5_400)

    # (47) Forward Reaction – 30-60 s
    if job_name == "forward_reaction":
        return _apply_buffer(90)

    # (48) Impurity Prediction – ~60 s
    if job_name == "impurity_prediction":
        return _apply_buffer(90)

    # (49) Atom Mapping – ~10 s
    if job_name == "atom_mapping":
        return _apply_buffer(30)

    # (50) Condition Recommendation – 20-30 s
    if job_name == "condition_recommendation":
        return _apply_buffer(60)

    # ---- Unknown tool — fall back to env / default ------------------------
    return _apply_buffer(300)


# ───────────────────────────────────────────────
# Token helpers
# ───────────────────────────────────────────────

def _is_auth_error(response: requests.Response) -> str | None:
    """Return a human-readable auth error message, or None if no auth failure."""
    if response.status_code not in (401, 403):
        return None
    detail = ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            detail = payload.get("message") or payload.get("detail") or payload.get("error") or ""
    except Exception:
        detail = response.text[:200]
    from .results import safe_detail
    # Do not echo credentials even when the server includes its request headers.
    authorization = getattr(getattr(response, "request", None), "headers", {}).get("Authorization", "")
    token = authorization.removeprefix("Bearer ")
    detail = safe_detail(detail, token)
    suffix = f" Backend said: {detail}" if detail else ""
    return f"Boltzmann service rejected authentication.{suffix}"


# ───────────────────────────────────────────────
# Timeout helpers
# ───────────────────────────────────────────────
def _resolve_token(token: str | None) -> str:
    """Return the API key supplied by the caller or active profile.

    Explicit parameter, then the profile-scoped environment passed to the
    plugin or its MCP child process.
    """
    if token is not None:
        return token.strip()
    try:
        from agent.secret_scope import get_secret
    except ImportError:
        return (os.getenv("BOLTZMANN_API_KEY") or "").strip()
    return (get_secret("BOLTZMANN_API_KEY") or "").strip()


def _auth_headers(token: str | None = None):
    key = _resolve_token(token)
    if not key:
        raise ValueError("BOLTZMANN_API_KEY is not configured for this profile")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def validate_api_key(token: str | None = None) -> bool:
    """Validate the API key using the read-only authenticated projects route."""
    active_token = _resolve_token(token)
    if not active_token:
        return False
    try:
        response = requests.get(
            _AUTH_CHECK_URL,
            headers=_auth_headers(active_token),
            timeout=15,
            allow_redirects=False,
        )
        if response.status_code != 200:
            return False
        payload = response.json()
    except (requests.exceptions.RequestException, ValueError):
        return False
    return isinstance(payload, dict) and str(payload.get("status", "")).lower() == "success"


# ───────────────────────────────────────────────
# Boltzmann NodeAPI functions
# ───────────────────────────────────────────────

def file_upload(input_path, token: str | None = None):
    active_token = _resolve_token(token)
    headers = _auth_headers(active_token)
    # requests supplies the multipart boundary when files are attached.
    headers.pop("Content-Type")
    with open(input_path, "rb") as f:
        files = {"file": f}
        response = requests.post(_UPLOAD_URL, headers=headers, files=files, timeout=120, allow_redirects=False)
    auth_err = _is_auth_error(response)
    if auth_err:
        return {"error": auth_err}
    try:
        result = response.json()
    except ValueError:
        result = {}
    if response.status_code == 200 and isinstance(result, dict) and result.get("status") and result.get("fileDetails", {}).get("folderPath"):
        return result["fileDetails"]["folderPath"]
    from .results import service_error
    return service_error("upload", response, active_token)


def submit_request(experiment_data, job_name, experiment_name, token: str | None = None, conv_id: str | None = None):
    payload = {
        "experimentData": experiment_data,
        "job_name": job_name,
        "experimentName": experiment_name,
    }
    active_token = _resolve_token(token)
    # 120 s HTTP timeout — gives slow/busy Boltzmann nodes enough time to
    # accept the job AND return a doc_id.  The old 60 s timeout caused the
    # client to give up while the server had already queued the job, which
    # led the LLM to re-submit → duplicate jobs on the platform.
    try:
        response = requests.post(_SUBMIT_URL, headers=_auth_headers(active_token), json=payload, timeout=120, allow_redirects=False)
    except requests.exceptions.ConnectTimeout:
        # TCP handshake never completed — server was never reached.
        # Safe to retry: no job was created on the platform.
        return {
            "error": (
                "Boltzmann server unreachable after 120 s (connection timed out). "
                "The job was NOT submitted — no request reached the server. "
                "You may retry once."
            ),
            "safe_to_retry": True,
        }
    except requests.exceptions.ReadTimeout:
        # Connection established and request body was sent, but the server
        # did not send a response within 120 s.  The job MAY have been
        # accepted and queued — re-submitting would create a duplicate.
        return {
            "error": (
                "Boltzmann server did not respond within 120 s after the request "
                "was sent.  The job may have already been accepted and queued on "
                "the platform — DO NOT re-submit without checking the Boltzmann "
                "dashboard for a recent job first.  Report this to the user."
            ),
            "safe_to_retry": False,
        }
    except requests.exceptions.ConnectionError:
        # A connection can break after the request body was delivered.
        return {
            "error": (
                "The Boltzmann connection failed; submission outcome is unknown. "
                "Reconcile the existing job before considering another submission."
            ),
            "stage": "submit", "status": "unknown", "safe_to_retry": False,
        }
    auth_err = _is_auth_error(response)
    if auth_err:
        return {"error": auth_err}
    try:
        result = response.json()
    except ValueError:
        result = {}
    if response.status_code == 200 and isinstance(result, dict) and result.get("success") and result.get("docId"):
        doc_id = result["docId"]
        conv_id = conv_id or os.getenv("conv_id") or ""
        if conv_id:
            try:
                log_workflow_update(
                    agent_mode="platform_tools",
                    message_type="workflow",
                    status="pending",
                    collection_name=job_name,
                    experiment_id=None,
                    step_type=job_name,
                    description=f"Executing {_display_name(job_name)}",
                    final_status="pending",
                    conv_id=conv_id,
                    token=active_token,
                )
            except Exception as exc:
                print(f"[submit_request] log failed: {exc}")
        return doc_id
    from .results import service_error
    return service_error("submit", response, active_token)


def _log_platform_terminal(collection_name, doc_id, status, conv_id, token):
    """Log a terminal (completed/failed) platform job result."""
    conv_id = conv_id or os.getenv("conv_id") or ""
    if not conv_id:
        return
    terminal = str(status or "completed").lower().strip()
    try:
        log_workflow_update(
            agent_mode="platform_tools",
            message_type="workflow",
            status="completed" if terminal not in ("failed", "error") else "failed",
            collection_name=str(collection_name),
            experiment_id=str(doc_id),
            step_type=str(collection_name),
            description=f"{_display_name(collection_name)} completed successfully" if terminal not in ("failed", "error") else f"{_display_name(collection_name)} failed",
            final_status="completed" if terminal not in ("failed", "error") else "failed",
            conv_id=conv_id,
            token=token,
        )
    except Exception as exc:
        print(f"[_log_platform_terminal] log failed for {collection_name}/{doc_id}: {exc}")


def fetch_status(
    collection_name,
    doc_id,
    watch_time=15,
    max_wait=None,
    token: str | None = None,
    experiment_data: dict | None = None,
    conv_id: str | None = None,
    output_folder: str | None = None,
):
    """Poll a submitted Boltzmann job until it completes or times out.

    The poll timeout is determined by (in priority order):
    1. Explicit ``max_wait`` parameter.
    2. Per-tool formula from ``_tool_timeout(collection_name, experiment_data)``.
    3. ``BOLTZMANN_MAX_POLL_SECONDS`` env var (default 300 s).

    Parameters
    ----------
    experiment_data : dict | None
        Original input payload from submit_request.  Used to compute
        formula-based timeouts (e.g. number of samples / sequences).
        When omitted the cached copy from ``submit_request`` is tried.
    """
    if max_wait is None:
        max_wait = _tool_timeout(str(collection_name), experiment_data)
    active_token = _resolve_token(token)
    headers = _auth_headers(active_token)
    payload = {"docId": doc_id, "job_name": collection_name}
    deadline = time.monotonic() + max_wait
    consecutive_errors = 0
    last_result = {"status": "unknown"}

    while True:
        if time.monotonic() >= deadline:
            return {**last_result, "stage": "status", "job_name": collection_name, "doc_id": doc_id,
                    "timeout": True, "safe_to_retry": False,
                    "message": "Polling window ended. The job may still be running; poll this same job, never resubmit."}

        try:
            response = requests.get(_FETCH_URL, headers=headers, json=payload,
                                    timeout=max(0.1, min(60, deadline - time.monotonic())), allow_redirects=False)
            auth_err = _is_auth_error(response)
            if auth_err:
                return {"error": auth_err, "stage": "status", "status": "unknown",
                        "authorization_required": True, "job_name": collection_name,
                        "doc_id": doc_id, "safe_to_retry": False}
            if not 200 <= response.status_code < 300:
                from .results import service_error
                return {**service_error("status", response, active_token),
                        "job_name": collection_name, "doc_id": doc_id}
            consecutive_errors = 0
        except requests.exceptions.RequestException:
            consecutive_errors += 1
            backoff = min(watch_time * (2 ** min(consecutive_errors - 1, 4)), 120)
            print(f"[fetch_status] Network error (attempt {consecutive_errors}); job outcome is unknown.")
            print(f"[fetch_status] Retrying in {backoff}s...")
            time.sleep(max(0, min(backoff, deadline - time.monotonic())))
            continue

        try:
            result = response.json()
        except Exception:
            print(f"[fetch_status] JSON parse failed (HTTP {response.status_code})")
            return {"error": "Status response was not valid JSON; job outcome is unknown.",
                    "stage": "status", "status": "unknown", "job_name": collection_name,
                    "doc_id": doc_id, "safe_to_retry": False}

        if not isinstance(result, dict) or "status" not in result:
            return {"error": "Status response omitted the job status; no completion is confirmed.",
                    "stage": "status", "status": "unknown", "job_name": collection_name,
                    "doc_id": doc_id, "safe_to_retry": False}

        status = str(result["status"]).lower().strip()
        last_result = {**result, "job_name": collection_name, "doc_id": doc_id}

        if status in ("completed", "success", "100%completed"):
            _log_platform_terminal(collection_name, doc_id, status, conv_id, active_token)
            return last_result

        if status in {"failed", "error", "cancelled", "canceled"}:
            from .results import safe_detail
            result = {"status": status, "stage": "status", "job_name": collection_name, "doc_id": doc_id,
                      "error": safe_detail(result, active_token) or "The service reported a terminal failure without a diagnostic.",
                      "safe_to_retry": False}
            _log_platform_terminal(collection_name, doc_id, "failed", conv_id, active_token)
            return result

        elapsed = int(time.monotonic() - (deadline - max_wait))
        remaining = int(deadline - time.monotonic())
        print(f"[fetch_status] status={status}  elapsed={elapsed}s  remaining={remaining}s")
        time.sleep(max(0, min(watch_time, deadline - time.monotonic())))


def download_from_signed_url(urls, output_folder: str, token: str | None = None):
    if urls is None:
        return {"output_paths": [], "error": "No URLs provided"}

    if isinstance(urls, str):
        urls = [urls]
    elif not isinstance(urls, list):
        try:
            urls = list(urls)
        except TypeError:
            urls = [str(urls)]

    output_files = []
    errors = []
    os.makedirs(output_folder, exist_ok=True)

    for url in urls:
        if not isinstance(url, str) or not url.startswith("http"):
            errors.append("Download reference is not a supported URL.")
            continue
        try:
            with requests.get(url, stream=True, timeout=120) as response:
                auth_err = _is_auth_error(response)
                if auth_err:
                    errors.append(auth_err)
                    continue
                response.raise_for_status()

                filename = os.path.basename(urlparse(url).path) or "res_file"
                if filename in {".", ".."}:
                    filename = "res_file"
                destination = Path(output_folder) / filename
                output_path = destination
                counter = 0
                while True:
                    try:
                        handle = output_path.open("xb")
                        break
                    except FileExistsError:
                        counter += 1
                        output_path = destination.with_name(f"{destination.stem}-{counter}{destination.suffix}")
                try:
                    with handle:
                        for chunk in response.iter_content(chunk_size=8192):
                            handle.write(chunk)
                except BaseException:
                    # Only this call's exclusively created, incomplete artifact.
                    output_path.unlink(missing_ok=True)
                    raise

            print(f"Downloaded: {output_path}")
            output_files.append(str(output_path))
        except Exception as e:
            from .results import safe_detail
            errors.append("Artifact download failed: " + safe_detail(str(e), token or ""))
            print("[download_from_signed_url] Artifact download failed; inspect the sanitized errors.")

    return {"output_paths": output_files, "errors": errors, "stage": "download",
            "status": "partial" if errors and output_files else "failed" if errors else "downloaded"}

def download_input_files(input_files: list[str], output_dir: str, token: str | None = None):
    """Return GCP file paths for use as tool dataPath inputs.

    Boltzmann tools accept GCP / S3 paths directly via their ``dataPath``
    parameter — no local download is needed.  This function validates that
    each reference is non-empty and returns them as-is so the LLM can pass
    them straight into tool calls.

    Returns
    -------
    dict
        ``{"output_paths": [...], "errors": [...]}``.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_paths: list[str] = []
    errors: list[str] = []

    for file_ref in input_files:
        if not file_ref or not isinstance(file_ref, str):
            errors.append(f"Skipping non-string ref: {str(file_ref)[:100]}")
            continue
        file_ref = file_ref.strip()
        if not file_ref:
            errors.append("Skipping empty file reference")
            continue
        # Pass through as-is — Boltzmann tools read directly from GCP/S3
        output_paths.append(file_ref)

    return {"output_paths": output_paths, "errors": errors}


def fetch_tool_log(collection: str, experiment_id: str, token: str | None = None):
    """Fetch one durable platform-tools record without mutating it."""
    if not collection or not experiment_id:
        return {"error": "collection and experiment_id are required"}
    payload = {"collection": collection, "experiment_id": experiment_id}
    headers = _auth_headers(_resolve_token(token))
    response = requests.post(_TOOL_LOG_URL, headers=headers, json=payload, timeout=60)
    if response.status_code in (404, 405):
        response = requests.post(
            _TOOL_LOG_COMPAT_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
    auth_err = _is_auth_error(response)
    if auth_err:
        return {"error": auth_err}
    try:
        result = response.json()
    except ValueError:
        return {"error": f"tool log lookup returned HTTP {response.status_code} without JSON"}
    if response.status_code >= 400:
        return {"error": f"tool log lookup failed with HTTP {response.status_code}", "details": result}
    return result


# --------------------------------------
# Handling two different workflow keys - one for platform tools and one for omics
# --------------------------------------

# ───────────────────────────────────────────────
# Layer 1: MongoDB document fetch & update via NodeAPI
# ───────────────────────────────────────────────

def fetch_document(conversation_id: str, agent_mode:str, job_name: str = "codegenagent", token: str | None = None) -> dict | None:
    """Fetch the whole MongoDB document via Node API.

    Returns the document dict, None if the document doesn't exist, or the
    _AUTH_FAILED sentinel if the backend rejected the token after all auth
    retries (a transient blip that didn't clear).  Callers MUST skip — never
    seed an empty doc — on _AUTH_FAILED, to avoid clobbering the conversation.
    Supports both explicit token and env/config fallback.
    """
    active_token = _resolve_token(token)
    headers = _auth_headers(active_token)
    payload = {"id": str(conversation_id), "job_name": job_name, "agent_mode": agent_mode, "collection_name": CONVERSATION_COLLECTION}

    senders = [
        lambda: requests.get(_DOC_FETCH_URL, headers=headers, json=payload, timeout=60),
        lambda: requests.get(_DOC_FETCH_URL, headers=headers, params=payload, timeout=60),
        lambda: requests.post(_DOC_FETCH_URL, headers=headers, json=payload, timeout=60),
    ]

    # Retry the whole sender batch across auth-blip windows: Boltzmann's NodeAPI
    # intermittently 401-rejects a valid token for ~15-20s then recovers on its
    # own.  A later attempt usually lands in a healthy window.
    last_response = None
    for attempt in range(_AUTH_RETRY_ATTEMPTS + 1):
        auth_err = None
        for sender in senders:
            try:
                response = sender()
            except requests.exceptions.RequestException as exc:
                print(f"[fetch_document] request failed: {exc}")
                continue
            ae = _is_auth_error(response)
            if ae:
                auth_err = ae
                break  # stop senders; retry the whole batch after a delay
            last_response = response
            if response.status_code == 200:
                try:
                    parsed = response.json()
                    if isinstance(parsed, dict):
                        return parsed.get("data", parsed)
                except (json.JSONDecodeError, ValueError):
                    pass
            if 400 <= response.status_code < 600:
                continue
            print(f"[fetch_document] failed: {response.status_code} {response.text[:200]}")
            return None

        if auth_err:
            print(f"[fetch_document] auth error (attempt {attempt + 1}/{_AUTH_RETRY_ATTEMPTS + 1}): {auth_err}")
            if attempt < _AUTH_RETRY_ATTEMPTS:
                time.sleep(_AUTH_RETRY_DELAY)
                continue
            return _AUTH_FAILED  # persistent auth failure — caller MUST skip, never seed

        # No auth error and no 200 across senders -> treat as missing/not-found.
        break

    if last_response is not None:
        print(f"[fetch_document] all attempts failed: {last_response.status_code}")
    return None


def update_document(collection_name: str, experiment_id: str, update_data: dict, agent_mode: str, token: str | None = None):
    active_token = _resolve_token(token)
    headers = _auth_headers(active_token)
    payload = {
        "updateData": update_data,
        "ExpId": experiment_id,
        "tool_type": agent_mode,
        "job_name": "codegenagent",
        "collection_name": collection_name,
    }

    response = requests.put(_BACKEND_UPDATE_URL, headers=headers, json=payload, timeout=60)
    # Retry across auth-blip windows (see fetch_document): a valid token is
    # intermittently 401-rejected for ~15-20s, then accepted again.
    last_auth_err = None
    for attempt in range(_AUTH_RETRY_ATTEMPTS + 1):
        auth_err = _is_auth_error(response)
        if auth_err:
            last_auth_err = auth_err
            print(f"[update_document] auth error (attempt {attempt + 1}/{_AUTH_RETRY_ATTEMPTS + 1}): {auth_err}")
            if attempt < _AUTH_RETRY_ATTEMPTS:
                time.sleep(_AUTH_RETRY_DELAY)
                response = requests.put(_BACKEND_UPDATE_URL, headers=headers, json=payload, timeout=60)
                continue
            raise RuntimeError(auth_err)
        if response.status_code not in (200, 201, 204):
            raise RuntimeError(f"backend_update failed: {response.status_code} {response.text}")
        if response.headers.get("content-type", "").startswith("application/json"):
            parsed = response.json()
            if isinstance(parsed, dict) and parsed.get("status") is False:
                raise RuntimeError(f"backend_update returned failure: {parsed}")
            return parsed
        return {"status": True, "message": "Backend update successful"}
    raise RuntimeError(last_auth_err or "update_document exhausted retries")


def upload_db(value, field_name: str, collection_name: str, conversation_id: str, agent_mode: str, token: str | None = None):
    """Write a single top-level field to the session document via /backendupdate."""
    update_data = {field_name: value}
    try:
        result = update_document(collection_name, conversation_id, update_data, agent_mode, token=token)
        return result
    except Exception as e:
        print(f"[upload_db] Error updating {field_name}: {e}")
        raise


# ───────────────────────────────────────────────
# Layer 2: 3-path router
# ───────────────────────────────────────────────

def _upload_db_main(
    output_info: dict,
    collection_name: str,
    conversation_id: str,
    status: str,
    agent_mode: str,
    token: str | None = None,
):
    """Fetch -> mutate -> upload_db.  Handles the 3 message_type branches.

    Serialized per conversation_id so concurrent writes never clobber each other.
    Different conv_ids run in parallel without contention.
    """
    lock = _get_conv_lock(conversation_id)
    with lock:
        return _upload_db_main_inner(
            output_info, collection_name, conversation_id,
            status, agent_mode, token=token,
        )


def _upload_db_main_inner(
    output_info: dict,
    collection_name: str,
    conversation_id: str,
    status: str,
    agent_mode: str,
    token: str | None = None,
):
    """Read-modify-write — always called under the conv lock.

    Retries once on transient fetch failures (backend propagation lag)
    before initialising a fresh document.  When no document exists yet
    (new conversation, or frontend hasn't created it), we seed an empty
    conversation so the first log entry is never silently dropped.
    """
    res = fetch_document(conversation_id, agent_mode, token=token)

    # Auth-blip that didn't clear after retries: SKIP this write entirely.
    # NEVER seed an empty doc on auth failure — that would clobber the real
    # conversation.  (fetch_document returns the _AUTH_FAILED sentinel.)
    if res is _AUTH_FAILED:
        print(f"[_upload_db_main] Skipping write for {conversation_id} — Boltzmann auth unavailable; will not risk clobbering.")
        return {"status": "skipped", "reason": "auth_unavailable"}

    # Fetch can return None when the backend hasn't propagated a recent
    # write yet — wait and retry once before creating from scratch.
    # NOTE: conversation may be [] (empty list) for new documents — that is
    # valid and we must NOT skip it. Only seed when the field is missing.
    if not res or res.get("conversation") is None:
        time.sleep(1)
        res = fetch_document(conversation_id, agent_mode, token=token)
        if res is _AUTH_FAILED:
            print(f"[_upload_db_main] Skipping write for {conversation_id} — Boltzmann auth unavailable; will not risk clobbering.")
            return {"status": "skipped", "reason": "auth_unavailable"}

    if not res or res.get("conversation") is None:
        print(f"[_upload_db_main] No existing document for {conversation_id} — creating initial document")
        res = {"conversation": [], "status": "pending", "active_request": True}

    msg_type = output_info.get("message_type")

    # ── GREETING ────────────────────────────────────────────────────────────
    if msg_type == "greeting":
        greeting_entry = {
            "message_type": "greeting",
            "message_text": output_info.get("content", ""),
        }

        res.setdefault("conversation", []).append(greeting_entry)

        try:
            upload_db(res["conversation"], "conversation", collection_name, conversation_id, agent_mode, token=token)
            upload_db("completed", "status", collection_name, conversation_id, agent_mode, token=token)
            upload_db(False, "active_request", collection_name, conversation_id, agent_mode, token=token)
        except Exception as exc:
            print(f"[_upload_db_main] greeting upload failed: {exc}")
            return {"status": "error", "reason": str(exc)[:200]}

        return res

    # ── GENERIC ─────────────────────────────────────────────────────────────
    elif msg_type == "generic":
        step = output_info.get("generation_step")
        content = output_info.get("content")
        if not step:
            return {"status": "skipped", "reason": "generic message missing generation_step"}
        if step in {"user_query", "generic_response"}:
            return {"status": "skipped", "reason": f"{step} is stored as a greeting/frontend message, not a workflow"}

        new_step = {
            "step_type": step,
            "content": f"<div><pre>{content}</pre></div>",
        }

        if step == "planning":
            workflow_id = str(uuid.uuid4())
            workflow_entry = {
                "message_type": "workflow-omics" if agent_mode == "omics" else "workflow",
                "workflow_id": workflow_id,
                "generation_steps": {step: new_step},
                "message_content": [],
            }

            res.setdefault("conversation", []).append(workflow_entry)
            try:
                upload_db(res["conversation"], "conversation", collection_name, conversation_id, agent_mode, token=token)
                upload_db("pending", "status", collection_name, conversation_id, agent_mode, token=token)
                upload_db(True, "active_request", collection_name, conversation_id, agent_mode, token=token)
            except Exception as exc:
                print(f"[_upload_db_main] generic/planning upload failed: {exc}")
                return {"status": "error", "reason": str(exc)[:200]}

        else:
            # Re-fetch to avoid stale data
            res = fetch_document(conversation_id, agent_mode, token=token)
            if not res or not isinstance(res, dict) or "conversation" not in res:
                print(f"[_upload_db_main] Cannot update step '{step}': no conversation document found")
                return {"status": "skipped", "reason": f"no conversation document for step {step}"}

            # Use the last entry in the conversation array directly
            workflow_msg = res["conversation"][-1]

            # If the last entry is not a workflow, create a new one
            if workflow_msg.get("message_type") not in ("workflow", "workflow-omics"):
                workflow_id = str(uuid.uuid4())
                workflow_msg = {
                    "message_type": "workflow-omics" if agent_mode == "omics" else "workflow",
                    "workflow_id": workflow_id,
                    "generation_steps": {step: new_step},
                    "message_content": [],
                }
                res.setdefault("conversation", []).append(workflow_msg)
            else:
                workflow_msg.setdefault("generation_steps", {})[step] = new_step

            try:
                upload_db(res["conversation"], "conversation", collection_name, conversation_id, agent_mode, token=token)
                upload_db("completed", "status", collection_name, conversation_id, agent_mode, token=token)
                upload_db(False, "active_request", collection_name, conversation_id, agent_mode, token=token)
            except Exception as exc:
                print(f"[_upload_db_main] generic/{step} upload failed: {exc}")
                return {"status": "error", "reason": str(exc)[:200]}

        return res

    # ── WORKFLOW ────────────────────────────────────────────────────────────
    elif msg_type in ("workflow", "workflow-omics"):
        res.setdefault("conversation", [])

        # If the last entry is a greeting, the previous run completed.
        # Always start a fresh workflow card — do NOT merge into a closed run.
        last_entry = res["conversation"][-1] if res["conversation"] else None
        if last_entry and last_entry.get("message_type") == "greeting":
            workflow_msg = None
        else:
            # Search BACKWARDS for the last workflow entry.  Using [-1] is wrong
            # when a greeting was appended after the last workflow step — that
            # would create a duplicate workflow card on the frontend.
            workflow_msg = None
            run_boundary_seen = False
            for entry in reversed(res["conversation"]):
                if entry.get("message_type") in ("greeting", "text"):
                    run_boundary_seen = True
                elif entry.get("message_type") in ("workflow", "workflow-omics"):
                    if run_boundary_seen:
                        workflow_msg = None
                    else:
                        workflow_msg = entry
                    break

        if workflow_msg is None:
            workflow_id = str(uuid.uuid4())
            workflow_msg = {
                "message_type": msg_type,
                "workflow_id": workflow_id,
                "generation_steps": {},
                "message_content": [],
            }
            res["conversation"].append(workflow_msg)
            # New query → new workflow card → reset status to pending.
            # The previous run's greeting set status="completed" — if we
            # don't reset it, the frontend shows the run as already done.
            res["status"] = "pending"

        # ── Validation + Dedup ─────────────────────────────────────────────
        new_entry = output_info["message_content"]
        mc = workflow_msg.setdefault("message_content", [])
        entry_status = new_entry.get("status")
        entry_coll = new_entry.get("collection_name")
        entry_exp = new_entry.get("experiment_id")

        # Guard: Validate experiment_id format.  Real Boltzmann doc_ids are
        # 24-char hex strings.  Fabricated values like "random_ab_20" are
        # silently rejected — the LLM must never invent IDs.
        if entry_exp is not None:
            if (not isinstance(entry_exp, str)
                    or len(entry_exp) != 24
                    or not all(c in "0123456789abcdefABCDEF" for c in entry_exp)):
                print(f"[_upload_db_main] Rejecting entry with invalid experiment_id: {entry_exp!r}")
                return res

        # Dedup: skip if an identical entry already exists in this workflow
        # card (same collection_name + experiment_id + status).  Prevents
        # duplicates when the LLM calls fetch_status (auto-logs terminal)
        # AND manually calls log_workflow_update for the same completion.
        # Planning entries are exempt — the LLM may legitimately adjust its
        # plan, and each plan carries different intent in its description.
        if entry_status and entry_status != "planning":
            is_dup = any(
                e.get("collection_name") == entry_coll
                and e.get("experiment_id") == entry_exp
                and e.get("status") == entry_status
                for e in mc
            )
            if is_dup:
                # Don't append the duplicate — just re-upload the current
                # state so status/active_request stay consistent.
                try:
                    upload_db(res["conversation"], "conversation", collection_name, conversation_id, agent_mode, token=token)
                    upload_db(res["status"], "status", collection_name, conversation_id, agent_mode, token=token)
                    upload_db(True, "active_request", collection_name, conversation_id, agent_mode, token=token)
                except Exception as exc:
                    print(f"[_upload_db_main] workflow dedup upload failed: {exc}")
                return res

        # Insert planning entries at the TOP so plans always appear before
        # pending/completed steps. Everything else appends normally.
        if entry_status == "planning":
            mc.insert(0, new_entry)
        else:
            mc.append(new_entry)
        res["status"] = status

        # Keep active_request=True until the greeting is logged — the
        # run is NOT complete just because a tool finished (the LLM
        # still has to download results, format the greeting, etc.).
        # The greeting branch and the generic branch handle the final
        # active_request=False transition.
        try:
            upload_db(res["conversation"], "conversation", collection_name, conversation_id, agent_mode, token=token)
            upload_db(res["status"], "status", collection_name, conversation_id, agent_mode, token=token)
            upload_db(True, "active_request", collection_name, conversation_id, agent_mode, token=token)
        except Exception as exc:
            print(f"[_upload_db_main] workflow upload failed: {exc}")
            return {"status": "error", "reason": str(exc)[:200]}

    else:
        print(f"[_upload_db_main] Unknown message_type: {msg_type}, skipping")

    return res


# ───────────────────────────────────────────────
# Layer 3: High-level entry point
# Called by both tools.py (agent-driven) and server.py (server-driven)
# ───────────────────────────────────────────────

def log_workflow_update(
    agent_mode: str = "platform_tools",
    step_type: str = None,
    description: str = None,
    message_type: str = None,
    status: str = None,
    collection_name: str = None,
    experiment_id: str = None,
    generation_step: str = None,
    generation_content: str = None,
    final_status: str = None,
    conv_id: str = None,
    token: str | None = None,
    gcp_paths: list[str] | None = None,
):
    """Log workflow updates, generation_steps, or greetings.

    Supports two calling patterns:
    - Server-driven: pass conv_id and token explicitly.
    - Agent-driven: conv_id/token read from os.environ as fallback.
    """
    conversation_id = conv_id or os.getenv("conv_id")
    if not conversation_id:
        print("[log_workflow_update] Skipping — no conv_id")
        return None

    active_token = _resolve_token(token)

    # ── GENERIC ─────────────────────────────────────────────────────────────
    if message_type == "generic":
        update_payload = {
            "message_type": "generic",
            "generation_step": generation_step,
            "content": generation_content,
        }
        return _upload_db_main(
            update_payload,
            CONVERSATION_COLLECTION,
            conversation_id,
            final_status,
            agent_mode,
            token=active_token,
        )

    # ── GREETING ────────────────────────────────────────────────────────────
    elif message_type == "greeting":
        update_payload = {
            "message_type": "greeting",
            "generation_step": generation_step,
            "content": generation_content,
        }
        return _upload_db_main(
            update_payload,
            CONVERSATION_COLLECTION,
            conversation_id,
            final_status,
            agent_mode,
            token=active_token,
        )

    # ── WORKFLOW / WORKFLOW-OMICS ──────────────────────────────────────────
    elif message_type in ("workflow", "workflow-omics"):
        tz = ZoneInfo("Asia/Kolkata")
        timestamp = datetime.now(tz).isoformat()

        workflow_step_entry = {
            "description": description,
            "collection_name": collection_name,
            "experiment_id": experiment_id,
            "status": status,
            "step_type": step_type,
            "timestamp": timestamp,
            "final_status": final_status,
        }
        if gcp_paths:
            workflow_step_entry["gcp_paths"] = gcp_paths

        workflow_doc = {
            "message_type": message_type,
            "message_content": workflow_step_entry,
        }

        if description:
            workflow_doc["message_text"] = f"<div><p>{description}</p></div>"

        return _upload_db_main(
            workflow_doc,
            CONVERSATION_COLLECTION,
            conversation_id,
            status,
            agent_mode,
            token=active_token,
        )

    else:
        print(f"[log_workflow_update] Invalid message_type: {message_type}")
        return None
