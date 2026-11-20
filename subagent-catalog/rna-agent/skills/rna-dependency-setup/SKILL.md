---
name: rna-dependency-setup
description: Use when planning or verifying the dependencies a leaf specialist needs (interpreters, bio-tools, R stacks, model environments), or when a leaf reports a missing-program blocker.
version: 1.0.0
author: Agent Scientist
license: MIT
---

# Leaf dependency setup procedure

1. **Read the matrix**: {{resource.references/leaf-dependency-matrix.json}} — per leaf: program ids, pins, roles,
   which endpoints each unlocks, satisfaction routes and the parent assets no install can substitute.
2. **Plan**: `python3 -B <package-root>/scripts/dependency_plan.py --leaf <name>` prints the plan (PLAN_ONLY). For a
   reported blocker, map the exact program id from the leaf's message to the matrix row before proposing anything.
3. **Verify the host**: `--verify` probes interpreters (PATH + conda env roots by minor version), bio-tools
   (RNAfold/RNAplfold/RNAduplex/bowtie2), Rscript and git/env-manager availability, and returns READY / PARTIAL /
   MISSING per leaf with absent programs listed. Include the `--binding PACKAGE=LOCAL_NAME` arguments from
   the coordinator's rendered child table. Only the owning SCI_HOME's saved definitions are inspected;
   bindings are never borrowed from main or another profile.
4. **Escalate precisely**: MISSING blocks core modes; PARTIAL blocks the named endpoints. Propose the matrix's
   satisfaction routes as commands the parent approves: leaf package install review (binds executables,
   version-checked), pinned conda recipes into fresh prefixes, or the bio-tools recipe. Never install yourself, never
   loosen a pin, never present PARTIAL as READY, and remember a found executable is not a binding.
5. **Re-verify and report the delta** after any parent-approved binding or install.

Read [approval boundaries](references/approval-boundaries.md) before proposing any command.
