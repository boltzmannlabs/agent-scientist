"""Read-only model configuration check for installers; never verifies or prints secrets.

Exit 0 means configuration was found, 3 means model setup is still required.
Other failures retain their error exit status rather than masquerading as missing keys.
"""

from __future__ import annotations


def main() -> int:
    from sci_cli.main import _has_any_provider_configured

    if _has_any_provider_configured():
        print('Model configuration detected. Provider connectivity has not been tested.')
        return 0
    print('Model setup is incomplete. Run: sci setup')
    return 3


if __name__ == '__main__':
    raise SystemExit(main())
