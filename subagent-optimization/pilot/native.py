"""Instrumented advisory policies on an existing Agent Scientist runtime.

Factory-created parents must be fresh, correctly scoped and tool-restricted.
This module does not install definitions, resolve keys, change profiles or submit
science. The specialist arm calls the named native delegation rail explicitly.
"""
from copy import deepcopy
import json
import time

from specialist.advisor import parse_answer


class RoutingError(RuntimeError):
    pass


class FixtureDecisionDriver:
    """Explicit test callback. Never evidence of a native model decision."""
    def __init__(self, decide):
        self.decide = decide

    def choose(self, arm, packet):
        specialist = arm == "base_algorithm_specialist"
        return {"advice": self.decide(arm, deepcopy(packet)), "evidence_kind": "fixture",
                "runtime": {"specialist_invoked": specialist, "specialist_name": "smallmol-investigation" if specialist else None,
                            "response_source": "fixture"},
                "usage": {"all_usage": "synthetic fixture; no model inference"}}


class NativeDecisionDriver:
    def __init__(self, parent_factory, runtime_identity, *, response_source="model", specialist_name="smallmol-investigation"):
        if response_source not in {"model", "fixture"}:
            raise ValueError("Explicit model/fixture response source required")
        self.parent_factory = parent_factory
        self.runtime_identity = deepcopy(runtime_identity)
        self.response_source = response_source
        self.specialist_name = specialist_name

    def choose(self, arm, packet):
        # Import only inside the real owning host; portable/offline use has no
        # dependency on its SDK, installed profiles or provider credentials.
        from run_agent import AIAgent
        from agent.specialist_policy import SpecialistPolicy, specialist_scope
        from tools.delegate_tool import delegate_task
        from sci_cli.config import load_config_readonly
        from pilot.runner import digest
        # The exact role is supplied once by the native child context or the
        # main policy prompt below, rather than repeated inside assignment DATA.
        transmitted = deepcopy(packet)
        role = transmitted.pop("specialist_definition", None)
        transmitted["scientific_role_binding"] = ({k: role[k] for k in ("name", "sha256") if k in role}
                                                   if isinstance(role, dict) else None)
        text = json.dumps(transmitted, sort_keys=True, separators=(",", ":"), allow_nan=False)
        limit = packet.get("context_limits", {}).get("maximum_assignment_chars", 24000)
        if type(limit) is not int or not 1 <= limit <= 262144:
            raise RoutingError("Invalid frozen assignment-data allowance")
        if len(text) > limit:
            raise RoutingError("Decision context exceeds the tested allowance; no evidence was silently dropped")
        parent = self.parent_factory(arm)
        if not isinstance(parent, AIAgent):
            raise TypeError("Actual native AIAgent instance required")
        specialist = arm == "base_algorithm_specialist"
        expected_tools = {"delegate_task"} if specialist else set()
        try:
            identity = {"model": parent.model, "provider": parent.provider}
            if identity != self.runtime_identity:
                raise RoutingError("Native model/provider differs from the registered pilot configuration")
            policy = getattr(parent, "_specialist_policy", None)
            names = {t["function"]["name"] for t in parent.tools}
            if (not isinstance(policy, SpecialistPolicy) or set(policy.tools) != expected_tools
                    or names - expected_tools or (specialist and set(policy.children) != {self.specialist_name})):
                raise RoutingError("Fresh advisory-only parent with exact tool/child grants required")
            # A separate delegation model would confound the first comparison.
            cfg = load_config_readonly().get("delegation", {})
            if specialist and any(cfg.get(k) and cfg[k] != identity[k] for k in ("model", "provider")):
                raise RoutingError("Delegation model/provider override does not match this pilot")
            if specialist and any(cfg.get(k) is not None and cfg[k] != "" and cfg[k] != {} and cfg[k] != [] for k in
                                  ("temperature", "reasoning_effort", "extra_body", "request_kwargs", "request_overrides",
                                   "fallback_providers", "base_url", "api_mode")):
                raise RoutingError("Separate delegation inference settings must be removed or explicitly qualified before comparison")
            expected = packet.get("specialist_definition")
            if not isinstance(expected, dict):
                raise RoutingError("Freeze the scientific role definition before native decisions")
            if specialist:
                from agent.specialist_store import load
                saved = load(self.specialist_name)
                for field in ("name", "purpose", "instructions", "output", "tools", "skills", "skill_files", "sources", "children",
                              "max_iterations", "timeout_seconds"):
                    current = getattr(saved, field)
                    if isinstance(current, tuple): current = list(current)
                    if current != expected[field]:
                        raise RoutingError("Saved specialist differs from the frozen scientific role")
            goal = ("Return one plain advisory JSON object using exactly the supplied advice_fields. "
                    "Copy input_digest. Use scientific_claim=hypothesis_only. You may recommend one eligible library, "
                    "request information or abstain. Keep all original rules. This is a conditional investigation, "
                    "not permission to execute tools or assert measured potency.")
            started = time.monotonic()
            with specialist_scope(policy):
                if specialist:
                    raw = delegate_task(tasks=[{"specialist": self.specialist_name, "goal": goal, "context": text}],
                                        parent_agent=parent)
                    native = json.loads(raw) if isinstance(raw, str) else raw
                    results = native.get("results", []) if isinstance(native, dict) else []
                    if (len(results) != 1 or results[0].get("status") != "completed"
                            or results[0].get("specialist") != self.specialist_name):
                        raise RoutingError("Named specialist did not complete; no main-only fallback is accepted")
                    output = results[0].get("summary")
                    parent_calls = "not called: the pilot invokes the bounded delegation step explicitly"
                else:
                    common_role = ("Scientific role: " + expected["purpose"] + "\n" + expected["instructions"]
                                   + "\nExpected output: " + expected["output"])
                    native = parent.run_conversation(common_role + "\n" + goal + "\nAssignment data:\n" + text)
                    output = native.get("final_response")
                    parent_calls = "actual API attempts not exposed here; retain native trace and unknown usage"
            advice = parse_answer(output)
            # Keep full native trace private, with caller-visible content binding.
            trace = {k: native[k] for k in ("messages", "results", "usage", "status") if k in native}
            return {"advice": advice,
                    "evidence_kind": "native_agent_runtime" if self.response_source == "model" else "fixture",
                    "runtime": {**identity, "specialist_invoked": specialist,
                                "specialist_name": self.specialist_name if specialist else None,
                                "native_trace": trace, "native_trace_digest": digest(trace),
                                "assignment_digest": packet["input_digest"],
                                "transmitted_assignment_digest": digest(transmitted),
                                "transmitted_assignment_chars": len(text),
                                "transmitted_assignment_chars_limit": limit,
                                "response_source": self.response_source, "elapsed_seconds": time.monotonic() - started,
                                "model_provider_verified": True,
                                "sampling_settings": "separate delegation overrides refused; full inference-setting and fresh-session equivalence is a caller assumption, not verified",
                                "policy_scope": "forced bounded native decision; not unrestricted discovery or natural routing"},
                    "usage": {"parent": parent_calls, "reported_native_usage": native.get("usage"),
                              "total_parent_child_tokens_and_cost": "unknown unless present in native usage/trace; not zero"}}
        finally:
            parent.close()


def parent_factory(host_options, *, timeout_seconds=180):
    """Build advisory parents in the caller's existing, already configured profile.

    host_options can contain inference credentials in memory. They are never
    persisted to a pilot protocol. No definition is installed or enabled here.
    """
    options = dict(host_options)
    def make(arm):
        from run_agent import AIAgent
        from agent.specialist_policy import SpecialistPolicy, specialist_scope
        from sci_constants import get_sci_home
        specialist = arm == "base_algorithm_specialist"
        grants = frozenset({"delegate_task"}) if specialist else frozenset()
        children = frozenset({"smallmol-investigation"}) if specialist else frozenset()
        policy = SpecialistPolicy("pilot-advisory-parent", str(get_sci_home().resolve()), "pilot-advisory-v1",
                                  grants, frozenset(), children, ("pilot-advisory-parent",), time.monotonic() + timeout_seconds)
        kwargs = {**options, "enabled_toolsets": ["delegation"] if specialist else [],
                  "quiet_mode": True, "skip_context_files": True, "skip_memory": True, "max_iterations": 4}
        with specialist_scope(policy):
            agent = AIAgent(**kwargs)
        agent.run_budget_seconds = timeout_seconds
        return agent
    return make
