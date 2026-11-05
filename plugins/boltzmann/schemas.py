"""Schemas for the tools-only Boltzmann integration."""

SCHEMAS = [
    {
        "name": "boltzmann_submit",
        "description": (
            "Submit one validated platform-tools job. Use the exact job name and payload "
            "from the selected Boltzmann skill module. First load skill_view(name='boltzmann:tools'). "
            "Never resubmit after an ambiguous timeout."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "job_name": {
                    "type": "string",
                    "description": "Exact job_name from the selected Boltzmann contract.",
                },
                "experiment_data": {
                    "type": "object",
                    "description": "Complete payload matching that job's documented schema.",
                },
                "experiment_name": {
                    "type": "string",
                    "description": "Optional platform label. Omit it for an automatically generated readable name, or pass the exact name requested by the user.",
                },
                "allow_partial_validation": {
                    "type": "boolean", "default": False,
                    "description": "Set true only after the user explicitly approves the reported unchecked aspects and possible service charges. Never overrides invalid inputs or authorization.",
                },
            },
            "required": ["job_name", "experiment_data"],
            "additionalProperties": False,
        },
    },
    {
        "name": "boltzmann_status",
        "description": (
            "Poll an existing Boltzmann platform-tools job. Use the exact job_name and doc_id "
            "returned by boltzmann_submit. One bounded check returns promptly; durable monitoring "
            "continues pending/running jobs without an overall queue deadline. Polling never creates another job."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "job_name": {"type": "string"},
                "doc_id": {"type": "string"},
                "output_folder": {
                    "type": "string",
                    "description": "Optional local results directory used by the active session.",
                },
            },
            "required": ["job_name", "doc_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "boltzmann_download",
        "description": "Download one output artifact from a completed Boltzmann job.",
        "input_schema": {
            "type": "object",
            "properties": {
                "download_url": {
                    "type": "string",
                    "description": "Signed HTTPS URL returned by boltzmann_status.",
                },
                "output_folder": {
                    "type": "string",
                    "description": "Local directory in which to save the artifact.",
                },
            },
            "required": ["download_url", "output_folder"],
            "additionalProperties": False,
        },
    },
    {
        "name": "boltzmann_upload",
        "description": "Upload one validated local input file to Boltzmann platform storage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "local_path": {
                    "type": "string",
                    "description": "Absolute path to the already validated input file.",
                },
                "job_name": {"type": "string", "description": "Exact scientific job name from tool-contracts.v1.json."},
                "input_field": {"type": "string", "description": "Exact payload field this file will populate."},
                "experiment_data": {"type": "object", "description": "Reviewed values needed for mode-dependent file validation; never include credentials."},
                "allow_partial_validation": {"type": "boolean", "default": False,
                    "description": "True only after explicit user approval of the returned partial-validation warnings."}
            },
            "required": ["local_path", "job_name", "input_field"],
            "additionalProperties": False,
        },
    },
    {
        "name": "boltzmann_fetch_tool_log",
        "description": (
            "Read a durable platform-tools record using job_name and the returned experiment_id. "
            "Resolves the documented collection automatically; never guess a collection. "
            "This is diagnostic and never submits or mutates a job."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "collection": {
                    "type": "string",
                    "description": "Optional verified collection for existing callers. If job_name is supplied, this must match its documented collection.",
                },
                "job_name": {
                    "type": "string",
                    "description": "Exact submitted job name; resolves the diagnostic collection from the installed contract.",
                },
                "experiment_id": {
                    "type": "string",
                    "description": "Exact document ID returned by the current workflow.",
                },
            },
            "required": ["experiment_id"],
            "additionalProperties": False,
        },
    },
]

# Native SCI registration consumes `parameters`, not the MCP `input_schema` key.
for _schema in SCHEMAS:
    _schema["parameters"] = _schema.pop("input_schema")
