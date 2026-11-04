# SCI contributor mappings

This directory holds verified commit-author email → GitHub login mappings for
Agent Scientist contributors. It is not a contributor roster. Git commit history
remains the record of authorship; release notes use these mappings when an email
does not already identify a GitHub account.

## Adding a mapping

Run from the repository root:

```bash
python3 scripts/add_contributor.py <email> <github-login>
```

The command writes `emails/<email>` with the GitHub login on the first
non-comment line. It rejects conflicting logins and filename case collisions.
Verify that the account belongs to the contributor before adding a mapping.

GitHub noreply addresses resolve directly in release notes. Unmapped authors
retain their Git commit name. There are no person- or company-specific exemptions
in the attribution check; common automation identities are skipped.

Use `python3 scripts/audit_pr_attribution.py` to inspect the current branch.
Its optional `--fix` mode queries GitHub and creates mapping files for review.
