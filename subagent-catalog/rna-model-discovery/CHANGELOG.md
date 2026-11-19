# Changelog

## 1.1.1 — complete the v1.1 contract

The 1.1.0 edit was incomplete (the discovery specialist caught it live: the staged schema/validator still
rejected local repository paths and lacked the WEIGHTS_VERIFIED_LOCAL enum in the schema). Both files now fully
implement the contract; verified by a local-path spec passing structural and strict validation.

## 1.1.0 — local/fixture integration support

E2E testing through rna-agent (bench, 2026-11-17) surfaced an honest-blocker: the v1 spec contract could not
represent a parent-supplied local fixture without inventing metadata — local repository paths failed the URL
pattern, fixture models have no publication, and "public availability unverified" had no weights enum value. The
discovery specialist correctly refused to fabricate a pass. This revision extends the contract honestly:

- repository_url accepts http(s)/file URLs and absolute local paths.
- publication_references are documented as provenance references: a DOI/URL or an explicit parent-supplied fixture
  provenance statement — never a fabricated citation.
- weights_availability adds WEIGHTS_VERIFIED_LOCAL: artifact checksum verified locally, public availability
  unverified (offline/fixture integrations). Registry semantics unchanged: WEIGHTS_AVAILABLE still requires
  verified public availability.

No scientific claims changed; fixture contracts untouched.

## 1.0.0 — initial package

Discovery/evaluation/spec leaf with evidence-attached multi-criteria evaluation, weights-availability verdicts,
ModelIntegrationSpec v1 contract, shared registry CLI (reader states), preflight routing and unit tests.
