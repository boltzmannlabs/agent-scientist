"""Package/catalog commands at the CLI edge; the current agent snapshot is never rebuilt."""
from pathlib import Path

from sci_cli.subagent_package_io import open_package

USAGE = ('/subagent package install <path|catalog:id> [--profile main|name] [--name local-name]\n'
         '/subagent package update <local-name> [path|catalog:id]\n'
         '/subagent package updates\n/subagent catalog [search text]')


def _destination(ui, name):
    from sci_constants import get_sci_home
    from sci_cli.profiles import list_profile_names, get_profile_dir, profile_exists
    if name is None:
        names = ['main' if n == 'default' else n for n in list_profile_names()]
        labels = {'Current owning profile': get_sci_home(), **{n: get_profile_dir('default' if n == 'main' else n) for n in names}}
        return labels[ui.choose('Install into which profile? Existing conversations stay unchanged.', [*labels, 'Cancel'])]
    key = 'default' if name == 'main' else name
    if not profile_exists(key):
        raise ValueError('Destination profile does not exist. Use /profiles_list.')
    return get_profile_dir(key)


def _install(cli, ui, args, *, local_name=None):
    import argparse
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    parser.add_argument('source')
    parser.add_argument('--profile')
    parser.add_argument('--name', default=local_name)
    try:
        options, unknown = parser.parse_known_args(args)
    except (argparse.ArgumentError, SystemExit) as exc:
        raise ValueError(USAGE) from exc
    if unknown:
        raise ValueError(USAGE)
    owner = _destination(ui, options.profile)
    from sci_cli.subagent_package_install import install
    if options.source.startswith('catalog:'):
        from sci_cli.subagent_package_catalog import package
        with package(options.source[8:]) as root:
            return install(root, owner, cli, ui, name=options.name, source=options.source)
    with open_package(options.source) as root:
        return install(root, owner, cli, ui, name=options.name, source=str(Path(options.source).expanduser().absolute()))


def browse(cli, ui, args):
    from sci_cli.subagent_package_catalog import catalog
    query = ' '.join(args).casefold()
    rows = {key: row for key, row in catalog().items() if query in (key + ' ' + row['manifest']['description']).casefold()}
    page = 0
    while True:
        labels = {f'{key} {row["manifest"]["version"]} — {row["manifest"]["description"][:90]}': key
                  for key, row in list(rows.items())[page * 6:page * 6 + 6]}
        actions = [*labels, 'Search', 'Done']
        if (page + 1) * 6 < len(rows):
            actions.append('Next page')
        if page:
            actions.append('Previous page')
        choice = ui.choose(f'Release catalog: {len(rows)} packages; page {page + 1}. Nothing is installed by viewing.', actions)
        if choice == 'Done':
            return
        if choice == 'Search':
            return browse(cli, ui, [ui.ask('Search package name or purpose:')])
        if choice in labels:
            return _install(cli, ui, ['catalog:' + labels[choice]])
        page += 1 if choice == 'Next page' else -1


def dispatch(cli, ui, args):
    if not args:
        action = ui.choose('Install or manage catalog specialists', ['Catalog', 'Install', 'Updates', 'Cancel']).lower()
        args = [action, ui.ask('Package folder/ZIP path or catalog:id:')] if action == 'install' else [action]
    action, rest = args[0].lower(), args[1:]
    from sci_cli.subagent_package_catalog import updates
    handlers = {'install': _install, 'catalog': browse, 'update': _update,
                'updates': lambda c, u, a: updates(u) if not a else _usage()}
    if action in {'export', 'seal', 'validate'}:
        raise ValueError('Contributor preparation is documented in subagent-catalog/README.md; '
                         'prepare the package files and test evidence, then open a PR to dev. '
                         'These preparation slash commands are not provided.\n' + USAGE)
    return handlers.get(action, lambda c, u, a: _usage())(cli, ui, rest)


def _usage():
    raise ValueError(USAGE)


def _update(cli, ui, args):
    if not 1 <= len(args) <= 2:
        return _usage()
    from agent.specialist_store import load
    from sci_constants import get_sci_home
    item = load(args[0])
    if not item.package_info:
        raise ValueError('This is not a managed package installation. Install a package under a new name.')
    source = args[1] if len(args) == 2 else 'catalog:' + item.package_info['id']
    # An update always stays in the active owning profile; it never redirects to main.
    from sci_cli.subagent_package_install import install
    if source.startswith('catalog:'):
        from sci_cli.subagent_package_catalog import package
        with package(source[8:]) as root:
            return install(root, get_sci_home(), cli, ui, name=item.name, source=source)
    with open_package(source) as root:
        return install(root, get_sci_home(), cli, ui, name=item.name, source=str(Path(source).absolute()))
