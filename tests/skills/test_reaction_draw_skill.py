"""The built-in chemistry skill and its actual resources survive profile sync."""
import json
import re


def test_reaction_draw_syncs_and_loads_across_profiles(tmp_path):
    from sci_constants import reset_sci_home_override, set_sci_home_override
    from tools.skills_sync import sync_skills
    from tools.skills_tool import skill_view

    homes = [tmp_path / "a", tmp_path / "b"]
    for home in [homes[0], homes[1], homes[0]]:
        token = set_sci_home_override(home)
        try:
            sync_skills(quiet=True)
            result = json.loads(skill_view("reaction-draw", allow_setup=False))
            assert result["success"], result
            matches = list((home / "skills").rglob("reaction-draw/templates/acyl_substitution.json"))
            assert matches
            figure = json.loads(matches[0].read_text(encoding="utf-8-sig"))
            assert figure["format"] == 2 and figure["panels"]
            assert all(panel["species"] for panel in figure["panels"])
            simple = next((home / "skills").rglob("reaction-draw/templates/proton_transfer_small_molecules.json"))
            transfer = json.loads(simple.read_text(encoding="utf-8-sig"))
            identities = [
                {atom_map: element for species in panel["species"]
                 for element, atom_map in re.findall(r"\[([A-Z][a-z]?|\*)[^\]]*?:(\d+)\]", species["smiles"])}
                for panel in transfer["panels"]
            ]
            # The moving proton changes its molecule, never its identity.
            assert identities[0] and all(atoms == identities[0] for atoms in identities[1:])
        finally:
            reset_sci_home_override(token)


def test_fischer_templates_connect_with_conserved_atoms_and_full_electron_steps():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / 'skills/science/chemistry/reaction-draw/templates'
    first, second = [json.loads((root / name).read_text()) for name in
                     ('fischer_esterification_1.json', 'fischer_esterification_2.json')]
    assert first['panels'][-1]['species'] == second['panels'][0]['species']
    identities = []
    for figure in (first, second):
        assert all(not arrow.get('summary') for arrow in figure['reaction_arrows'])
        for panel in figure['panels']:
            identities.append({atom_map: element for species in panel['species']
                               for element, atom_map in re.findall(r'\[([A-Z][a-z]?|\*)[^\]]*?:(\d+)\]', species['smiles'])})
        assert all(panel.get('arrows') for panel in figure['panels'][:-1])
    assert identities[0] and all(identity == identities[0] for identity in identities)
