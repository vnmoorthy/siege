# Recorded SIEGE evidence

The verified deliverable is `phone-recorded-credit-breach-430x932.png` (430 × 932), captured at 2026-09-13 18:54:15 UTC from the actual product UI in live mode. It shows the existing 18:18:11 UTC gate-v1 event: a $100 credit executed against a $20 cap, TypeSafe allow probability 78%, confidence 67%, and 187 ms gate latency. The current app header shows v3; the historical tool call correctly shows v1. No new attack was submitted.

An existing profile was read from SQLite using `mode=ro` and served only to the browser profile request, preventing that endpoint from updating `last_seen`. The history itself came from the actual live read-only endpoint. The profile is a seeded Nimbus demo customer.

`manifest.json` contains capture times, mode, current metrics/providers, exact failures, and this routing disclosure. Captured totals were 153 turns, 18 breaches, and 9 attackers; those are not 200 actual participants.

Desktop screenshots could not be captured reliably during simultaneous rendering and live-app load. The scripts preserve real failures and do not substitute mock data. The optional raw video is unusable and should not be published. No additional capture attempts are running intentionally.

Use the phone frame as recorded product proof alongside the conceptual cinematic. Keep a recorded-event label when editing it into video. The repeatable capture scripts are one directory above; use them only after the current render workload finishes.
