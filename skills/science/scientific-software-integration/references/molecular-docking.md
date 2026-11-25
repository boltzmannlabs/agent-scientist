# Molecular docking deployment and probes

Use this reference to install and exercise receptor–small-molecule docking executables. Keep deployment, scoring an existing pose, global docking search, input preparation, and agent registration as separate capabilities.

## 1. Select and install a publisher artifact

For AutoDock Vina, start with the publisher's download index at https://vina.scripps.edu/downloads/ and release metadata at https://api.github.com/repos/ccsb-scripps/AutoDock-Vina/releases/latest. Save metadata to a scratch file before parsing it; do not pipe downloaded content into an interpreter. Select the returned asset URL for the live OS and architecture instead of inventing a filename or assuming an old release remains latest.

The publisher's `vina_1.2.7_linux_x86_64` asset is a standalone statically linked ELF executable. A user-local installation under `$HOME/.local/share/autodock-vina/<version>/vina`, with a non-overwriting link from `$HOME/.local/bin/vina`, is a verified Linux deployment shape. Download the license from the same release tag and preserve it alongside the binary. Check `file`, exact release-asset byte size, and `sha256sum` before execution. When release metadata has no digest, label the stored SHA-256 as locally measured rather than publisher-verified.

Run `vina --version`, `vina --help`, and `vina --help_advanced` after installation. Use the standalone CLI when its capabilities satisfy the request; do not add Python scientific dependencies merely to wrap an executable.

## 2. Acquire prepared, identified fixtures

Use tagged publisher files from `ccsb-scripps/AutoDock-Vina` under `example/basic_docking/solution/`:

- `1iep_receptor.pdbqt`
- `1iep_ligand.pdbqt`
- `1iep_receptor.box.txt`

The publisher's basic-docking tutorial at https://autodock-vina.readthedocs.io/en/latest/docking_basic.html identifies this fixture as imatinib with the c-Abl kinase domain. Preserve the upstream PDBQT preparation for an installation test; introducing a new preparation pipeline would confound the executable probe. This is not an antibody-docking fixture.

## 3. Verify scoring of an existing pose

With local paths substituted for the two prepared fixtures, this invocation is verified on Vina 1.2.7:

```sh
vina --receptor receptor.pdbqt --ligand ligand.pdbqt \
  --score_only --autobox --cpu 1 --seed 42
```

Include `--autobox` for this receptor-plus-ligand score-only probe even though advanced help says the search space can be omitted: the automatic box supplies grid dimensions required by the actual runtime. Verify exit status zero and a finite `Estimated Free Energy of Binding` value in kcal/mol. Retain complete stdout and stderr before extracting the value. Label it a docking-model score, not a measured binding affinity.

## 4. Verify global docking independently

Read the box file rather than inferring a binding site. The publisher fixture specifies center `[15.190, 53.903, 16.917]` and dimensions `[20, 20, 20]` in Angstrom. Supply explicit center and size flags for global docking; do not substitute the score-only autobox probe for a docking-search test. Use an explicit CPU limit, fixed seed, low exhaustiveness for a smoke test, a timeout, and a fresh output path. Require a real nonempty PDBQT output with checked pose records and finite Vina result energies before claiming docking works.

## 5. Gate agent integration separately

Do not infer native registration from CLI success. Apply the umbrella's supported-plugin and fresh-runtime dispatch checks, then exercise each requested tool through the actual registry. Do not describe an unfinished wrapper as installed or available. Keep preprepared PDBQT input requirements explicit; scoring and docking do not establish PDB/SDF conversion, protonation, charge assignment, or antibody-docking support.

The verified profile-local native plugin is `autodock-vina`, with tools `autodock_vina_info`, `autodock_vina_score`, and `autodock_vina_dock` in toolset `autodock_vina`. It uses the standalone executable without adding Python scientific packages to Sci. Score-only supplies `--autobox`; docking requires an explicit Angstrom box. Both use fresh directories under `plugin_data_dir('autodock-vina')`, durable stdout/stderr and JSON results, bounded CPU/time settings, argument-list subprocess execution, and checked finite output energies. Keep these scientific and execution limits explicit in the schemas.

Before activation, run `sci plugins doctor "$SCI_HOME/plugins/autodock-vina" --ci` and the plugin's `test_plugin.py` suite through the bootstrapped launcher. Enable with `sci plugins enable autodock-vina --no-allow-tool-override`, then run `sci --run-module unittest discover -s "$SCI_HOME/plugins/autodock-vina/tests" -p verify_registration.py -v`. That fresh-runtime test asserts configured CLI exposure, dispatches all three real handlers, and writes `plugin_data_dir('autodock-vina')/verification.json`. Read back the enabled profile configuration and verification report before claiming completion. Existing conversations need a new session for native tool schemas; `/reload-mcp` is not a native-plugin reload.

When checking activation changes, account for the CLI sorting `plugins.enabled` and persisting the explicit denial at `plugins.entries.autodock-vina.allow_tool_override: false`. Do not mistake those documented changes for unrelated configuration edits. Preserve a pre-change parsed snapshot or SHA-256-identifiable backup, compare the complete parsed config with only those expected changes allowed, and assert the entire `mcp_servers` section is unchanged.

If startup reports `Unknown toolsets: autodock-vina`, inspect the affected profile’s `platform_toolsets.cli` list. Remove the `autodock-vina` entry and keep `autodock_vina` when Vina tools should be enabled. The hyphenated identifier belongs in `plugins.enabled` and `plugins.entries`. Preserve other entries and reopen Sci to verify the warning is gone and the expected tools are available.
