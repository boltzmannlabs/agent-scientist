# Formulation Optimization Report

## Executive summary
**Objective:** …

**Best evaluated candidate:** … (generation / exact recipe ID)

**Baseline comparison:** …

**Estimated cost basis and change:** …

**Evidence status:** Model prediction / measured / mixed. **Experimental validation pending** where applicable.

## Run Summary
**Objective:** …

**Simulations performed:** model — generation / recipe ID / run ID …

**Optimization steps:** …

**Parameters compared:** …

**Baseline → selected candidate:** …

**Best-performing evaluated outcome:** … (or “not determined” with reason)

| Indicator | Parameter | Baseline → optimized | Basis / note |
|---|---|---|---|
| Changed / Improved / Unchanged / Needs validation | … | … → … | … |

**Experimental validation status:** …

## Agent decisions
| Question | Agent-selected option | Reason based on objectives and inputs | Assumptions / evidence |
|---|---|---|---|
| … | … | … | … |

## Problem and decision criteria
In plain language, the user wants … Constraints … Target specifications … Hard requirements … Preferences … Metric directions and units …

## Baseline V0
| Ingredient | Grade/source | Concentration | Quantity and basis | Process note | Evidence |
|---|---|---:|---:|---|---|
| … | … | … | … | … | … |

Baseline performance and cost coverage: … (state unknowns; never fill with zero).

## Generation-wise recipe evolution
| Generation | Formulation / recipe ID and revision | Ingredient and grade | Concentration | Quantity / basis | Change from previous version | Rationale |
|---|---|---|---:|---:|---|---|
| V0 | … | … | … | … | Reference | … |
| V1 | … | … | … | … | … | … |

## Simulation coverage and exact mapping
| Objective / criterion | Model and scenario | Generation / formulation | Recipe ID/revision | Run ID | Inputs and shared conditions | Evidence / assumptions |
|---|---|---|---|---|---|---|
| … | … | … | … | … | … | … |

For every simulation, add an interpretation block:

**Purpose:** What was evaluated?

**Results:** What values/trends were produced, with units?

**Meaning:** What do the results mean in plain language?

**Target/reference:** How do they compare with specification and V0? Use “not assessed” if unavailable.

**Drivers:** Which changes are supported by evidence? Which explanations remain hypotheses?

**Next:** What should be measured, simulated or changed next?

**Status:** Measured / user-provided / literature-reported / model-predicted / assumed / unknown. **Experimental validation pending** when appropriate.

## Cost and grade comparison
| Generation | Ingredient / grade / supplier | Quantity | Unit price and source/date | Raw-material contribution | Manufacturing and other costs | Total cost/basis | Savings vs V0 |
|---|---|---:|---|---:|---:|---:|---:|
| … | … | … | … | … | … | … | … |

Describe unavailable quotations, cost assumptions and trade-offs. Do not label a subtotal as total cost.

## Visual comparison
Include readable generation-wise performance trends, target bands, raw-material/total-cost comparison and baseline-versus-best summary where data supports them. Label axes, units, generations and evidence type. Missing data is a gap, not zero.

## Ranking and recommendation
| Rank | Candidate | Feasibility against stated criteria | Predicted performance | Cost | Trade-off / confidence |
|---:|---|---|---|---:|---|
| … | … | … | … | … | … |

State best overall and best cost-effective evaluated candidates when supported. Explain why the recommendation follows from the user's priorities. Call modeled target misses “did not meet the modeled target”; do not call an untested prediction an experimental failure or declare a formulation unsuitable solely because validation is pending.

## Optimization evolution
Explain what changed at each step, why, what the model predicts improved or deteriorated, and what remains unresolved. Distinguish evidence-backed drivers from hypotheses.

## Suggested experimental validation
Specify candidate/reference batches, measurements, conditions, replicates or controls as appropriate, and which uncertainty each test resolves. Mark all predictions **To be experimentally confirmed**. Do not imply laboratory work has occurred.

## Limitations and provenance
List unsupported criteria, missing inputs, model domain limits, assumptions, source/date, units, model/package versions and exact saved record IDs.
