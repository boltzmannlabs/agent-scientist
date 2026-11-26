# Complete visualization of a discussed reaction

## Define the scope

Identify each reactant and the product mentioned in the current exchange. Use
conditions, catalysts and prior clarifications already present in the conversation.
For an equation request, depict the overall reactant-to-product transformation.
For an electron-pushing request, depict the elementary steps of that reaction.
Do not expand into a retrosynthesis tree or a route overview. The existing
retrosynthesis tool owns those visualizations. If it has already supplied a route,
expand only the reaction or reactions selected or discussed by the user.

## Resolve chemistry before drawing

Compare functional groups and required bond changes. Check whether the stated
reactants and conditions support the requested transformation. Ask a focused
clarification if a missing reagent, condition, precursor or product identity
changes the mechanism. Show the specific discrepancy in simple language. A target
alone cannot establish the route or mechanism, and an unspecified E/Z or R/S
configuration stays unspecified.

Do not invent a preceding reaction to repair incompatible inputs. For example,
a terminal vinyl heterocycle and a beta-ketophosphonate are insufficient to specify
an HWE coupling to an enone. The conventional coupling needs a carbonyl partner.
Ask whether the intended reactant was the corresponding aldehyde and which
conditions apply. Do not silently replace the vinyl compound, select a cleavage
reaction, draw a new synthetic route or describe guessed conditions as supplied.
This example guides ambiguity handling, not automatic reaction classification.

## Cover the requested reaction

Before rendering, associate each necessary mechanistic event with a panel:

- Reactant activation when required, followed by the actual coupling or main
  transformation rather than stopping at activation.
- Every participating substrate at its point of reaction, with nucleophile and
  electrophile identified by their actual structures and atom maps.
- Supported intermediates, bond formation/cleavage and electron-pair movements.
  Use fishhooks for single-electron chemistry where appropriate.
- Product formation, necessary proton transfers, leaving groups/byproducts and
  catalyst regeneration when supported by the mechanism.

Keep atom identities and explicit moving hydrogens consistent across panels.
Mechanism templates illustrate arrow syntax; they do not establish which mechanism
occurs for a new substrate. Distinguish a conventional illustrative mechanism,
a source-supported proposal and experimental evidence. Do not imply experimental
observation merely because a reaction was mentioned in chat.

## Readability and delivery

Split a crowded mechanism across numbered figures with matching step labels and
shared intermediate identities. Display every figure inline in order and retain
PNG/SVG/CDXML outputs. Do not abbreviate away the reacting functional groups.
If unaffected groups are abbreviated, define the abbreviation with the full
structure so the product and reactant identities remain clear.

When only part of a mechanism can be supported, state exactly which part and why.
A partial activation figure may accompany a clarification, but cannot satisfy a
request for a complete mechanism. Do not substitute a text-only account of omitted
steps while claiming the images show the whole reaction.

## Completion check

Verify that each requested reaction, participating reactant and supported step has
its own visible representation, and that the last mechanistic panel reaches the
stated product. Check atom maps, charge/electron balance and relevant byproducts.
Review unresolved steps separately from renderer validation. A drawing-check pass
establishes consistency of the supplied diagram, not chemical feasibility or
complete scope. Retain existing renderer checks and visual-inspection procedures.
