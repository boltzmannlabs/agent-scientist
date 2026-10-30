"""CLI commands for saved specialists; execution stays on the ordinary delegation rail."""
from dataclasses import replace
import json
import shlex

from agent import specialist_store as store
from sci_cli.skill_add import Cancelled
from sci_cli.specialist_editor_state import SpecialistUI
from sci_cli.specialist_wizard import edit, review_text

USAGE = ('/Create_subagent [name]\n/Update_subagent [name]\n/subagents [search text]\n'
         '/subagent run <name> <task>\n/subagent show|edit|disable|enable|delete <name>\n'
         '/subagent copy <name> [profile|main] [new-name]\n/subagent duplicate <name> <new-name>\n'
         '/subagent export <name> "<destination.json>"\n/subagent import "<definition.json>" [new-name]\n'
         '/subagent status [run-id]\n/subagent history [page]\n/subagent stop <run-id>\n'
         '/subagent steer <run-id> <message>')


def _run(cli, ui, args):
    if not args:
        raise ValueError("Specify a saved specialist name.")
    item = store.load(args[0])
    if not item.enabled or item.needs_review:
        raise ValueError("This specialist is disabled or awaits review. Use /Update_subagent first.")
    task = " ".join(args[1:]) or ui.ask(f"Task for {item.name}:")
    if not cli._init_agent():
        raise ValueError("The profile's agent could not initialize. Check its model/provider setup.")
    snapshot = getattr(cli.agent, "_specialist_snapshot", {})
    if item.name not in snapshot or snapshot[item.name].revision != item.revision:
        raise ValueError(f"{item.name} is new or changed. Start /new, then repeat /subagent run. Existing conversation unchanged.")
    if "delegate_task" not in cli.agent.valid_tool_names:
        raise ValueError("Delegation is disabled in this conversation. Enable the delegation toolset and start /new.")
    unavailable = set(item.tools) - set(getattr(cli.agent, '_specialist_parent_tools', ()))
    if unavailable:
        ui.show('Unavailable in this conversation: ' + ', '.join(sorted(unavailable)) +
                '. The specialist may answer without these tools; tasks needing them must report a setup requirement.')
    if getattr(cli, "_pending_agent_seed", None):
        raise ValueError("Another request is already queued. Send or cancel it before assigning this task.")
    cli._pending_agent_seed = (
        f"Use my saved specialist {item.name} for this assignment through delegate_task with tasks[].specialist="
        f"{json.dumps(item.name)}. Assignment: {task}\n"
        "Report the run ID and outcome. If it cannot run, explain the blocker; do not replace it with another agent or run the task yourself.")
    ui.show(f"Queued assignment for {item.name}. Execution starts in the next ordinary agent turn; no job has been submitted by this command.")


def _copy(cli, ui, args):
    if len(args) == 1:
        from sci_cli.profiles import list_profile_names
        target = ui.choose('Copy to which profile?', [*("main" if n == "default" else n for n in list_profile_names()), 'Cancel'])
        args = [*args, target]
    if len(args) not in (2, 3):
        raise ValueError("Usage: /subagent copy <name> <profile|main> [new-name]")
    from sci_cli.profiles import get_profile_dir, profile_exists
    target = "default" if args[1] == "main" else args[1]
    if not profile_exists(target):
        raise ValueError("Destination profile does not exist. Use /profiles_list.")
    item = store.load(args[0])
    home = get_profile_dir(target)
    ui.show(f"Copy {item.name} to {args[1]} ({home}). Instructions and capability references are copied. "
            "Sources, child delegations, run history and credentials are not copied. The copy stays disabled pending destination review.")
    ui.choose("Create this copy?", ["Copy for review", "Cancel"])
    copied = store.copy_to(item, home, args[2] if len(args) == 3 else None)
    ui.show(f"Copied {copied.name}. Activate {args[1]}, then /Update_subagent {copied.name} to review and enable it.")


