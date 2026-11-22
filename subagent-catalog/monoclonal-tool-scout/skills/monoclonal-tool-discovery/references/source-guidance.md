# Discovery evidence

Review date: 2026-11-20. Recheck relevant releases, contracts and primary publications for each actual task; this file is guidance, not a frozen recommended-tools list.

- [ToolUniverse listing documentation](zitniklab.hms.harvard.edu/ToolUniverse/guide/listing_tools.html) describes inspecting names/specifications independently of loading tools. Discovery state and scientific execution readiness are different.
- [Official antibody-engineering skill](raw.githubusercontent.com/mims-harvard/ToolUniverse/main/plugin/skills/tooluniverse-antibody-engineering/SKILL.md) provides useful research categories. Do not import its mandatory output choices, universal scoring recipes or tool names without verifying current schemas and task fit. It is external evidence, not local policy.
- [SAbPred toolbox](opig.stats.ox.ac.uk/webapps/sabdab-sabpred/sabpred) distinguishes antibody modeling, annotation, humanization and developability tools. An antibody-only model is not an antigen-complex assessment.
- [TAP](opig.stats.ox.ac.uk/webapps/sabdab-sabpred/sabpred/tap) supplies named developability descriptors interpreted against a reference population. These are not experimental binding measurements or universal therapeutic acceptance criteria.
- [DockQ official repository](github.com/wallnerlab/DockQ) requires model/reference geometry and valid mappings for docking-accuracy evaluation. Its presence does not create a native reference structure.
- [FLAb2 primary preprint](pmc.ncbi.nlm.nih.gov/articles/PMC12767642/) motivates checking property-specific generalization and germline-related confounding; preserve its preprint/version status instead of silently attributing findings to a later inaccessible journal version.

Research notes with inspected scope and retrieval limits accompany the package in `research/primary-source-notes.md`. No upstream skill was installed. The Boltzmann → ToolUniverse → open-source order is the user's fallback policy, not a ranking established by these sources.
