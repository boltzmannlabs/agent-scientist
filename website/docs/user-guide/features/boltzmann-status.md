---
title: Boltzmann login status
description: Check the active profile's Boltzmann authorization and account balance.
---

# Boltzmann login status

Inside SCI, run:

```text
/boltzmann_status
```

The command identifies the active profile (main or a named profile), without
displaying its filesystem path. If it has no key or matching authorization record, it reports
**Not logged in** and directs you to `/boltzmann_login`.

For an authorized profile, it verifies the saved key with Boltzmann's existing
authentication endpoint. A successful response shows **Logged in**, email,
available credits and frozen credits. Balances display to two decimal places;
missing account fields are identified rather than inferred.

Verification has the existing 15-second request timeout, with no automatic
retry or redirects. A timeout, rejected key or unavailable service is reported
as a verification failure; an outage does not erase the saved login.

The command does not change credentials, grant authorization, enable tools,
switch models, deduct credits, submit jobs or modify conversation context.
It never uses another profile's key as a fallback. To inspect a different
profile, activate it first, then run `/boltzmann_status` there. Login status
does not override that profile's tool permissions or verify every service.
