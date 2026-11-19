# Application routing and native endpoint boundaries

Task IDs describe application requirements, not claims of runnable adapters. Use the exact parent-supplied versioned task specification.

| ID | Application | Native evidence needed | Do not substitute |
| --- | --- | --- | --- |
| 001 | General CRISPR routing | Confirm modality, target and system, then choose a defined task | A routing choice is not activity validation |
| 002 | Nuclease knockout | Matched nuclease activity, transcript/CDS coverage, DNA specificity, conditional indel endpoint when supported | Conditional frameshift fraction is not unconditional knockout probability |
| 003 | Therapeutic in-vivo research | System-matched on/off-target evidence and declared variant/population scope | No delivery prediction, clinical recommendation or safety guarantee |
| 004 | Variant correction router | Verified assembly/alleles and BE/PE/HDR-specific measured outcomes | No allele selectivity inferred from sequence consistency alone |
| 005 | Base editing | Exact editor/cell model; intended vs any-edit efficiency; genotype and bystander evidence separately | BE4 is not BE4max; any-edit efficiency is not purity |
| 006 | Prime editing | Exact PE system/scaffold/cell features, PBS/RTT construction, matched measured labels | PRIDICT1 is not PRIDICT2; unintended-edit accuracy is not purity; PE2 is not PE3 |
| 007 | CRISPRi/a | dCas effector context, versioned TSS, native chromatin/phenotypic inputs | Nuclease activity and fixed TSS windows are not learned repression/activation efficacy |
| 008 | Epigenome editing | Matched durable-silencing or methylation phenotype | CpG counts and TSS distance do not predict functional silencing |
| 009 | Cas13 RNA targeting | Versioned transcript, declared Cas13 system, native accessibility/activity, transcriptome specificity | DNA specificity or collateral-cleavage prediction from an unrelated score |
| 010 | Diagnostics | Approved non-pathogen/contrived assay; exact nuclease, representation and measured fluorescence/detection labels | Pathogen guide design/optimization is review-only; no clinical sensitivity from correlation |
| 011 | Pooled libraries | Guide endpoints plus library-level screen outcomes/diversity/controls | Guide correlation does not prove essential-gene detection or screen power |
| 012 | Plant editing | Approved species adapter, actual reference and species/assay-matched phenotype | Inactive by default; human labels cannot validate plant editing |
| 013 | Microbial CRISPR | Confirmed non-pathogenic strain/reference and bacterial endpoint | Mammalian efficacy cannot replace bacterial evidence; CRISPRi depletion is not nuclease knockout |

Established completed model/endpoint examples in the originating project were RS3 Sequence, CRISPRon v1 comparative cohorts, native CFD2016 assayed-site ranking, BE-Hive BE4 any-edit efficiency, PRIDICT2.0 grouped OOF, DeepPrime matched PE2, and RFcombined refit evaluation. This statement is context only: inspect current approved evidence manifests on the recipient machine; this package does not contain those tools, weights or benchmark data.
