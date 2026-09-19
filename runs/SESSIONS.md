# Session log

Append-only, one line per session. Metadata only — no conversation content.

> 2026-09-19: ten duplicate entries timestamped `2026-09-19T01:38` were
> collapsed to one. They were an artefact of the SessionEnd hook firing
> repeatedly and appending unconditionally, not ten sessions — see #13. The
> hook now skips a write that says nothing new, so nothing else here has been
> edited and nothing else will need to be.

- `2026-09-18T23:23:52Z` — runs on disk: 0, champion: none
- `2026-09-19T01:38:03Z` — runs on disk: 0, champion: none
