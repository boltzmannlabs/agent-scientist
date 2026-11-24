"""Read-only strict package checks inside the approved installed SCI interpreter.
Not an installer, live specialist test, dependency bootstrap or scientific run.
"""
import argparse
import json
from pathlib import Path
import sys

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--package',type=Path,required=True)
    p.add_argument('--check-evidence',action='store_true')
    a=p.parse_args()
    source=a.source.resolve(strict=True)
    sys.path.insert(0,str(source))
    # Read the installed selection without bootstrap/sync, leases, recovery or installs.
    # The bare managed Python does not itself include SCI's selected dependency generation.
    from pm.environments import committed_venv,site_packages
    environment=committed_venv(source)
    if environment is not None:
        selected=site_packages(environment)
        expected='python'+str(sys.version_info.major)+'.'+str(sys.version_info.minor)
        if selected.parent.name.startswith('python') and selected.parent.name!=expected:
            raise SystemExit('SCI dependency ABI differs; select the installed SCI interpreter')
        sys.path.insert(1,str(selected.resolve(strict=True)))
    from sci_cli.subagent_package_schema import validate
    from agent.specialist_runtime import BLOCKED
    manifest,files,_=validate(a.package.resolve(strict=True))
    assert manifest['automatic'] is False and not set(manifest['tools'])&BLOCKED
    if a.check_evidence:
        from sci_cli.subagent_package_review import evidence
        evidence(a.package,manifest)
    print(json.dumps({'status':'PASS_INSTALLED_SCHEMA_ONLY','package_id':manifest['id'],'package_version':manifest['version'],'files_checked':len(files),'local_evidence_checked':a.check_evidence,'scientific_execution':False,'live_agent_tested':False}))
if __name__=='__main__':main()
