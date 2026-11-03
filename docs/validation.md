# Local validation — November 3, 2026, Malaysia time

- Reviewed demo: conditional local pass, 32/32 geometry fixtures and 500/500 no-crowd checks.
- Application suite: 24 tests pass.
- Python compilation and JavaScript syntax: pass.
- Evidence record and source/candidate/diff artifact hashes: pass.
- Loopback server startup and rendered browser inspection on Mac Studio: pass.
- `openfix-runner:local` image build and isolated Docker execution through Colima on Apple Silicon: pass.

HTTP unit tests use in-memory request/response streams. Model tests mock the endpoint; workflow tests mock model and Docker operations and ensure blocked verification stays blocked. In addition, the Mac Studio build-host checks exercised the real loopback service and Docker execution path.

Unavailable here: a real Meta request, because the hackathon credits/key have not yet been issued. Do not describe the built-in candidate as Meta-generated; once credits appear, run the live workflow and retain its evidence ID.

The fixture harness uses selected original upstream methods, exhaustive tiny matching, and bbox/bitmap geometry. It does not establish full COCO wrapper behavior, compressed RLE equivalence, model inference, or dataset-scale performance.
