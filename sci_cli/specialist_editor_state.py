"""Recoverable in-memory wizard drafts, separated by the owning profile."""
from sci_constants import get_sci_home
from sci_cli.skill_add import WizardUI, Cancelled
from sci_cli.skill_add_status import WizardInputTimeout


class SpecialistUI(WizardUI):
    def ask(self, question, choices=(), *, allow_other=True, allow_blank=False):
        if not getattr(getattr(self.cli, '_app', None), 'is_running', False):
            raise ValueError('Use this wizard in the interactive terminal CLI.')
        while True:
            result = self.cli._clarify_callback([{'qid': 'specialist', 'question': question,
                                                 'choices': list(choices), 'multi_select': False,
                                                 'allow_other': allow_other}])
            if result.get('outcome') == 'timed_out':
                raise WizardInputTimeout('Input timed out. Your draft is retained in this CLI/profile.')
            if result.get('outcome') != 'submitted':
                raise Cancelled()
            value = result.get('answers', {}).get('specialist')
            if isinstance(value, str) and (value.strip() or allow_blank):
                return value.strip()
            self.show('Please enter a value, or cancel to return to the prompt with your draft retained.')


def drafts(cli):
    if not hasattr(cli, '_specialist_drafts'):
        cli._specialist_drafts = {}
    return cli._specialist_drafts.setdefault(str(get_sci_home().resolve()), {})


def remember(cli, item, existing):
    drafts(cli)[item.name] = (item, existing)


def additional_setup(cli, ui):
    routes = {'Add a skill': '/Add_skill', 'Add a tool': '/Add_tool', 'Connect MCP': '/Add_mcp',
              'Configure Boltzmann': '/add_boltzmann'}
    choice = ui.choose('Add capabilities to this owning profile; your specialist draft stays saved in this CLI.',
                       [*routes, 'Back', 'Cancel'])
    if choice == 'Back':
        return False
    command = routes[choice]
    ui.show(f'Opening {command} for this profile. After setup, use /Create_subagent to resume your draft. '
            'New execution permissions still require a new conversation.')
    cli.process_command(command)
    return True
