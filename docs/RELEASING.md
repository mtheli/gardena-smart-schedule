# Releasing

How a release is cut and, more importantly, how its notes are written. The
format is shared with the sibling integrations (philips_sonicare_ble,
philips_shaver, isdt_air_ble) — this file exists so it stops drifting.

## Release notes

Written for someone who runs the integration, not for someone who reads the
diff. What changed for them, and what they have to do about it.

**Written in English.** The integration is localized, the notes are not — one text
every reader can open beats a partial set of translated ones. German belongs
in the German-language forum threads, where a release gets announced in the
reader's own language; the notes themselves stay English.

**Structure:** `##` sections by theme, each holding bullets that open with a
bold phrase and then explain themselves in one or two sentences.

```markdown
## Setup no longer blocks Home Assistant

Optional lead-in paragraph — only when the bullets need context to make
sense, e.g. an external cause the reader could not know about.

- **The integration finishes setting up right away** — the schedule sensors
  appear about half a minute later, once the first poll returns.
- **A failing poll is no longer visible as "Retrying setup"** — it is
  written to the log and retried on the next scan interval.
```

**Title:** `vX.Y.Z — what it is about`, e.g.
*v0.1.2 — setup no longer blocks Home Assistant*.

**What does not belong in the notes:** commit lists, file names, internal
symbol names, test tallies, and documentation-only changes.

**Credit belongs in the notes.** Name whoever reported the problem, tested
the fix or supplied the logs, with `@handle` and the issue number, in the
bullet their work belongs to. The `@` is not decoration: it notifies them and
links their profile, and it is how the release and the issue thread explain
each other.

When an external change caused the release, link it. A reader who upgraded
Home Assistant and then saw something break deserves to know the two are
connected — link the core pull request or release that changed the
behaviour.

Where a release changes what the Gardena Smart System Card shows, say so in
the notes — the card is the reason most people install this integration, and
its own release notes will not mention a change that happened here.

## Cutting the release

1. Content commits first, pushed and green.
2. `custom_components/gardena_smart_schedule/manifest.json` — new
   integration version, as its own commit: `release: vX.Y.Z`.
3. Tag `vX.Y.Z`, push, then `gh release create` with the notes above.

HACS offers the release once the tag exists and the manifest version matches
it; a tag without the bump leaves users on the old version with no update
prompt.