def _duplicate(cli, ui, args):
    if len(args) != 2:
        raise ValueError("Usage: /subagent duplicate <name> <new-name>")
    copied = store.copy_to(store.load(args[0]), store.definition_dir().parent, args[1])
    ui.show(f"Duplicated as {copied.name}; disabled pending /Update_subagent {copied.name}. No credentials or run history copied.")


def _change(cli, ui, args, action):
    if action == "edit" and not args:
        return browse(cli, ui, edit_only=True)
    if len(args) != 1:
        raise ValueError(f"Usage: /subagent {action} <name>")
    item = store.load(args[0])
    if action == "show":
        return ui.show(review_text(item) + f"\nEnabled: {item.enabled}; needs review: {item.needs_review}")
    if action in ("edit", "enable"):
        return edit(cli, ui, existing=item)
    ui.choose(f"{action.title()} {item.name}? Running tasks will not be silently stopped.", [action.title(), "Cancel"])
    if action == "delete":
        store.delete(item.name, expected_revision=item.revision)
    else:
        store.save(replace(item, enabled=False), expected_revision=item.revision)
    ui.show(f"{item.name}: {action} completed. New assignments are blocked; retained run history is unchanged.")


def _history(cli, ui, args, *, detail=False, running_only=False):
    from agent.specialist_runs import history
    rows = history()
    if running_only:
        rows = [row for row in rows if row['status'] == 'running']
    if detail and args:
        matches = [r for r in rows if r['run_id'] == args[0]]
        if not matches:
            raise ValueError("Run not found in this profile.")
        return ui.show(json.dumps(matches[0], indent=2, ensure_ascii=False))
    page = int(args[0]) if args and not detail else 1
    if page < 1:
        raise ValueError("Page must be at least 1.")
    ui.show(f"Specialist runs: {len(rows)}; page {page}. No scientific tool or service was queried.")
    for row in rows[(page - 1) * 10:page * 10]:
        ui.show(f"{row['run_id']} | {row['specialist']} | {row['status']} | {row.get('goal', '')[:150]}\n"
                f"  {row.get('note', '')} Transcript: {row.get('transcript') or 'not retained'}")
    ui.show("Use /subagent status <run-id> for results/errors and transcript path; /subagent history <page> for more.")


def _control(cli, ui, args, action):
    if not args or (action == "steer" and len(args) < 2):
        raise ValueError(f"Usage: /subagent {action} <run-id>" + (" <message>" if action == "steer" else ""))
    if getattr(cli, "agent", None) is None:
        raise ValueError("No live agent owns runs in this conversation.")
    from tools.delegate_tool import delegate_task
    ui.show(delegate_task(action=action, subagent_id=args[0], message=" ".join(args[1:]), parent_agent=cli.agent))


