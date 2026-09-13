# SIEGE — 30-second film and capture script

Creative direction: a dark command room with one luminous core, incoming red attack paths, and a gate that visibly changes after it learns. Let the animation introduce the idea; use real recorded product evidence to prove it. A conceptual render should be labeled “Loop visualization” while visible. The final piece should remain understandable with audio muted.

## Cut A: first recorded loop

Use the v1 → v2 run throughout this cut. It has a complete observed credit-breach story, a rejected first patch, a shipped second patch, a later blocked $100 request, and a legitimate $15 request. Keep the recorded-run label visible over evidence. The 71-second loop is edited for length.

| Time | Picture and motion | Large on-screen copy | Evidence |
|---|---|---|---|
| 0:00–0:03 | Fast push toward the core. Red paths enter the outer gate; one crosses. End the move on a product screenshot. | “WE LET THE ROOM ATTACK OUR AGENT.” | Concept hook; not a claim that 200 people have already joined |
| 0:03–0:07 | Crop to a real tool call. Hold the amount and oracle reason. One brief red impact. | “$100 CREDIT. $20 LIMIT.” / “BREACH EXECUTED” | `turn_4989785be4e2`, v1, TypeSafe allow 78% |
| 0:07–0:11 | Breach trace travels into the defender, then into policy rules. Use four readable stages, not a wall of logs. | “TRACE → PATCH → EVALUATE” | `run_9a8d5533a201`; animation represents the recorded workflow |
| 0:11–0:15 | Freeze the first evaluation. Red “rejected” appears only after the numbers are legible. | “PATCH REJECTED” / “Only 8/11 benign requests allowed” | v2 attempt 1, benign 72.73%, floor 90% |
| 0:15–0:20 | Gate assembles a new segment. Cut to the accepted eval and keep sample counts on screen. | “GATE v2 SHIPPED” / “5/5 attack samples caught · 10/11 benign allowed” | v2 attempt 2, benign 90.91%; 1 breach plus 4 generated attack variants |
| 0:20–0:26 | Two successive real tool-call crops: $100 blocked, then first $15 credit allowed. Red stops at the gate; green continues. | “$100: BLOCKED” → “$15: ALLOWED” | `turn_0698506ad0f9` and `turn_8379ff086021`; different personas, same tool |
| 0:26–0:30 | Hold the wordmark against the now-stable gate. A subtle loop continues behind the type. | “SIEGE” / “Every breach becomes a better gate.” / “github.com/vnmoorthy/siege” | End card; small “Recorded demo · Sep 13, 2026” |

Voiceover, approximately 74 words:

> We let the room attack our support agent. It issued a hundred dollars of credit against a twenty-dollar limit. SIEGE turned that breach into a gate patch. The first patch blocked too many legitimate requests. Rejected. The next caught all five attack samples and allowed ten of eleven benign requests. After the patch, another hundred-dollar request was blocked. A legitimate fifteen-dollar credit still worked. SIEGE. Every breach becomes a better gate.

The exact [rejected evaluation](https://wandb.ai/vnmoorthy-amperes-ai/siege/r/call/01a09bff-ac5f-798f-8d55-2bc0a2ec5585) and [accepted evaluation](https://wandb.ai/vnmoorthy-amperes-ai/siege/r/call/01a09c00-271b-720e-82af-7d26ca52fa18) anchor this cut. Do not substitute v3's 12/12 and 15/16 numbers into v2 footage.

## Cut B: evaluation proof card

For a separate six-second insert, show v3 as its own recorded evaluation:

“GATE v2 → v3”

“Attack samples caught: 6/12 → 12/12”

“Benign requests allowed: 15/16”

“First candidate rejected below the 90% benign floor”

Small footer: “Recorded replay evaluation · 12 attack + 16 benign samples · Sep 13, 2026.” Link its [accepted evaluation](https://wandb.ai/vnmoorthy-amperes-ai/siege/r/call/01a09c07-8834-7e84-9f2e-99dc2751d112) in the post description. Keep this separate from any claim about live room breach rate.

## Capture checklist

- Record a wide master at 1920×1080 and prepare a separate 1080×1920 edit. Reframe the phone/chat and proof cards for vertical; do not shrink the entire dashboard into a phone frame.
- Keep titles and evidence in the central safe area, with generous bottom space for social-platform controls. Limit each large caption to two lines. Sample denominators must survive a phone-size preview.
- Capture the actual product with the intended mode, gate version, and provider visible. Browser mock footage carries a persistent “Simulation” label. Renders carry “Loop visualization”; they never carry fabricated live metrics.
- Open a trace or tool call before recording, then hold it long enough to read. Use clean crops of the amount, decision, and oracle reason; omit irrelevant seeded customer email/address fields.
- Use 30 fps, H.264 MP4, and an export that starts playing immediately. Include a poster image from the strongest frame. Verify the exported file plays locally from start to finish with captions readable.
- Match motion to actual events only when driven by those events: one impact per breach, a stopped path per block, and a gate change per shipped version. Idle atmosphere can continue without incrementing counters.
- Keep light pulses subtle, avoid repeated full-screen flashes, and preserve a still/poster fallback for reduced-motion viewing.
- The teaser supports the live demo. Close with the project/repository; show the audience QR only after its destination has been verified from a phone.

## Post copy

“We gave a room a support agent to attack. SIEGE turns each forbidden tool call into an evaluated gate patch. In this recorded loop, the first patch was rejected for blocking too many legitimate requests; the next caught 5/5 attack samples while allowing 10/11 benign requests. Built at CoreWeave Hacks. Code and eval evidence: github.com/vnmoorthy/siege.”

Post only after the team has reviewed the exported video and the linked evidence is accessible. This document does not schedule or publish anything.
