# Specialist contribution template

Copy this folder to `subagent-catalog/<your-package-id>` in a separate contribution
checkout based on `origin/dev`. The included table-reviewer is an editable example,
not a claim that your new specialist is tested. Rename its identity and skill as needed.

Follow `subagent-catalog/README.md` and the complete package guide. Replace purpose,
instructions, output contract, tool/skill/dependency declarations and fixtures. Keep
all required supporting files. Add license/provenance, permissions, data transfers,
service charges, platform/backend requirements and known limitations here.

After real local testing fill `tests/validation.json` local evidence and open a PR
**to dev**. Leave integrated status pending until the merged dev revision is tested.
Do not include generated catalog snapshots/checksums or local SCI state. Do not copy
API keys, authorization receipts, conversations, private datasets or installed software.
