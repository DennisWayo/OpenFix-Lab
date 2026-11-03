"""Bounded subprocess capture and fail-closed Docker execution."""
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid

from .evidence import digest, utcnow


def capture(argv, *, cwd=None, timeout=30, max_bytes=2_000_000, env=None):
    started = utcnow()
    clock = time.monotonic()
    child = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    output = {"stdout": bytearray(), "stderr": bytearray()}
    selector = selectors.DefaultSelector()
    for name, stream in (("stdout", child.stdout), ("stderr", child.stderr)):
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, name)
    reason = None
    try:
        while selector.get_map():
            if time.monotonic() - clock > timeout:
                reason = "timeout"
                break
            for key, _ in selector.select(timeout=.05):
                data = os.read(key.fileobj.fileno(), 65536)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                remaining = max_bytes - sum(len(v) for v in output.values())
                output[key.data].extend(data[:max(0, remaining)])
                if len(data) > remaining:
                    reason = "output_limit"
                    break
            if reason:
                break
        if reason:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            code = child.wait(timeout=max(.1, timeout - (time.monotonic() - clock)))
        except subprocess.TimeoutExpired:
            reason = "timeout"
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            code = child.wait(timeout=5)
    finally:
        selector.close()
        child.stdout.close()
        child.stderr.close()
    return {"argv": list(argv), "started_at": started, "duration_seconds": round(time.monotonic()-clock, 3),
            "exit_code": code, "termination": reason or "exited",
            **{k:v.decode("utf-8", errors="replace") for k,v in output.items()}}


def bundled_demo(store):
    root = Path(__file__).resolve().parents[1]
    # Run only the reviewed module bundled with this application, never user-provided code.
    safe_env = {k:v for k,v in os.environ.items() if k in ("PATH", "SYSTEMROOT", "LANG", "LC_ALL", "TMPDIR")}
    safe_env["PYTHONNOUSERSITE"] = "1"
    safe_env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = capture([sys.executable, "-m", "openfix.case_sam3"], cwd=root, timeout=30, env=safe_env)
    if result["exit_code"] != 0 or result["termination"] != "exited":
        return store.create({"kind":"sam3_demo", "status":"execution_failed", "execution":result})
    payload = json.loads(result["stdout"])
    payload["record"]["execution"] = {k:v for k,v in result.items() if k != "stdout"}
    payload["record"]["execution"]["isolation"] = "reviewed bundled fixture on host; not a sandbox for untrusted code"
    payload["record"]["execution"]["stdout_sha256"] = digest(result["stdout"].encode())
    return store.create(payload["record"], payload["files"])


def docker_available():
    docker = shutil.which("docker")
    if not docker:
        return False
    result = capture([docker,"info","--format","{{.ServerVersion}}"], timeout=5, max_bytes=4000)
    return result["exit_code"] == 0


def docker_run(repository, revision, command, image, timeout=60, overlays=None):
    """Run a pinned git snapshot in a container. No host fallback."""
    docker = shutil.which("docker")
    if not docker or not docker_available():
        raise RuntimeError("Docker is unavailable. Untrusted repository execution is blocked; start Docker on the build host.")
    if not command or any(not isinstance(arg,str) or "\x00" in arg for arg in command):
        raise ValueError("command must be a nonempty argument array")
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("A full commit SHA is required")
    repo = Path(repository).resolve(strict=True)
    tree = capture(["git","-C",str(repo),"ls-tree","-rl",revision],timeout=10,max_bytes=2_000_000)
    if tree["exit_code"]!=0 or tree["termination"]!="exited":
        raise ValueError("Could not inspect the repository snapshot within the metadata limit")
    total_bytes=0
    for line in tree["stdout"].splitlines():
        metadata=line.split("\t",1)[0].split()
        if len(metadata)>=4 and metadata[3].isdigit():
            total_bytes+=int(metadata[3])
    if total_bytes>128*1024*1024:
        raise ValueError("Repository snapshot exceeds the 128 MB local staging limit; use a smaller fixture checkout")
    image_info = capture([docker,"image","inspect",image,"--format","{{.Id}}"], timeout=10, max_bytes=4000)
    if image_info["exit_code"] != 0:
        raise RuntimeError("The specified container image is not installed. Build or pull it explicitly before running.")
    name = "openfix-" + uuid.uuid4().hex[:16]
    # Stage beside the repository so macOS container runtimes can bind-mount
    # the snapshot. Their default shared paths include /Users, but not the
    # system temp directory under /private/var/folders.
    with tempfile.TemporaryDirectory(prefix=".openfix-snapshot-", dir=repo.parent) as tmp:
        tmp = Path(tmp)
        archive = tmp / "snapshot.tar"
        archived = capture(["git","-C",str(repo),"archive","--format=tar",f"--output={archive}",revision], timeout=20, max_bytes=4000)
        if archived["exit_code"] != 0:
            raise ValueError("Could not export the requested repository revision")
        archive_sha = digest(archive.read_bytes())
        snapshot = tmp / "input"
        snapshot.mkdir()
        with tarfile.open(archive) as tar:
            # Reject links/devices as the snapshot is transferred across a host boundary.
            members = tar.getmembers()
            if any(not (m.isfile() or m.isdir()) for m in members):
                raise ValueError("This runner currently supports snapshots containing regular files and directories only")
            tar.extractall(snapshot, members=members, filter="data")
        for path,content in (overlays or {}).items():
            if path != "candidate/source.py":
                raise ValueError("Only the candidate source overlay is accepted")
            destination = snapshot/path
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(content)
        argv = [docker,"run","--pull=never","--rm","--name",name,"--network=none","--read-only",
                "--cap-drop=ALL","--security-opt=no-new-privileges","--pids-limit=64","--memory=1g",
                "--memory-swap=1g","--cpus=2","--ulimit","nofile=256:256","--user","65534:65534",
                "--mount",f"type=bind,src={snapshot},dst=/input,readonly",
                "--tmpfs","/workspace:rw,nosuid,nodev,size=256m,mode=1777",
                "--tmpfs","/tmp:rw,nosuid,nodev,size=64m,mode=1777",
                "--env","HOME=/tmp","--env","PYTHONDONTWRITEBYTECODE=1", image,
                "/bin/sh","-c",'cp -R /input/. /workspace/ && cd /workspace && exec "$@"',"openfix",*command]
        try:
            result = capture(argv, timeout=timeout)
        finally:
            capture([docker,"rm","-f",name], timeout=10, max_bytes=4000)
    result.update({"isolation":"docker_no_network", "revision":revision, "snapshot_sha256":archive_sha,
                   "container_image_id":image_info["stdout"].strip(), "command":command})
    result["overlays"] = {path:digest(content.encode()) for path,content in (overlays or {}).items()}
    # Discard the temporary host snapshot path from persisted metadata.
    result.pop("argv", None)
    return result
