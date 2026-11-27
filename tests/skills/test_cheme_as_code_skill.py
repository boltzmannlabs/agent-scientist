"""The engineering skill and its resources remain usable after profile sync."""
import json


def test_engineering_skill_and_template_sync_across_profiles(tmp_path):
    from sci_constants import reset_sci_home_override, set_sci_home_override
    from tools.skills_sync import sync_skills
    from tools.skills_tool import skill_view

    homes = [tmp_path / "a", tmp_path / "b"]
    for home in [homes[0], homes[1], homes[0]]:
        token = set_sci_home_override(home)
        try:
            sync_skills(quiet=True)
            result = json.loads(skill_view("cheme-as-code", allow_setup=False))
            assert result["success"], result
            template = next((home / "skills").rglob("cheme-as-code/templates/mixer/plant.yaml"))
            assert template.is_file()
            assert (template.parent / "process/flowsheet.yaml").is_file()
            assert (template.parents[2] / "references/reporting.md").is_file()
        finally:
            reset_sci_home_override(token)
