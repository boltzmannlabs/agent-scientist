"""Title upgrades must not cold-import SDK resources alongside the main request."""

import os
from pathlib import Path
import subprocess
import sys
import textwrap


def test_cold_title_and_sync_async_chat_share_initialized_sdk(tmp_path):
    # A subprocess is essential: the normal test collector already imports SDK
    # resources, hiding the first-request race. All HTTP uses MockTransport.
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent("""
            import asyncio
            import importlib.abc
            import json
            import os
            from pathlib import Path
            import sys
            import threading

            import httpx
            from openai import AsyncOpenAI, OpenAI
            from agent import title_generator as tg
            from sci_state import SessionDB

            assert 'openai.resources' not in sys.modules, 'probe must start cold'
            owner = threading.get_ident()
            cold_worker_imports = []

            class Guard(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname.startswith('openai.resources') and threading.get_ident() != owner:
                        cold_worker_imports.append(fullname)
                        raise RuntimeError('SDK resource initialization raced title startup')
                    return None

            sys.meta_path.insert(0, Guard())
            barrier = threading.Barrier(3, timeout=15)
            failures = []
            requests = []

            def respond(request):
                requests.append(json.loads(request.content))
                return httpx.Response(200, json={
                    'id': 'controlled-response', 'object': 'chat.completion',
                    'created': 0, 'model': 'test-model',
                    'choices': [{'index': 0, 'finish_reason': 'stop',
                        'message': {'role': 'assistant', 'content': '{"title":"Investigate startup imports"}'}}],
                })

            kwargs = dict(model='test-model', messages=[{'role': 'user', 'content': 'test'}])

            def sync_request():
                with OpenAI(api_key='test-only', base_url='https://example.invalid/v1',
                            http_client=httpx.Client(transport=httpx.MockTransport(respond))) as client:
                    return client.chat.completions.create(**kwargs)

            def title_call(**_kwargs):
                barrier.wait()
                return sync_request()

            async def async_request():
                async with AsyncOpenAI(api_key='test-only', base_url='https://example.invalid/v1',
                        http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond))) as client:
                    await client.chat.completions.create(**kwargs)

            def async_worker():
                try:
                    barrier.wait()
                    asyncio.run(async_request())
                except Exception as exc:
                    failures.append(str(exc))

            tg.call_llm = title_call
            db = SessionDB(Path(os.environ['SCI_HOME']) / 'state.db')
            db.create_session(session_id='cold-start', source='cli')
            title_thread = tg.maybe_auto_title(
                db, 'cold-start', 'Investigate SDK startup imports',
                main_runtime={'provider': 'openrouter'},
                failure_callback=lambda task, exc: failures.append(str(exc)),
            )
            assert title_thread is not None
            async_thread = threading.Thread(target=async_worker)
            async_thread.start()
            barrier.wait()
            sync_request()
            title_thread.join(20)
            async_thread.join(20)
            assert not title_thread.is_alive() and not async_thread.is_alive()
            assert not cold_worker_imports, cold_worker_imports
            assert not failures, failures
            assert len(requests) == 3, requests
            assert db.get_session_title('cold-start') == 'Investigate startup imports'
            assert db.get_session_title_source('cold-start') == 'llm'
            db.close()
        """)],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "SCI_HOME": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
