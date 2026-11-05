"""Plugin reload must tolerate unrelated imports during namespace eviction."""

from types import SimpleNamespace

from sci_cli import plugins_loader


def test_module_eviction_preserves_imports_added_during_traversal(monkeypatch):
    imported = object()

    class ImportingModules(dict):
        """Interleave an unrelated import with either a live walk or a snapshot."""

        def __iter__(self):
            names = super().__iter__()
            yield next(names)
            self["background_import"] = imported
            yield from names

        def copy(self):
            snapshot = super().copy()
            self["background_import"] = imported
            return snapshot

    neighbor = object()
    modules = ImportingModules({
        "sci_plugins.fixture": object(),
        "sci_plugins.fixture.child": object(),
        "sci_plugins.fixture_neighbor": neighbor,
    })
    monkeypatch.setattr(plugins_loader, "sys", SimpleNamespace(modules=modules))

    plugins_loader._evict_modules("sci_plugins.fixture")

    assert modules == {"sci_plugins.fixture_neighbor": neighbor, "background_import": imported}
