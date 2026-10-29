"""Run receipts survive Unicode content and BOMs from external text editors."""

from types import SimpleNamespace
import time

from agent.specialist_policy import SpecialistPolicy
from agent.specialist_runs import history, record
from sci_constants import get_sci_home


def test_bom_receipt_can_be_read_and_completed_without_losing_context():
    home = get_sci_home()
    policy = SpecialistPolicy('reviewer', str(home), 'revision', frozenset(), frozenset(),
                              frozenset(), ('reviewer',), time.monotonic() + 60)
    child = SimpleNamespace(_specialist_policy=policy, _subagent_id='sa-fixture')
    goal = 'Review evidence — 生物学'
    record(child, goal)
    path = home / 'subagent-runs' / 'sa-fixture.json'
    path.write_bytes(b'\xef\xbb\xbf' + path.read_bytes())
    assert history()[0]['goal'] == goal
    record(child, goal, {'status': 'completed', 'summary': 'Reviewed — 完了'})
    row = history()[0]
    assert row['goal'] == goal
    assert row['status'] == 'completed'
    assert row['result']['summary'] == 'Reviewed — 完了'
