"""Science-friendly specialist editor; invalid answers preserve the draft."""
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

from agent.specialist_store import Specialist, inventory, save, validate_name
from agent.specialist_runtime import EXECUTION_TOOLS
from sci_cli.science_profiles_catalog import select_science_items, BOLTZMANN_WORKFLOW_TOOLS
from sci_cli.specialist_capabilities import choices, skill_menu, tool_menu, expand_tools, BOLTZMANN_PACKAGE
from sci_cli.specialist_editor_state import drafts, remember, additional_setup


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
    result = list(item.sources)
    while True:
        action = ui.choose(f'References: {len(result)}. Contents are not read or uploaded.',
                           ['Done', 'Add file/folder/URL', 'Clear references', 'Cancel'])
        if action == 'Done':
            return tuple(result)
        if action == 'Clear references':
            result = []
            remember(cli, replace(item, sources=()), existing)
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
                if value not in result:
                    result.append(value)
                    remember(cli, replace(item, sources=tuple(result)), existing)
                break
            except (ValueError, OSError) as exc:
                ui.show(f'Could not use that reference: {exc}. Try again or type skip. Your draft is unchanged.')


def review_text(item):
    from sci_cli.native_profile_session import profile_label
    _, selected = tool_menu({}, item.tools)
    use = ('explicitly by name and automatically for matching tasks' if item.automatic else
           'explicit requests only (legacy setting; review and save to enable both)')
    children = ('\nExisting child-specialist grants: ' + ', '.join(item.children)) if item.children else ''
    return (f'Specialist: {item.name} — profile: {profile_label()}\nPurpose: {item.purpose}\nOutput: {item.output}\n'
            f'Skills: {", ".join(item.skills) or "none"}\nModules: {", ".join(item.skill_files) or "none"}\n'
            f'Tools: {", ".join(selected) or "none (can answer without tools)"}\n'
            f'Use: {use}.{children}\n'
            f'References: {", ".join(item.sources) or "none"}\n'
            f'Additional instructions: {item.instructions or "none"}\n'
            'Uses this profile’s model, credentials and execution limits. A skill is guidance, not permission. '
            'Boltzmann requires this profile’s configured key and authorization. References are not upload grants.')


def _capabilities(cli, ui, item, existing=None):
    skills, tools = choices(cli)
    options, selected, resources = skill_menu(skills, tools, item)
    picked = pick(ui, 'Skills / Boltzmann modules (search a domain or topic)', options, selected)
    selected_files = tuple(resources[n] for n in picked if n in resources)
    selected_skills = {n for n in picked if n not in resources}
    selected_skills.update(r.partition('#')[0] for r in selected_files)
    item = replace(item, skills=tuple(sorted(selected_skills)), skill_files=selected_files)
    remember(cli, item, existing)
    prior_tools = item.tools
    if selected_files and set(BOLTZMANN_WORKFLOW_TOOLS) <= set(tools):
        prior_tools = tuple(set(prior_tools) | set(BOLTZMANN_WORKFLOW_TOOLS))
        ui.show('Boltzmann job tools are preselected for review as one complete package.')
    options, selected = tool_menu(tools, prior_tools)
    if BOLTZMANN_PACKAGE not in options:
        ui.show('Boltzmann job access is not configured here. Use Add capabilities → Configure Boltzmann if needed.')
    selected_tools = expand_tools(pick(ui, 'Tools / integration packages', options, selected))
    if set(selected_tools) & EXECUTION_TOOLS:
        ui.choose('Terminal/code access can use the execution environment; a tool list is not a filesystem/network sandbox.',
                  ['Approve selected execution access', 'Cancel'])
    return replace(item, skills=tuple(sorted(selected_skills)), skill_files=selected_files, tools=selected_tools)


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
            item = Specialist(name, ui.ask('What should this specialist do, and when should it be used?'), automatic=True)
            remember(cli, item, existing)
            item = _capabilities(cli, ui, item)
            remember(cli, item, existing)
            item = replace(item, output=ui.ask('What should the specialist return? (Example: cited comparison with limitations)'))
        else:
            item = existing  # Editing opens review immediately; no repeated questionnaire.
    item = replace(item, automatic=True, enabled=True, needs_review=False)
    while True:
        remember(cli, item, existing)
        ui.show(review_text(item))
        action = ui.choose('Review specialist', ['Save and enable for the next conversation', 'Edit purpose/output',
                          'Edit skills/tools', 'Additional instructions', 'References', 'Add capabilities',
                          'Rename', 'Discard draft', 'Cancel'])
        if action == 'Save and enable for the next conversation':
            try:
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
            item = replace(item, sources=_sources(cli, ui, item, existing))
        elif action == 'Edit skills/tools':
            item = _capabilities(cli, ui, item, existing)
        elif action == 'Additional instructions':
            value = _text(ui, 'Additional instructions/limitations; type none to clear', item.instructions)
            item = replace(item, instructions='' if value.lower() == 'none' else value)
        elif action == 'Add capabilities':
            if additional_setup(cli, ui):
                return
        elif action == 'Rename':
            new_name = _name(ui)
            pending.pop(item.name, None)
            item, existing = replace(item, name=new_name), None
        else:
            item = replace(item, purpose=_text(ui, 'Purpose / when to use:', item.purpose),
                           output=_text(ui, 'Expected output:', item.output))
