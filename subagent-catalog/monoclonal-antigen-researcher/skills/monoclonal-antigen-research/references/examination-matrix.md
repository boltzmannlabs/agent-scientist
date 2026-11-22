# Antigen examination matrix

Inspect all 18 domains. For each, record what was checked, source scope, findings, disagreement, uncertainty and the specific workflow implication. The matrix is a research framework, not a requirement to invent a positive answer for every field.

| Domain ID | Examine | Consequence to explain |
|---|---|---|
| identity | Species, accession and record version, synonyms, gene/protein distinction, isoforms, supplied-file identity | Whether all sources and proposed inputs refer to the same intended antigen |
| construct | Full sequence versus mature chain, signal/propeptides, cleavage, truncations, missing termini/loops, mutations, purification tags and numbering namespaces | Which exact sequence/coordinates and residue maps the workflow must preserve |
| topology | Domain boundaries, repeats, transmembrane segments, extracellular/intracellular orientation and domain connectivity | Whether proposed binder access and structural input are physically relevant |
| presentation | Soluble versus membrane presentation, density, orientation, neighboring domains, crowding and native versus isolated-domain accessibility | Whether an exposed surface in a simplified construct represents the requested biological setting |
| assembly | Biological assembly versus asymmetric unit, stoichiometry, oligomer interfaces, cofactors, ligands and interaction partners | Which chains/context must be retained and where omitted partners could alter accessibility |
| conformations | Apo/ligand/partner-bound states, alternate conformations, disorder, flexible linkers, experimentally supported motion and uncertain regions | Which states need consideration and where a single structure is an inadequate representation |
| modifications | Experimentally supported and predicted glycosylation separately, observed occupancy, unresolved glycans, disulfides and other relevant processing | Where chemical context could change shape or accessibility; missing coordinates do not prove absence |
| structures | Experimental source and method, native coordinates, coverage/alignment, local density/validation, missing atoms, mutations, biological assembly and prediction confidence | Which model is admissible, what preparation changes, and which regions remain uncertain |
| epitopes | Mapped sites, complex contacts, competition groups, linear/conformational evidence, predicted sites, accessibility in relevant states | Distinguish direct epitope evidence from competition inference and modeling; preserve chain-qualified identifiers |
| function | Physiological function, ligands/partners, binding versus modulation, desired endpoint and context-dependent mechanism | Which evidence supports the requested result and which endpoint requires independent measurement |
| specificity | Paralogues/homologues, related domains, evidence-backed cross-reactivity, off-target panels and assay limitations | What must be distinguished and what specificity remains untested; similarity alone is not cross-binding |
| variation | Isoform/allelic variation, naturally occurring substitutions and coverage of relevant sequence populations | Which sequences the request intends to recognize or distinguish; sequence conservation is not functional proof |
| expression | Tissue/cell/subcellular distribution, evidence type, mature-protein surface presentation versus transcript abundance, context dependence | Whether expression data support accessible protein in the requested setting |
| known_binders | Reported binders and paired sequence provenance, format/valency, exact reference versus scaffold, structural complexes, affinities and competition evidence | Which baseline is defensible and which measurements are comparable; absent paired sequence stays missing |
| assays | Endpoint, native/recombinant construct, format/valency, assay orientation, concentrations/conditions as reported, controls, sample size and uncertainty | Separate affinity, avidity, kinetic, binding, specificity and functional outcomes |
| reagent_quality | Reported purity, heterogeneity, aggregation, folding/assembly, expression-system differences, tags, preparation effects and lot/record identity | Whether reagent artifacts could explain observations or make reference/candidate comparisons misleading |
| biological_relevance | Normal function, tissue accessibility, supported liabilities of the requested mechanism and limitations of available models | Which interpretation and follow-up evidence are needed before translational claims |
| gaps | Missing records, unresolved identities, source conflicts, unavailable searches, stale observations and consequential assumptions | Which stages can proceed, which remain conditional, and what specific evidence would resolve each decision |

Research reference controls, experimental conditions and alternative explanations alongside favorable findings. Avoid assuming that sequence similarity, high model confidence, many predicted contacts or an isolated-domain assay establishes native binding or the requested function.
