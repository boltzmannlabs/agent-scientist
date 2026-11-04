"""Task-source boundaries for specialist file reading; no implicit nearby-folder access."""
from pathlib import Path
import shlex


def approved_paths(item, user_request):
    paths = {str(Path(value).expanduser().resolve()) for value in item.sources
             if not value.startswith(('https://', 'http://'))}
    if item.source_manifest:
        from agent.specialist_source_library import reading_paths
        paths.update(reading_paths(item.source_manifest))
    if isinstance(user_request, str):
        try:
            tokens = shlex.split(user_request)
        except ValueError:
            tokens = user_request.split()
        for token in tokens:
            token = token.rstrip('.,;:)')
            if token.startswith(('/', './', '../', '~/')):
                path = Path(token).expanduser()
                if path.exists():
                    paths.add(str(path.resolve()))
    return tuple(sorted(paths))


def check_read(policy, name, args):
    if policy.read_paths is None or name not in {'read_file', 'search_files'}:
        return None
    raw = args.get('path')
    if not isinstance(raw, str) or not raw.strip():
        return 'No implicit workspace search is permitted. Use an explicitly supplied task/reference path.'
    target = Path(raw).expanduser().resolve()
    for root in policy.read_paths:
        allowed = Path(root).expanduser().resolve()
        if target == allowed or (allowed.is_dir() and target.is_relative_to(allowed)):
            return None
    return ('This path was not supplied by the user or selected as a reference. Work from the provided '
            'assignment/saved source text; do not search nearby files. Return a missing-input request if needed.')
