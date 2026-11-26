import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sci_cli import subagent_package_owner_workflow as workflow
from sci_cli.subagent_package_schema import dependency
from sci_cli.config import atomic_config_replace, read_user_config_raw

DEP = {'kind':'plugin','id':'retrosynthesis-support','source':'https://github.com/krish-200212/retrosynthesis-specialists',
       'revision':'a'*40,'owner_workflow':True}


def test_owner_scope_requires_explicit_known_pinned_source():
    dependency(DEP)
    for changes in ({'source':'https://example.org/repo'}, {'revision':'dev'}, {'optional':True}, {'owner_workflow':'yes'}):
        with pytest.raises(ValueError):
            dependency({**DEP, **changes})


def test_declining_or_collision_preserves_existing_profile(tmp_path):
    ui = SimpleNamespace(show=lambda _: None, choose=lambda *_:'Cancel')
    with pytest.raises(ValueError, match='declined'):
        workflow.review(tmp_path,'new-name',ui)
    directory = tmp_path/'plugins'/workflow.KEY
    directory.mkdir(parents=True)
    sentinel = directory/'local.txt'
    sentinel.write_text('untouched')
    with pytest.raises(ValueError, match='Nothing overwritten'):
        workflow.review(tmp_path,'new-name',ui)
    assert sentinel.read_text()=='untouched'


@pytest.mark.parametrize('fail',[False,True])
def test_owner_plan_binds_renamed_child_or_rolls_back(tmp_path,fail):
    from contextlib import ExitStack
    from sci_cli import plugins_cmd as pc
    owner=tmp_path/'owner'; owner.mkdir()
    private=tmp_path/'child'
    source=private/'plugins'/workflow.KEY
    source.mkdir(parents=True)
    provenance={k:DEP[k] for k in ('source','revision')} | {'pinned':True}
    (source.parent/'.install-metadata.json').write_text(json.dumps({workflow.KEY:provenance}))
    cfg={'memory':{'enabled':False},'platform_toolsets':{'cli':['skills','no_mcp']}}
    atomic_config_replace(owner/'config.yaml',cfg)
    def publish(staged,target,old,new,*,new_only):
        assert new_only
        assert new[workflow.KEY]==provenance
        staged.rename(target)
    with ExitStack() as stack:
        for target,value in [('sci_cli.plugins_transaction.publish_plugin',publish),
                ('sci_cli.plugins_manifest.parse_manifest_file',lambda *_:SimpleNamespace(name=workflow.KEY,key=workflow.KEY,
                    config_schema={'workflow_specialist_name':{}},provides_tools=['start_retrosynthesis_workflow','retrosynthesis_workflow_status'])),
                ('sci_cli.tools_config._get_platform_tools',lambda *a,**kw:{'skills'}),
                ('sci_cli.subagent_package_owner_workflow.backend_python',lambda:'/private/backend')]:
            stack.enter_context(patch(target,value))
        for method,rv in [('_get_enabled_set',set()),('_get_disabled_set',set()),('_read_install_metadata',{}),
                ('_write_install_metadata',None),('_admit_and_save_plugin_sets',None)]:
            stack.enter_context(patch.object(pc,method,return_value=rv))
        try:
            with workflow.activate(owner,private,'renamed',DEP):
                installed=read_user_config_raw(owner/'config.yaml')
                assert installed['plugins']['entries'][workflow.KEY]['settings']['workflow_specialist_name']=='renamed'
                assert 'skills' in installed['platform_toolsets']['cli']
                assert 'no_mcp' in installed['platform_toolsets']['cli']
                if fail: raise RuntimeError('definition publication failed')
        except RuntimeError as exc:
            assert fail and str(exc)=='definition publication failed'
    assert (owner/'plugins'/workflow.KEY).exists() != fail
    if fail: assert read_user_config_raw(owner/'config.yaml')==cfg
