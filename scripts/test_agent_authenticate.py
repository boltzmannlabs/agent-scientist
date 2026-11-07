#!/usr/bin/env python3
"""Manually check token verification using GET with a JSON request body.

Run with Python 3; no third-party dependencies are needed. The token comes
from AGENT_API_TOKEN or a hidden interactive prompt, never a command argument.
"""

import argparse
import getpass
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request


ENDPOINT = "https://nodejsdev.grsmano.shop/api/agent-authenticate"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Do not forward the token to a redirected destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds (default: 30)")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")

    try:
        token = os.environ.get("AGENT_API_TOKEN") or getpass.getpass("API token (hidden): ")
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled. No request sent.", file=sys.stderr)
        return 1
    if not token.strip():
        print("API token is required. No request sent.", file=sys.stderr)
        return 1

    # This endpoint explicitly requires req.body.apiToken, even for GET.
    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps({"apiToken": token}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="GET",
    )
    opener = urllib.request.build_opener(NoRedirect())
    print(f"GET {ENDPOINT}")
    print("Sending JSON body with apiToken; token hidden. No automatic retries.")
    started = time.monotonic()
    try:
        try:
            response = opener.open(request, timeout=args.timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            status = response.code
            body = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
        detail = str(exc).replace(token, "[REDACTED]")
        print(f"Request failed after {time.monotonic() - started:.2f}s: {detail}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nRequest interrupted; no retry attempted.", file=sys.stderr)
        return 1

    print(f"HTTP {status} ({time.monotonic() - started:.2f}s)")
    try:
        body = json.dumps(json.loads(body), indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        pass
    print(body.replace(token, "[REDACTED]") if body else "(empty response body)")
    print("Inspect the response body for the token-verification outcome.")
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
