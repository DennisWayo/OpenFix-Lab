# OpenFix Lab — three-minute demo plan

Problem statement: **Push the Frontier**. Competition track: **Indie Developer**.

Before recording, launch on the validated Mac Studio. Begin with the guided Step 01 issue inspection, show the Step 02 Muse model choice and request-only key boundary, then use recorded workflow `20261103T063701-97ca14bbbd` to present the completed Step 03 without leaving a network wait in the video. It completed with `conditional_local_pass` on the first Meta repair attempt. Keep the built-in reviewed candidate distinct from the recorded Meta-generated candidate.

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:20 | Step 01 · Inspect issue | “OpenFix Lab begins with a public issue, pins its source revision, and exposes the unresolved contract before showing any solution.” |
| 0:20–0:45 | Issue confirmation | “Our first case is a reported SAM 3 scoring discrepancy. Once the context is inspected, I explicitly choose whether to ask Muse for a repair.” |
| 0:45–1:15 | Step 02 · Generate candidate | “I choose the Muse model and provide a request-only key. Muse diagnoses the suspected contract violation and proposes a patch, but that proposal is not yet evidence.” |
| 1:15–1:50 | Step 03 · Verify and review | “We scope the exact patch to one evaluator method and execute it in a resource-limited container without network access. Meta proposes; execution decides.” |
| 1:50–2:20 | Recorded candidate results and model challenge | “The Meta-generated candidate passed all 32 reviewed geometry fixtures and all 500 no-crowd invariants in a no-network Docker runner. A fresh Meta call then identifies unsupported claims and requests stronger full-path checks.” |
| 2:20–2:40 | Provisional policy and evidence | “Passing tests cannot settle the benchmark's intended crowd policy. OpenFix flags that uncertainty and keeps the issue open for maintainer guidance.” |
| 2:40–3:00 | Export and original contribution | “During the event we built reusable intake, Meta workflow, execution wrappers, evidence storage, and this interface. Developers get a candidate, reproducible results, and explicit review questions.” |

Label footage from earlier executions “recorded run” and show the real evidence IDs. Trim network waits without suggesting instantaneous execution. The recorded Meta candidate independently achieved 32/32 and 500/500; do not use the built-in candidate as its evidence. Show verification `20261103T063647-debe68837e` and challenge `20261103T063701-5e2b24c887`.

Remaining: record/upload the accessible three-minute video and submit by **November 5, 2026, 10:00 AM Malaysia time**.
