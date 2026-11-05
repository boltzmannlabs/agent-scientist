"""Science-friendly specialist editor; invalid answers preserve the draft."""
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

from agent.specialist_store import Specialist, inventory, save, validate_name
from agent.specialist_runtime import EXECUTION_TOOLS
from sci_cli.science_profiles_catalog import select_science_items, BOLTZMANN_WORKFLOW_TOOLS
from sci_cli.specialist_capabilities import choices, skill_menu, tool_menu, expand_tools, BOLTZMANN_PACKAGE
from sci_cli.specialist_editor_state import drafts, remember, additional_setup
from sci_cli.specialist_source_setup import purpose_fields, prepare_references


def pick(ui, title, options, selected=()):
    options = {**{n: 'Previously selected; unavailable here. It will not be granted at runtime.' for n in selected}, **options}
    if not options:
        ui.show(f'{title}: none available in this profile. You can add capabilities from the final review.')
        return []
    return select_science_items(ui, title, options, selected=selected, filtered_controls=True)


def _text(ui, question, current):
    return ui.ask(question + ' (blank keeps the current value)', allow_blank=True) or current


def _name(ui, initial=None):
    value = initial
    while True:
        value = value if value is not None else ui.ask('Name your specialist (lowercase letters, numbers, hyphens):')
        try:
            validate_name(value)
            if value in inventory()[0]:
                raise ValueError(f'{value} already exists; choose another name.')
            return value
        except ValueError as exc:
            ui.show(str(exc) + ' Your other answers are retained.')
            value = None


def _sources(cli, ui, item, existing):
    while True:
        action = ui.choose(f'References: {len(item.sources)}. Saved text is automatically available to assignments.',
                           ['Done', 'Add file/folder/URL', 'Remove a reference', 'Refresh saved contents', 'Clear references', 'Cancel'])
        if action == 'Done':
            return item
        if action == 'Clear references':
            item = replace(item, sources=(), source_documents=(), source_manifest='')
            remember(cli, item, existing)
            continue
        if action == 'Remove a reference':
            if not item.sources:
                ui.show('No references to remove.')
                continue
            source = ui.choose('Remove which source? Other references remain saved.', [*item.sources, 'Back', 'Cancel'])
            if source != 'Back':
                try:
                    item = prepare_references(replace(item, sources=tuple(s for s in item.sources if s != source)), ui)
                    remember(cli, item, existing)
                    ui.show('Reference removed from this draft. Existing conversations may still retain prior snapshots.')
                except (ValueError, OSError, UnicodeError) as exc:
                    ui.show(f'Could not remove source: {exc}. Draft retained.')
            continue
        if action == 'Refresh saved contents':
            try:
                item = prepare_references(item, ui, refresh=True)
                remember(cli, item, existing)
            except (ValueError, OSError, UnicodeError) as exc:
                ui.show(f'Could not refresh: {exc}. Existing snapshots and draft retained.')
            continue
        while True:
            value = ui.ask('Local path or public HTTPS URL (none/skip or blank to skip):', allow_blank=True).strip('"\'')
            if value.lower() in ('', 'none', 'skip', 'back'):
                break
            try:
                url = urlsplit(value)
                if url.scheme in ('http', 'https'):
                    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
                        raise ValueError('Use public HTTPS without credentials, query parameters or fragment.')
                else:
                    value = str(Path(value).expanduser().resolve(strict=True))
                if value not in item.sources:
                    item = prepare_references(replace(item, sources=(*item.sources, value)), ui)
                    remember(cli, item, existing)
                break
            except (ValueError, OSError, UnicodeError) as exc:
                ui.show(f'Could not use that reference: {exc}. Try again or type skip. Your draft is unchanged.')


