# Capabilities and prerequisites

The Sci integration runs unmodified ChemE-as-Code 1.13.0 from revision
`5b0576c63ae6e82ecad28db745c83f2ef2eb8994` in a PM-managed environment. Its lock
fixes the dependency versions. Use `sci cheme -- --version` to identify the runtime.

Available runtime dependencies cover project initialization and validation,
schemas, BFD/PFD and P&ID rendering, supported analytical propagation, property
libraries, unit conversion and the read-only HTTP API. Access further upstream
commands through `sci cheme -- ...`; discover their inputs with `--help` and
`schema`. Availability of a command does not establish applicability of its model.

## Optional setup

`sci cheme --check-backends` reports Viewer, IDAES/IPOPT and DWSIM-image readiness
without installing. `--setup-viewer` fetches the pinned upstream source, installs
its exact npm lock, builds the Viewer, and keeps assets and licenses outside
Sci's source. `--setup-idaes` installs locked IDAES 2.13.0 in its own PM
environment and checksummed official solver extensions 3.4.2. `--setup-dwsim`
builds the pinned upstream DWSIM 9.0.5 Docker image; Docker must be available.
External upstream worker environment overrides remain supported.

## Optional operations

- `process simulate`: use the optional managed setup for DWSIM or IDAES first.
  Check the selected backend, solver readiness, component and unit-operation
  coverage and thermodynamic package applicability before running it. Record
  convergence and balance diagnostics. Never substitute assumed outputs for a
  missing simulator.
- `sci cheme --project PROJECT --viewer --port 8765` serves the prepared Viewer
  and upstream API together on localhost. For SSH, forward the port from the
  user's computer (`ssh -L 8765:127.0.0.1:8765 USER@SERVER`) and open
  `http://127.0.0.1:8765`. Viewer startup is explicit; normal chat still delivers
  PNG/SVG files. The Viewer exposes the selected project's files and inherits
  upstream same-origin and command-check protections; do not broaden its bind
  address as an expedient for remote viewing.
- Layout, sizing, TEA and LCA: require their corresponding project inputs,
  correlations, cost basis and assessment boundaries. Brightway and third-party
  background inventories need separate preparation; licensed datasets are not
  included. Distinguish missing inputs from an unfavorable calculated result.
- HAZOP and control intent: generated documents are review drafts. PLC output,
  plant readiness and reviewed safety conclusions must not be inferred.

## Backend limits

The pinned IDAES adapter supports benzene, toluene, hydrogen and methane only,
with ideal VLE or Peng–Robinson. It supports selected mixers, heaters/coolers,
pumps/valves, flashes, splitters, conversion reactors and recycles. Unsupported
compounds or operations must be refused, not replaced silently. Its property
packages remain unbenchmarked for experimental prediction; IDAES reactor-energy
closure is explicitly unsupported by upstream. Numerical conservation and
repeatability tests do not remove these limitations.

DWSIM covers a broader set of compounds and operations, including columns and
two-sided heat exchangers. Model applicability, property data, interaction
parameters and independent experimental evidence still need checking for each
case. Do not compare absolute enthalpies across backends with different references.

## Sources and licensing

- Toolkit: https://github.com/ChemE-as-Code/core
- Documentation: https://docs.cheme-as-code.org/
- Process data: https://github.com/ChemE-as-Code/process-library
- License summary: https://cheme-as-code.org/licence/

Upstream toolkit code and its own bundled skills are AGPL-3.0-or-later; process
library data generally uses CC BY 4.0. This integration's original skill and
synthetic example are MIT. No upstream source or skills are copied into Sci.
Redistribution of the upstream software must retain its license and notices.
Generated plant data and reports are not automatically AGPL according to the
upstream license summary. Review distribution choices before bundling a release.
