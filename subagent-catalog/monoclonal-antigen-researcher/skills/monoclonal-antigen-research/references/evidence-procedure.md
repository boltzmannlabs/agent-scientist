# Evidence retrieval and adjudication

Start from supplied artifacts and identity constraints. Use UniProt for versioned sequence and evidence-qualified annotations, RCSB PDB/wwPDB for native structural records and validation, and the current SAbDab2 service for antibody/complex records when relevant. Confirm actual chain sequences and construct mapping rather than relying on accession/name matches alone. Read source definitions: a curated annotation and an experimental measurement have different evidentiary scope.

Search the exact biological question and key aliases; cover identity, native context, existing binding/functional evidence and contradictory or negative results. Search newly released evidence since the previous review as well as foundational records. Log date, query, channel, record versions, access/read scope and outcome. An inaccessible database is not an empty result. An abstract supports only what it states; retain the underlying table/figure/record locator for numerical claims.

For each source record retain URL/accession, accessed date, record/version or revision, publisher, source type, lawful local artifact path and SHA-256, read scope and exact claim locator. Archive native machine-readable records where available. If full text cannot be retained, retain concise scoped notes identifying the source and what was actually inspected; notes do not authenticate the original source. Keep copyrighted bulk text out of reusable instructions.

Domain statuses:

- `supported`: at least one cited source supports the bounded finding; qualify experimental, inferred, predicted or user-supplied basis in the text.
- `uncertain`: evidence exists but does not resolve the relevant conclusion.
- `conflicting`: source claims disagree; cite the conflict and decision consequence.
- `not_found`: a documented scoped search found no adequate evidence; this is not proof of biological absence.
- `not_applicable`: explain why the domain does not apply to this request.
- `not_assessed`: research has not been completed or access failed; identify the missing step.

Keep observation and interpretation separate. Conflicts can arise from isoform, construct, state, expression system, assay, valency, numbering or source-date differences. Resolve those distinctions when evidence allows; otherwise retain separate records. Record which downstream stage IDs each uncertainty affects. Do not block unrelated research because one execution prerequisite is missing.

For structure review, native and prepared coordinates are distinct artifacts. Record sequence/construct alignment, assembly choice, missing residues/atoms, tags, model uncertainty and any crop/repair/relaxation. Cropping is optional and needs a reversible residue map plus review in the relevant full context. Experimental-only constraints cannot silently become prediction-based inputs.

Return a concise decision narrative with the dossier: admissible antigen representation, inaccessible/uncertain context, reference applicability, evidence gaps, and effects on tool compatibility. Evidence completeness and scientific readiness remain separate judgments.
