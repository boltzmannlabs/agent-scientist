"""The upload credit checker requires exact CatPred CSV headers."""


def test_catpred_headers_are_checked_before_upload_without_rewriting_input(tmp_path, monkeypatch):
    from plugins.boltzmann import preflight
    from plugins.boltzmann.contracts import ContractStore

    store = ContractStore()
    sent = []
    monkeypatch.setattr(preflight, "current_key", lambda: "fixture-key")

    def upload(path):
        from pathlib import Path
        sent.append(Path(path).read_bytes())
        return "fixture/catpred.csv"

    source = tmp_path / "catpred.csv"
    for contents, valid in (
        ("seq_id,sequences,smiles\nfixture,MKT,CCO\n", False),
        ("Sequences,SMILES\nMKT,CCO\n", False),
        ("Seq_id,Sequence,SMILES\nfixture,MKT,CCO\n", True),
        ("Seq_id,Sequences,SMILES\nfixture,MKT,CCO\n", True),
        ("Seq_id,sequence,SMILES\nfixture,MKT,CCO\n", False),
        ("Seq_id,Sequences,smiles\nfixture,MKT,CCO\n", False),
        ("Seq_id,Sequence,Sequences,SMILES\nfixture,MKT,MKT,CCO\n", False),
        ("Seq_id,Sequences,SMILES\nfixture,,CCO\n", False),
    ):
        source.write_text(contents)
        before = len(sent)
        result = preflight.validated_upload(str(source), "Cat_Pred", "input_path", {}, True, upload)
        assert source.read_text() == contents
        if valid:
            assert result["status"] == "uploaded", result
            assert sent[-1] == contents.encode()
            assert result["validation"]["warnings"]  # No claim of molecular validation.
        else:
            assert result["status"] == "not_started", result
            assert result["validation"]["errors"]
            assert len(sent) == before
    # Existing receipts under obsolete, permissive header rules cannot be reused.
    import copy
    changed = copy.deepcopy(store)
    changed.files["Cat_Pred"]["files"]["input_path"]["header_case_sensitive"] = False
    assert preflight._contract_digest(store, "Cat_Pred") != preflight._contract_digest(changed, "Cat_Pred")
