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
            answers = result.get('answers', {})
            value = answers.get('specialist')
            # The terminal represents an explicitly submitted empty answer as None.
            # An absent answer, cancellation or timeout must never supply a value.
            if allow_blank and not choices and 'specialist' in answers and value is None:
                return ''
            if isinstance(value, str) and (value.strip() or allow_blank):
                text = value.strip()
                if '[Pasted text #' in text:
                    text = self.cli._expand_paste_references(text).strip()
                    if '[Pasted text #' in text:
                        self.show('Could not load pasted text. Paste it again or enter an instruction-file path; '
                                  'your previous answers are retained.')
                        continue
                if text or allow_blank:
                    return text
            self.show('Please enter a value, or cancel to return to the prompt with your draft retained.')


def drafts(cli):
    if not hasattr(cli, '_specialist_drafts'):
        cli._specialist_drafts = {}
    return cli._specialist_drafts.setdefault(str(get_sci_home().resolve()), {})


def remember(cli, item, existing):
    drafts(cli)[item.name] = (item, existing)
