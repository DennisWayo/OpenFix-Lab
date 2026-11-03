# OpenFix Lab — three-minute demo plan

Problem statement: **Push the Frontier**. Competition track: **Indie Developer**.

Before recording, launch on the validated Mac Studio and load recorded workflow `20261103T063701-97ca14bbbd`. It completed with `conditional_local_pass` on the first Meta repair attempt. The Docker runner, browser interface, live Meta endpoint, and end-to-end workflow have passed build-host checks. Keep the built-in reviewed candidate distinct from the recorded Meta-generated candidate. The current exported HTML report is preparation material; the video has not yet been recorded.

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:20 | Issue intake | “OpenFix Lab turns a repository issue into a reviewable repair investigation, with model hypotheses and execution evidence recorded separately.” |
| 0:20–0:45 | Pinned source and failure | “Our first case is a reported SAM 3 scoring discrepancy. A prediction inside a crowd region can become a localization false positive. We pin the code and reproduce that behavior.” |
| 0:45–1:15 | Actual saved Meta diagnosis | “Meta examines the original source and observed results, identifies a suspected contract violation, and proposes a repair. We retain the prompt, response, model, and usage.” |
| 1:15–1:50 | Model diff and Docker verification | “We scope the patch to one evaluator method and execute it in a resource-limited container without network access. Failed checks can trigger a second repair attempt.” |
| 1:50–2:20 | Recorded candidate results and model challenge | “The Meta-generated candidate passed all 32 reviewed geometry fixtures and all 500 no-crowd invariants in a no-network Docker runner. A fresh Meta call then identifies unsupported claims and requests stronger full-path checks.” |
| 2:20–2:40 | Provisional policy and evidence | “Passing tests cannot settle the benchmark's intended crowd policy. OpenFix flags that uncertainty and keeps the issue open for maintainer guidance.” |
| 2:40–3:00 | Export and original contribution | “During the event we built reusable intake, Meta workflow, execution wrappers, evidence storage, and this interface. Developers get a candidate, reproducible results, and explicit review questions.” |

Label footage from earlier executions “recorded run” and show the real evidence IDs. Trim network waits without suggesting instantaneous execution. The recorded Meta candidate independently achieved 32/32 and 500/500; do not use the built-in candidate as its evidence. Show verification `20261103T063647-debe68837e` and challenge `20261103T063701-5e2b24c887`.

Remaining: record/upload the accessible three-minute video and submit by **November 5, 2026, 10:00 AM Malaysia time**.
