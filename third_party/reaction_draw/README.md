# Bundled reaction-draw

The upstream `reaction-draw` 1.0.0 skill/renderer is pinned in `provenance.json`.
`upstream/` retains its drawing scripts, JSON templates, prebuilt Octet adapter and
original documentation/notices. It is Apache-2.0 software by Takuto Ohmura;
Octet Draw attribution is retained in `NOTICE` and the upstream third-party notice.

Agent Scientist exposes `sci reaction-draw INPUT.json --out DIR` and one built-in
chemistry skill. The CLI prepares `runtime/` through PM's locked isolated-project
environment API and uses the existing managed Chromium package. `--check-env`
does not install; `--setup` explicitly prepares dependencies and tests browser/font
readiness. Normal draws respect PM's existing lazy-install policy. No core model
tool, service deployment, extra model or API credential is added.

The host needs Chromium's native libraries and Arial or Liberation Sans. Setup
reports a missing host prerequisite without claiming readiness; it does not run
system package installers. On Linux, the distribution's `fonts-liberation`
package supplies the compatible drawing font.

Integration changes replace Unix-only output locking with a native Windows/POSIX
lock, explicitly decode subprocess text as UTF-8 and recognize Sci's existing
managed browser executable. Chemistry, round-trip checks and positive controls
remain upstream-owned. Outputs are PNG/SVG/CDXML plus input/check/edit records;
the drawing does not experimentally validate a mechanism or plan a synthesis.

To update: review a new upstream commit, replace the vendored snapshot and hashes,
reapply the documented adaptations, refresh the isolated runtime lock through PM,
and rerun rendering, portability, CLI and skill tests. Do not rebuild the adapter
from unpinned packages during a normal drawing request.