def browse(cli, ui, query="", *, edit_only=False):
    page = 0
    while True:
        items, errors = store.inventory()
        for error in errors:
            ui.show("Unavailable definition: " + error)
        if edit_only and not items:
            ui.show("No saved specialists in this profile. Create one to get started.")
            ui.choose("Create a specialist?", ["Create specialist", "Cancel"])
            return edit(cli, ui)
        matches = [s for s in items.values() if query.casefold() in (s.name + " " + s.purpose).casefold()]
        pages = max(1, (len(matches) + 5) // 6)
        page = min(page, pages - 1)
        labels = {f"{s.name} [{'enabled' if s.enabled else 'disabled'}] — {s.purpose[:90]}": s
                  for s in matches[page * 6:(page + 1) * 6]}
        actions = ([*labels, "Search", "Create specialist", "Cancel"] if edit_only else
                   ["Done", "Create specialist", *labels, "Search", "Import definition", "Running tasks", "Previous runs"])
        if page + 1 < pages:
            actions.append("Next page")
        if page:
            actions.append("Previous page")
        title = "Saved specialists"
        if edit_only:
            from sci_cli.native_profile_session import profile_label
            title = f"Choose a specialist to edit — profile: {profile_label()}"
        choice = ui.choose(f"{title}: {len(matches)}; page {page + 1}/{pages}", actions)
        if choice == "Done":
            return
        if choice in labels:
            item = labels[choice]
            if edit_only:
                return edit(cli, ui, existing=item)
            ui.show(review_text(item))
            action = ui.choose(item.name, ["Run", "Edit", "Duplicate", "Copy to profile", "Export definition", "Disable", "Delete", "Back", "Cancel"])
            if action == "Back":
                continue
            if action == "Run":
                return _run(cli, ui, [item.name])
            if action == "Copy to profile":
                from sci_cli.profiles import list_profile_names
                target = ui.choose("Destination profile", [*("main" if n == "default" else n for n in list_profile_names()), "Cancel"])
                _copy(cli, ui, [item.name, target])
            elif action == "Duplicate":
                _duplicate(cli, ui, [item.name, ui.ask("Name for the copy:")])
            elif action == "Export definition":
                from sci_cli.specialist_portability import export_definition
                export_definition(cli, ui, [item.name, ui.ask('Destination JSON file path:')])
            else:
                _change(cli, ui, [item.name], action.lower())
        elif choice == "Create specialist":
            result = edit(cli, ui)
            if edit_only:
                return result
        elif choice == "Import definition":
            from sci_cli.specialist_portability import import_definition
            import_definition(cli, ui, [ui.ask('Local definition JSON path:')])
        elif choice == "Search":
            query, page = ui.ask("Search name or purpose (use * for all):"), 0
            query = "" if query == "*" else query
        elif choice in ("Running tasks", "Previous runs"):
            _history(cli, ui, [], detail=True, running_only=choice == "Running tasks")
        else:
            page += 1 if choice == "Next page" else -1


def dispatch(cli, command, ui=None):
    ui = ui or SpecialistUI(cli)
    try:
        parts = shlex.split(command)
        verb, args = parts[0].lstrip("/").lower(), parts[1:]
        allowed_while_busy = verb == "subagent" and args and args[0].lower() in {"status", "history", "stop", "steer", "show"}
        if getattr(cli, "_agent_running", False) and not allowed_while_busy:
            raise ValueError("Finish or stop the current turn before managing or assigning specialists")
        if verb == "create_subagent":
            if len(args) > 1:
                raise ValueError("Usage: /Create_subagent [name]")
            return edit(cli, ui, name=args[0] if args else None)
        if verb == "update_subagent":
            return _change(cli, ui, args, "edit")
        if verb == "subagents" or not args:
            return browse(cli, ui, " ".join(args))
        action, args = args[0].lower(), args[1:]
        from sci_cli.specialist_portability import export_definition, import_definition
        handlers = {"run": _run, "copy": _copy, "duplicate": _duplicate,
                    "export": export_definition, "import": import_definition,
                    "history": _history, "status": lambda c, u, a: _history(c, u, a, detail=True),
                    **{k: lambda c, u, a, k=k: _change(c, u, a, k) for k in ("edit", "show", "enable", "disable", "delete")},
                    **{k: lambda c, u, a, k=k: _control(c, u, a, k) for k in ("stop", "steer")}}
        if action not in handlers:
            return ui.show(USAGE)
        return handlers[action](cli, ui, args)
    except (Cancelled, KeyboardInterrupt, EOFError):
        ui.show("Subagent action cancelled. Any unfinished draft is retained in this CLI/profile; use /Create_subagent or /Update_subagent to resume. Nothing was activated by cancellation.")
    except (ValueError, OSError) as exc:
        ui.show(f"Subagent action failed: {exc}. No automatic retry. Use /subagents to inspect the saved state.")


class CLISpecialistMixin:
    def _handle_subagent_command(self, command):
        return dispatch(self, command)
