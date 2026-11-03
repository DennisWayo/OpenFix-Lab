# OpenFix Lab

**Repository + issue → reproduce → identify the contract → propose a repair → verify with evidence.**

A local developer tool built during the Meta Global AI Developer Hackathon. The first case is [SAM 3 #585](https://github.com/facebookresearch/sam3/issues/585). Meta's model can diagnose pinned source, propose a patch, revise against failed checks, and challenge the result. Model opinions and execution have separate evidence labels.

## Launch

Python 3.13+ recommended; tested on an Apple-silicon Mac Studio with Python 3.14.7 and NumPy 2.5.4.

```sh
git clone https://github.com/DennisWayo/OpenFix-Lab.git
cd OpenFix-Lab
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m openfix serve
```

Open **http://127.0.0.1:8765**. When dependencies are installed, `start.command` also starts the server. The app binds only to loopback.

1. **Inspect issue** loads the report, pinned revision, source context, and open policy questions.
2. Confirm **Ask Muse to solve this issue?**, choose a Muse model, and enter a request-only Meta key. OpenFix requests a structured diagnosis and candidate patch, but does not execute it yet.
3. **Verify & review** stages the exact patch, executes it in isolated Docker, and requests a fresh Muse challenge. The final view separates executed results, candidate patch, model criticism, and raw evidence.

The guided interface exposes `muse-spark-1.3` (recommended), `muse-wonder-1.0` (deep analysis), and `muse-spark-1.2` (previous version) in Standard mode. Model availability depends on the Meta account. See the [official model catalog](https://dev.meta.ai/docs/models).

`META_API_KEY` or `MODEL_API_KEY` may supply the key instead. UI keys are used for the request and never written to evidence or browser storage. Default model: `muse-spark-1.3`; endpoint: `https://api.meta.ai/v1/chat/completions`. Override with `META_MODEL` and `META_API_URL`. See the [official Meta quickstart](https://dev.meta.ai/docs/cookbook/quickstart-chat-completions).

## Verified locally

- 32 geometry fixtures: 16 bounding-box cases and 16 binary-mask cases.
- 500 seeded no-crowd checks: baseline and candidate remain identical.
- Ordinary matching, genuine background errors, false negatives, and image classification are preserved under the provisional localization policy.
- A recorded live `muse-spark-1.3` workflow completed with `conditional_local_pass`: Meta diagnosis, first repair proposal, isolated Docker verification, and a fresh Meta challenge. Workflow evidence: `20261103T063701-97ca14bbbd`.
- The Meta-generated candidate passed 32/32 reviewed geometry fixtures and 500/500 no-crowd invariants in Docker without network access. Verification evidence: `20261103T063647-debe68837e`.
- 29 application tests cover fixtures, patch scope and hunk normalization, evidence tampering, per-run Muse model selection, progressive workflow linkage and rejection records, model response handling and reasoning budgets, subprocess limits, in-memory HTTP routes, origin checks, trusted HTTPS proxying, Mac loopback startup, and blocked verification.
- The `export` command produces an interactive report from a recorded run. An exported fixture report is not a live Meta session.

## Execution and scope

The reviewed demo extracts unchanged upstream `evaluateImg` and `accumulate` methods, computes tiny bbox/bitmap overlaps, and uses exhaustive assignment instead of SciPy. It is a **method-level reproduction**, not full CGF1Evaluator/pycocotools, compressed COCO RLE, SAM 3 inference, or dataset-scale validation. The earlier investigation archive is separate and could not be downloaded into this checkout.

The reviewed baseline candidate is built into OpenFix and is not model-generated. Separately, the recorded live workflow used `muse-spark-1.3` to diagnose the pinned source and propose a repair; that exact proposal was staged and executed in the isolated Docker runner. On an Apple-silicon Mac Studio, the application suite, loopback server, browser interface, image build, live Meta workflow, and isolated Docker runner completed successfully.

The result remains conditional. The harness exercises selected evaluator methods with tiny bbox and bitmap geometry rather than full SAM 3 inference or dataset-scale evaluation. The final Meta challenge identified further checks and did not convert the provisional crowd policy into maintainer guidance. Challenge evidence: `20261103T063701-5e2b24c887`.

The server remains bound to loopback. For a private HTTPS reverse proxy such as Tailscale Serve, explicitly allow its exact origin when launching:

```sh
OPENFIX_TRUSTED_ORIGINS=https://your-device.your-tailnet.ts.net python -m openfix serve
```

Only comma-separated HTTPS origins are accepted; arbitrary Host and Origin headers remain blocked.

On the build host, explicitly prepare the container image:

```sh
docker build -t openfix-runner:local .
```

Model diffs must modify only `sam3/eval/cgf1_eval.py`, specifically `CGF1Eval.evaluateImg`. Staging applies and parses a diff without executing it. Verification runs the candidate in Docker with no network, a read-only root filesystem, non-root user, dropped capabilities, resource limits, timeout, and output cap. There is no host fallback for untrusted code. Containers provide practical process isolation, not proof against malicious code or a compromised Docker daemon. The runner was validated locally with Colima/Docker on Apple Silicon.

Docker verification exports a committed OpenFix git revision. After extracting the ZIP on another machine, initialize and commit the checkout before verification:

```sh
git init
git add .
git commit -m 'Import OpenFix Lab'
```

Generic issue intake can fetch current public GitHub issue data, pin HEAD, search related open PRs, and load up to three named source files. Empty PR text search does not establish that no repair is underway. Automated patch verification is currently limited to SAM 3 #585. The generic CLI runner supports pinned git snapshots containing regular files and directories:

```sh
python -m openfix run --repo /path/to/repo --revision FULL_COMMIT_SHA \
  --image YOUR_PREPARED_IMAGE --timeout 60 -- python -m unittest
```

## Other commands

```sh
python -m openfix demo
python -m openfix workflow
python -m openfix intake examples/sam3-585.json --out runs/sam3-585.json
python -m openfix diagnose runs/sam3-585.json --out runs/diagnosis.json
python -m openfix verify PROPOSAL_RUN_ID
python -m openfix audit RUN_ID
python -m openfix export RUN_ID --out OpenFix-Demo.html
python -m unittest discover -s tests -v
node --check web/app.js
```

Evidence in `artifacts/` includes commands, exit status, timing, source revision, digests, model prompts/responses, usage, and limits as applicable. SHA-256 detects modification relative to the record; it does not establish a claim or prevent rewriting both bytes and hashes.

## Provisional crowd policy

Ordinary matches take precedence. Otherwise-unmatched crowd detections meeting the evaluator threshold are ignored for localization, including multiple detections in one crowd. Background errors remain false positives. Existing crowd-only classification is retained with its uncertainty explicit. This policy has **no maintainer endorsement**. See the [clarification question](https://github.com/facebookresearch/sam3/issues/585#issuecomment-6470934831).

## Original work

New OpenFix components include issue intake, Meta integration, bounded orchestration, execution wrappers, candidate staging, evidence records, interface, and interactive export. Meta's evaluator is vendored unchanged under its SAM License with attribution in `vendor/sam3/`. The public source lives at [DennisWayo/OpenFix-Lab](https://github.com/DennisWayo/OpenFix-Lab); the recorded demo video remains a submission task. No upstream PR happens automatically.

## License

Original OpenFix Lab code is released under the [MIT License](LICENSE). The vendored SAM 3 evaluator remains governed by the SAM License included in `vendor/sam3/`.
