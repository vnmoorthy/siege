# AGI House project form (CoreWeave Hacks: Agent Loops)

**Project Name:** SIEGE

**Tagline:** 200 people vs one agent. A typed action gate that learns from every breach.

**Description:**
SIEGE puts a real customer-support agent with real tools (refunds, address changes, discounts, store credit, customer lookups) in front of a room full of attackers on their phones. Every tool call the agent wants to make passes through a typed action gate: TypeSafe System One answers allow / block / escalate with calibrated probabilities in about 200 ms. A deterministic policy oracle is ground truth, so a breach is exact: the gate allowed it, the oracle says it was forbidden, and the tool executed. A false block (a legitimate customer turned away) is exact too and is the guard metric.

The loop: reason (the agent decides on a tool call), act (the gate decides), catch (the oracle records breaches and false blocks as traces), iterate (when a round ends, a defender model rewrites the gate policy from the breach traces and writes a deterministic prefilter; a red-team model amplifies each breach into variants; the prefilter is validated inside a W&B Serverless Sandbox; a Weave Evaluation scores the candidate on all breaches plus variants versus a benign corpus; it ships only if the catch rate rises and the benign allow rate stays at or above 90%, up to 3 attempts, otherwise it is rejected with a recorded eval). The next round runs on the new gate and the breach rate on the wall falls while the room keeps attacking.

Recorded live run: gate v1 caught 2 of 8 attack samples; the defender's first candidate caught 8/8 but blocked 3 of 12 legitimate requests and was rejected; the second candidate caught 8/8 with 11/12 benign allowed and shipped, 81 seconds end to end. A 7-round simulated siege went from 100% breach rate to 0% as gates v1 to v3 shipped. Every turn, gate decision, oracle verdict, tool execution and defender stage is a Weave trace; every candidate policy is a Weave Evaluation with its own link.

What is on screen: a war room (live feed, per-round breach rate versus benign allow rate with gate-version markers, leaderboard, defender stepper, QR to join, and a three.js battlefield where attacks stream toward the gate, shatter amber when blocked and punch through red when they breach), a mobile attacker page (persona, bounty board, chat with tool-call chips showing the gate's probabilities, breach celebrations), a control page (rounds, settings, defender runs and logs, gate version browser with rule diffs and eval failures, rollback, trace viewer), and a marimo notebook on molab (RTX Pro 6000) with a TypeSafe calibration diagram, a what-if slider on the ship rule, and a GPU embedding map of every attack.

Models: gpt-oss-20b as the support agent, DeepSeek V4 Pro as the defender, NVIDIA Nemotron 3 Ultra as the red team, all served by W&B Inference on CoreWeave. Mock mode runs the entire loop with zero keys and is what the public demo link shows.

**Tech Stack:** Python, FastAPI, SQLite, React, TypeScript, Vite, Tailwind CSS, three.js, Recharts, Framer Motion, TypeSafe AI (System One), Weights & Biases Weave, W&B Inference, CoreWeave Serverless Sandboxes, marimo, Blender, pptxgenjs, GitHub Pages

**Repository URL:** https://github.com/vnmoorthy/siege

**Demo URL:** https://vnmoorthy.github.io/siege/  (in-browser simulation of the war room, labeled MOCK DATA; the live system runs at the venue on http://10.20.7.5:8000 and the marimo lab is at https://molab.marimo.io/notebooks/nb_JJREjE7meQ5T3n2SkNFCoL)

**Tracks:** Best Loop Design, Most Production-Ready, Best Use of Weave, Best Use of marimo, Best Social Media demo, Best Use of TypeSafe AI
(Do not select Best Use of ARIA: ARIA is not used.)

**Team Members:** NarasingaMoorthy (vnmoorthy) and teammates as registered.
