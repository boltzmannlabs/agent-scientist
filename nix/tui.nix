# Self-contained Sci TUI, compiled by the same recipe as npm.
{ sciNpmLib, ... }:
sciNpmLib.buildNpmPackage {
  dirs = [
    "ui-tui"
    "apps/shared"
    "sci_cli/data/science-terminal-art.json"
    "sci_cli/data/boltzmann-spin.json"
    "scripts/build/tui.mjs"
    "scripts/build/freshness.mjs"
    "scripts/build/frontend-common.mjs"
  ];

  doCheck = false;

  buildPhase = ''
    runHook preBuild
    node scripts/build/tui.mjs --source "$PWD" --out "$TMPDIR/tui-product"
    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall
    mkdir -p $out/lib/sci-tui
    cp -r "$TMPDIR/tui-product/." $out/lib/sci-tui/
    runHook postInstall
  '';
}
