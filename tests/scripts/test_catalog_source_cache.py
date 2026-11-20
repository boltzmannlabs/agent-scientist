"""Canonical test preparation must leave contributed source packages distributable."""


def test_checkout_catalog_stays_valid_after_test_preparation():
    from sci_cli.subagent_package_catalog import CATALOG, catalog
    # Exercise the actual checkout after the canonical runner's compile step.
    rows = catalog()
    assert set(rows) == {p.name for p in CATALOG.iterdir() if p.is_dir() and (p / 'manifest.yaml').is_file()}
    assert all(row['manifest']['id'] == name and row['digest'] for name, row in rows.items())
