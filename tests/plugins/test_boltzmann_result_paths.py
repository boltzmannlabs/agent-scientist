"""Boltzmann status exposes platform artifact paths without leaking download URLs."""

from types import SimpleNamespace


def test_status_includes_gcp_paths_from_output_data(monkeypatch):
    from plugins.boltzmann import nodeapi_helpers

    signed_url = "https://storage.example.invalid/signed-artifact?token=secret"
    payload = {
        "status": "success",
        "OutputData": {
            "outputFilePath": {
                "path": "gs://fixture-bucket/jobs/fixture/output.csv",
                "download_link": [signed_url],
            },
            "pockets_zip_path": {
                "path": "users/fixture/Binding_Site_Prediction/fpocket/job/6NZP_pockets.zip",
                "download_link": ["https://storage.example.invalid/pockets.zip?token=zip-secret"],
            },
        },
    }
    monkeypatch.setattr(nodeapi_helpers, "_resolve_token", lambda token: "fixture-key")
    monkeypatch.setattr(nodeapi_helpers, "_FETCH_URL", "https://api.example.invalid/result")
    monkeypatch.setattr(nodeapi_helpers.requests, "get", lambda *args, **kwargs: SimpleNamespace(
        status_code=200, json=lambda: payload,
    ))
    monkeypatch.setattr(nodeapi_helpers, "_log_platform_terminal", lambda *args, **kwargs: None)

    result = nodeapi_helpers.fetch_status("fixture-job", "fixture-id", token="fixture-key")

    assert result["gcp_paths"] == [artifact["path"] for artifact in payload["OutputData"].values()]
    assert result["OutputData"] == payload["OutputData"]
    assert all(not path.startswith("https://") for path in result["gcp_paths"])
    assert signed_url not in result["gcp_paths"]
