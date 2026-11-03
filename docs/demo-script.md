# OpenFix Lab — three-minute demo plan

Problem statement: **Push the Frontier**. Competition track: **Indie Developer**.

Before recording, launch on the validated Mac Studio with a valid Meta API key, run the Meta workflow, and inspect its recorded result. The Docker runner and browser interface have already passed build-host checks. If the model candidate fails or verification is blocked, disclose that outcome. The built-in candidate must not be presented as Meta-generated. The current exported HTML report is preparation material; the video has not yet been recorded.

| Time | Screen | Narration |
|---|---|---|
| 0:00–0:20 | Issue intake | “OpenFix Lab turns a repository issue into a reviewable repair investigation, with model hypotheses and execution evidence recorded separately.” |
| 0:20–0:45 | Pinned source and failure | “Our first case is a reported SAM 3 scoring discrepancy. A prediction inside a crowd region can become a localization false positive. We pin the code and reproduce that behavior.” |
| 0:45–1:15 | Actual saved Meta diagnosis | “Meta examines the original source and observed results, identifies a suspected contract violation, and proposes a repair. We retain the prompt, response, model, and usage.” |
| 1:15–1:50 | Model diff and Docker verification | “We scope the patch to one evaluator method and execute it in a resource-limited container without network access. Failed checks can trigger a second repair attempt.” |
| 1:50–2:20 | Recorded candidate results and model challenge | “Checks cover ordinary matches, genuine background errors, threshold boundaries, and no-crowd compatibility. A fresh Meta call challenges unsupported claims.” |
| 2:20–2:40 | Provisional policy and evidence | “Passing tests cannot settle the benchmark's intended crowd policy. OpenFix flags that uncertainty and keeps the issue open for maintainer guidance.” |
| 2:40–3:00 | Export and original contribution | “During the event we built reusable intake, Meta workflow, execution wrappers, evidence storage, and this interface. Developers get a candidate, reproducible results, and explicit review questions.” |

Label footage from earlier executions “recorded run” and show the real evidence ID. Trim network waits without suggesting instantaneous execution. State exact results from the recorded Meta candidate; the built-in 32/500 results cannot substitute for them.

Remaining: wait for Meta credits, add a payment method only when ready to make API calls, run and retain the real Meta workflow, record/upload the accessible three-minute video, and submit by **November 5, 2026, 10:00 AM Malaysia time**.