def review_text(item):
    from sci_cli.native_profile_session import profile_label
    _, selected = tool_menu({}, item.tools)
    use = ('explicitly by name and automatically for matching tasks' if item.automatic else
           'explicit requests only (legacy setting; review and save to enable both)')
    children = ('\nExisting child-specialist grants: ' + ', '.join(item.children)) if item.children else ''
    return (f'Specialist: {item.name} — profile: {profile_label()}\nPurpose: {item.purpose}\nOutput: {item.output}\n'
            f'Subagent-only skills: {", ".join(item.private_skills) or "none"}\n'
            f'Subagent-only tools: {", ".join(item.private_tools) or "none"}\n'
            f'Skills: {", ".join(item.skills) or "none"}\nModules: {", ".join(item.skill_files) or "none"}\n'
            f'Tools: {", ".join(selected) or "none (can answer without tools)"}\n'
            f'Use: {use}.{children}\n'
            f'References: {", ".join(item.sources) or "none"}\n'
            f'Additional instructions: {item.instructions or "none"}\n'
            f'Instruction file: {item.instruction_source or "none"}; saved reference documents: {len(item.source_documents)}'
            f'; external source library: {"yes" if item.source_manifest else "none"}\n'
            'Uses this profile’s model, credentials and execution limits. A skill is guidance, not permission. '
            'File reading/search are included when this profile permits them. '
            'Boltzmann requires this profile’s configured key and authorization. '
            'Saved reference text is supplied automatically to the selected model; service uploads are separate.')


def _capabilities(cli, ui, item, existing=None):
    skills, tools = choices(cli)
    options, selected, resources = skill_menu(skills, tools, item)
    picked = pick(ui, 'Skills / Boltzmann modules (search a domain or topic)', options, selected)
    selected_files = tuple(resources[n] for n in picked if n in resources)
    selected_skills = {n for n in picked if n not in resources}
    selected_skills.update(r.partition('#')[0] for r in selected_files)
    item = replace(item, skills=tuple(sorted(selected_skills)), skill_files=selected_files)
    item = replace(item, skills=tuple(sorted(set(item.skills) | set(item.private_skills))))
    remember(cli, item, existing)
    prior_tools = item.tools
    if selected_files and set(BOLTZMANN_WORKFLOW_TOOLS) <= set(tools):
        prior_tools = tuple(set(prior_tools) | set(BOLTZMANN_WORKFLOW_TOOLS))
        ui.show('Boltzmann job tools are preselected for review as one complete package.')
    options, selected = tool_menu(tools, prior_tools)
    from agent.specialist_sources import READ_TOOLS, DEFAULT_TOOLS
    defaults = DEFAULT_TOOLS & set(tools) if existing is None else READ_TOOLS & set(tools)
    options = {name: description for name, description in options.items() if name not in defaults}
    selected = [name for name in selected if name not in defaults]
    if defaults:
        ui.show('Default tools included from this profile: ' + ', '.join(sorted(defaults)) + '. '
                'Execution still follows the task and backend approval rules; reference code is not run during setup.')
    if BOLTZMANN_PACKAGE not in options:
        ui.show('Boltzmann job access is not configured here. Use Add capabilities → Configure Boltzmann if needed.')
    selected_tools = expand_tools(pick(ui, 'Tools / integration packages', options, selected))
    selected_tools = tuple(sorted(set(selected_tools) | defaults))
    if set(selected_tools) & EXECUTION_TOOLS and existing is not None:
        ui.choose('Terminal/code access can use the execution environment; a tool list is not a filesystem/network sandbox.',
                  ['Approve selected execution access', 'Cancel'])
    return replace(item, skills=tuple(sorted(set(selected_skills) | set(item.private_skills))),
                   skill_files=selected_files, tools=tuple(sorted(set(selected_tools) | set(item.private_tools))))


