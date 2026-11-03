# Local validation — November 3, 2026, Malaysia time

- Reviewed demo: conditional local pass, 32/32 geometry fixtures and 500/500 no-crowd checks.
- Application suite: 29 tests pass.
- Python compilation and JavaScript syntax: pass.
- Evidence record and source/candidate/diff artifact hashes: pass.
- Loopback server startup and rendered browser inspection on Mac Studio: pass.
- `openfix-runner:local` image build and isolated Docker execution through Colima on Apple Silicon: pass.
- Live `muse-spark-1.3` workflow: conditional local pass on the first repair attempt (`20261103T063701-97ca14bbbd`).
- Meta-generated candidate verification: 32/32 reviewed geometry fixtures and 500/500 no-crowd invariants passed in Docker without network access (`20261103T063647-debe68837e`).
- Fresh Meta challenge recorded its unsupported claims and requested additional checks (`20261103T063701-5e2b24c887`).

HTTP unit tests use in-memory request/response streams. Model tests mock the endpoint; workflow tests mock model and Docker operations and ensure blocked verification stays blocked. In addition, the Mac Studio build-host checks exercised the real loopback service, live Meta endpoint, orchestration path, and Docker execution path. The UI-supplied API key was used only for the requests and was not persisted in evidence or browser storage.

The built-in reviewed candidate and the separately recorded Meta-generated candidate must remain clearly distinguished. The live workflow record links the model diagnosis and proposal to its executed verification and subsequent model challenge.

The fixture harness uses selected original upstream methods, exhaustive tiny matching, and bbox/bitmap geometry. It does not establish full COCO wrapper behavior, compressed RLE equivalence, model inference, or dataset-scale performance.
