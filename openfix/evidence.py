"""Content-addressed files and execution records; model claims are not test results."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class EvidenceStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def create(self, record, files=None):
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:10]
        folder = self.root / run_id
        folder.mkdir()
        artifacts = []
        for name, value in (files or {}).items():
            if Path(name).name != name or name in (".", "..", "record.json"):
                raise ValueError("Artifact names must be plain filenames")
            data = value if isinstance(value, bytes) else value.encode()
            (folder / name).write_bytes(data)
            artifacts.append({"name": name, "sha256": digest(data), "bytes": len(data)})
        envelope = {"schema": "openfix.evidence.v1", "id": run_id, "created_at": utcnow(),
                    "record": record, "artifacts": artifacts}
        envelope["sha256"] = digest(envelope)
        (folder / "record.json").write_text(json.dumps(envelope, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
        return envelope

    def read(self, run_id):
        if not isinstance(run_id, str) or not run_id or any(c not in "0123456789TZ-abcdef" for c in run_id):
            raise ValueError("Invalid run identifier")
        folder = self.root / run_id
        if folder.is_symlink():
            raise ValueError("Symlink records are not accepted")
        path = folder / "record.json"
        if path.is_symlink():
            raise ValueError("Symlink records are not accepted")
        return json.loads(path.read_text())

    def list(self):
        result = []
        for path in sorted(self.root.glob("*/record.json"), reverse=True)[:100]:
            try:
                envelope = self.read(path.parent.name)
                result.append({"id": envelope["id"], "created_at": envelope["created_at"],
                               "kind": envelope["record"].get("kind"), "status": envelope["record"].get("status")})
            except (OSError, ValueError, KeyError):
                continue
        return result

    def audit(self, run_id):
        envelope = self.read(run_id)
        expected = envelope.pop("sha256", None)
        checks = [{"name": "record digest", "passed": digest(envelope) == expected}]
        for item in envelope.get("artifacts", []):
            name = item["name"]
            path = self.root / run_id / name
            safe = Path(name).name == name and not path.is_symlink()
            passed = safe and path.is_file() and digest(path.read_bytes()) == item["sha256"]
            checks.append({"name": name, "passed": bool(passed)})
        return {"passed": all(x["passed"] for x in checks), "checks": checks,
                "scope": "Detects changes to recorded bytes; does not prove correctness of a claim or protect against an attacker rewriting all hashes."}
