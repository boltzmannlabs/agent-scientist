"""Read-only token verification and account details; never retain a token in results."""

from dataclasses import dataclass
import json
import math

import requests

AUTHENTICATE_URL = "https://nodejsdev.grsmano.shop/api/agent-authenticate"
PLATFORM_URL = "https://app.boltzmann.co/user-profile"
TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 64 * 1024


@dataclass(frozen=True)
class AuthenticationResult:
    authenticated: bool
    message: str
    email: str | None = None
    credits: int | float | None = None
    frozen_credits: int | float | None = None

    def account_summary(self):
        if not self.authenticated:
            return self.message
        from io import StringIO
        import shutil
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        credits = f"{self.credits:,}" if self.credits is not None else "not provided by the service"
        frozen = f"{self.frozen_credits:,}" if self.frozen_credits is not None else "not provided by the service"
        body = Text("Successfully authenticated with Boltzmann.\n\n", style="bold")
        body.append(f"Email: {self.email or 'not provided by the service'}\n\n", style="bold")
        body.append(f"Credits: {credits}\n", style="bold")
        body.append(f"Frozen credits: {frozen}", style="bold")
        output = StringIO()
        # This summary also goes through modals which sanitize control codes.
        # Keep its framing printable so no ANSI/OSC fragments become visible.
        console = Console(file=output, force_terminal=False, color_system=None,
                          width=min(80, shutil.get_terminal_size((80, 24)).columns), highlight=False)
        console.print(Panel(body, title=Text("✓ Boltzmann account", style="bold"),
                            padding=(1, 2), expand=False))
        return "\n" + output.getvalue().rstrip("\n") + "\n"


def _credit(value):
    if type(value) is int:
        return value if value >= 0 else None
    return value if type(value) is float and value >= 0 and math.isfinite(value) else None


def authenticate(token, *, endpoint=AUTHENTICATE_URL):
    if not isinstance(token, str) or not token.strip():
        return AuthenticationResult(False, "No Boltzmann API key was supplied. Nothing was saved.")
    token = token.strip()
    try:
        # GET with a JSON body is this service's explicit contract. Do not move
        # credentials into a query string, follow redirects, or retry elsewhere.
        with requests.get(endpoint, json={"apiToken": token},
                          headers={"Accept": "application/json", "Content-Type": "application/json"},
                          timeout=TIMEOUT_SECONDS, allow_redirects=False, stream=True) as response:
            if response.status_code in {401, 403}:
                return AuthenticationResult(False, "Boltzmann rejected the API key. Check the key and try again. Nothing was saved.")
            if response.status_code != 200:
                return AuthenticationResult(False, f"Boltzmann verification did not succeed (HTTP {response.status_code}). No redirect or fallback was attempted. Nothing was saved.")
            chunks, size = [], 0
            for chunk in response.iter_content(chunk_size=8192):
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    return AuthenticationResult(False, "Boltzmann verification response exceeded the inspection limit. Nothing was saved.")
                chunks.append(chunk)
            payload = json.loads(b"".join(chunks))
    except requests.exceptions.Timeout:
        return AuthenticationResult(False, "Boltzmann verification timed out. No automatic retry was attempted. Nothing was saved.")
    except (requests.exceptions.RequestException, ValueError, UnicodeError):
        return AuthenticationResult(False, "Boltzmann verification was unavailable or returned an invalid response. Nothing was saved.")
    if not isinstance(payload, dict) or payload.get("success") is not True:
        return AuthenticationResult(False, "Boltzmann did not confirm authentication. Check the key and try again. Nothing was saved.")
    email = payload.get("email")
    if isinstance(email, str):
        # Account fields are untrusted terminal data, never markup/instructions.
        email = "".join(c for c in email.replace(token, "[redacted]") if c.isprintable())[:254]
    else:
        email = None
    return AuthenticationResult(True, "Authentication successful", email,
                                _credit(payload.get("credits")), _credit(payload.get("freezedCredits")))