def edit(cli, ui, *, name=None, existing=None):
    pending = drafts(cli)
    key = existing.name if existing else name
    if key is None and pending:
        key = ui.choose('Resume a draft or start a new specialist?', [*pending, 'Start new', 'Cancel'])
    item = None
    if key in pending:
        if ui.choose(f'Draft for {key}', ['Resume draft', 'Start over', 'Cancel']) == 'Resume draft':
            item, existing = pending[key]
        else:
            pending.pop(key)
    if item is None:
        if existing is None:
            name = _name(ui, name)
            item = Specialist(name, automatic=True, **purpose_fields(ui))
            remember(cli, item, existing)
            item = _capabilities(cli, ui, item)
            remember(cli, item, existing)
            item = replace(item, output=ui.ask('What should the specialist return? (Example: cited comparison with limitations)'))
        else:
            item = existing  # Editing opens review immediately; no repeated questionnaire.
            # Upgrade a previously stored bare path before review, without requiring a duplicate reference.
            item = replace(item, **purpose_fields(ui, initial=item.purpose))
    item = replace(item, automatic=True, enabled=True, needs_review=False)
    if item.extension_id:
        from sci_cli.specialist_private_inventory import reconcile
        try:
            installed = reconcile(item)
            if set(installed.private_skills) - set(item.private_skills) or set(installed.private_tools) - set(item.private_tools):
                ui.show('Installed private additions are awaiting permission review. Choose Review installed private additions; '
                        'you do not need to reinstall or download them.')
        except (ValueError, OSError, UnicodeError) as exc:
            ui.show(f'Private inventory needs attention: {exc}. Your saved definition is unchanged.')
    while True:
        remember(cli, item, existing)
        ui.show(review_text(item))
        action = ui.choose('Review specialist', ['Save and enable for the next conversation', 'Edit purpose/output',
                          'Edit skills/tools', 'Use standard tools', 'Additional instructions', 'References', 'Add capabilities',
                          'Add for this subagent only', 'Review installed private additions', 'Remove private capability',
                          'Rename', 'Discard draft', 'Cancel'])
        if action == 'Save and enable for the next conversation':
            try:
                item = prepare_references(item, ui)
                if item.extension_id:
                    from agent.specialist_extensions import extension_home, fingerprint
                    item = replace(item, extension_revision=fingerprint(extension_home(item)))
                saved = save(item, expected_revision=existing.revision if existing else None)
            except (ValueError, OSError) as exc:
                ui.show(f'Could not save: {exc}. Draft retained. Review, rename, or cancel; nothing was overwritten.')
                continue
            pending.pop(item.name, None)
            ui.show(f'Saved {saved.name}. Explicit and automatic use enabled for the next conversation. '
                    f'Use /new, then /subagent run {saved.name} <task>, or ask a matching question. '
                    'Current prompt/tools unchanged. No job was submitted.')
            return saved
        if action == 'Discard draft':
            pending.pop(item.name, None)
            ui.show('Draft discarded. Previously saved specialists are unchanged.')
            return
        if action == 'References':
            item = _sources(cli, ui, item, existing)
        elif action == 'Review installed private additions':
            from sci_cli.specialist_private_inventory import review_installed
            item = review_installed(cli, ui, item, existing)
        elif action == 'Add for this subagent only':
            from sci_cli.specialist_private_setup import setup
            try:
                item = setup(cli, ui, item)
            except (ValueError, OSError) as exc:
                item = pending[item.name][0]
                ui.show(f'Private setup stopped: {exc}. Draft retained. Saved private files/credentials may remain; nothing was added to main.')
        elif action == 'Remove private capability':
            selected = ui.choose('Remove access from this specialist (saved setup files are retained)',
                                 [*item.private_skills, *item.private_tools, 'Back', 'Cancel'])
            if selected != 'Back':
                if selected in item.shared_tools:
                    ui.show(f'{selected} also belongs to the inherited standard tools and remains selected there. '
                            'Use Edit skills/tools to remove that inherited access as well.')
                item = replace(item, private_skills=tuple(n for n in item.private_skills if n != selected),
                               private_tools=tuple(n for n in item.private_tools if n != selected),
                               shared_tools=tuple(n for n in item.shared_tools if n != selected),
                               skills=tuple(n for n in item.skills if n != selected),
                               tools=tuple(n for n in item.tools if n != selected or n in item.shared_tools),
                               skill_files=tuple(r for r in item.skill_files if r.partition('#')[0] != selected))
        elif action == 'Edit skills/tools':
            item = _capabilities(cli, ui, item, existing)
        elif action == 'Use standard tools':
            from agent.specialist_sources import DEFAULT_TOOLS
            _, available = choices(cli)
            item = replace(item, tools=tuple(sorted(set(item.tools) | (DEFAULT_TOOLS & set(available)))))
            ui.show('Available standard file, terminal, Python and process tools added to this review. '
                    'Save to approve them for the next conversation. No code has run.')
        elif action == 'Additional instructions':
            value = _text(ui, 'Additional instructions/limitations; type none to clear', item.instructions)
            from agent.specialist_sources import instruction_path
            if instruction_path(value):
                fields = purpose_fields(ui, initial=value)
                item = replace(item, instructions=fields.get('instructions', fields['purpose']),
                               instruction_source=fields.get('instruction_source', ''))
            else:
                item = replace(item, instructions='' if value.lower() == 'none' else value,
                               instruction_source='')
        elif action == 'Add capabilities':
            if additional_setup(cli, ui):
                return
        elif action == 'Rename':
            new_name = _name(ui)
            pending.pop(item.name, None)
            item, existing = replace(item, name=new_name), None
        else:
            item = replace(item, **purpose_fields(ui, current=item.purpose))
            item = replace(item,
                           output=_text(ui, 'Expected output:', item.output))
