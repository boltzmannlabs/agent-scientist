# Discovery source families and their honest use

- **GitHub**: repository quality, commit pinning, LICENSE at commit, issues/CI. A repo existing is not evidence of
  usability.
- **Hugging Face**: model cards, checkpoint artifacts, checksums, license tags, inference snippets. Verify the
  artifact actually downloads under the stated license.
- **PubMed / Europe PMC**: peer-reviewed performance claims with cohort/endpoint context; use for benchmark evidence
  rows, not for weights verdicts.
- **bioRxiv**: preprint evidence is legitimate but marked PREPRINT (not peer-reviewed) in every citation.
- **Zenodo**: versioned archived artifacts with DOIs; prefer for checkpoint URLs when offered.
- **Official model documentation**: input/output schemas, official inference instructions — the spec's
  `official_inference_instructions` must come from the project's own docs/examples, not paraphrased from memory.
- **Bioinformatics software repositories** (bioconda, bio.tools, Debian-med): installation sanity, maintained
  recipes.

Rules: cite access dates; pin commits before citing qualities; prefer primary sources over aggregators; never
present an aggregator's description as the project's own claim; a search that found nothing in a family is recorded
as such with the query used.
