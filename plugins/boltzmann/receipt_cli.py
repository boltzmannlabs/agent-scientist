"""Operator-only receipt maintenance; never contacts the scientific service."""

import argparse
import json

from .receipt_store import ReceiptStore, ReceiptStorageError


def register_cli(parser):
    parser.add_argument("receipt_action", choices=("status", "migrate", "cleanup"), default="status", nargs="?")
    parser.set_defaults(func=receipt_command)


def receipt_command(args):
    store = ReceiptStore()
    try:
        action = args.receipt_action
        result = {}
        if action == "migrate":
            result["migrated"] = store.migrate()
        elif action == "cleanup":
            result["removed_receipts"] = store.cleanup()
        result.update(store.inspect())
        print(json.dumps(result, indent=2))
        return 0
    except ReceiptStorageError as exc:
        print(json.dumps({"status": "failed", "error": str(exc),
                          "note": "Earlier atomic steps may have completed. No active/unresolved receipt was selected for deletion."}))
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    register_cli(parser)
    raise SystemExit(receipt_command(parser.parse_args()))
