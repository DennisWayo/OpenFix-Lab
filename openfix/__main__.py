import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys


ISSUE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/issues/([1-9][0-9]*)/?$")
SHA = re.compile(r"^[0-9a-f]{40}$")


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def intake(source):
    match = ISSUE.fullmatch(source.get("issue_url", ""))
    revision = source.get("revision", "")
    if not match or not SHA.fullmatch(revision):
        raise ValueError("Expected a GitHub issue URL and a pinned 40-character lowercase commit SHA")
    if not isinstance(source.get("issue_body"), str) or not source["issue_body"].strip():
        raise ValueError("issue_body must contain the issue text")
    owner, repo, number = match.groups()
    record = {
        "schema": "openfix.investigation.v1",
        "repository": f"https://github.com/{owner}/{repo}",
        "issue_url": source["issue_url"].rstrip("/"),
        "issue_number": int(number),
        "revision": revision,
        "issue_body": source["issue_body"],
        "observations": source.get("observations", []),
        "policy_questions": source.get("policy_questions", []),
        "candidate_policy": source.get("candidate_policy"),
        "status": "intake_only",
    }
    if not isinstance(record["observations"], list) or not isinstance(record["policy_questions"], list):
        raise ValueError("observations and policy_questions must be arrays")
    record["input_sha256"] = hashlib.sha256(canonical_bytes(source)).hexdigest()
    return record


def diagnose(record):
    from .model import request_model
    source = json.dumps(record.get("source_files",{}))
    if record.get("issue_url")=="https://github.com/facebookresearch/sam3/issues/585":
        source = (Path(__file__).resolve().parents[1]/"vendor/sam3/cgf1_eval.py").read_text()
    return request_model(record,source)


def main():
    parser = argparse.ArgumentParser(description="OpenFix evidence-first issue intake")
    commands = parser.add_subparsers(dest="action",required=True)
    for name in ("intake","diagnose"):
        command = commands.add_parser(name)
        command.add_argument("input",type=Path)
        command.add_argument("--out",required=True,type=Path)
    serve = commands.add_parser("serve")
    serve.add_argument("--port",type=int,default=8765)
    serve.add_argument("--store",type=Path,default=Path("artifacts"))
    demo = commands.add_parser("demo")
    demo.add_argument("--store",type=Path,default=Path("artifacts"))
    workflow = commands.add_parser("workflow")
    workflow.add_argument("--store",type=Path,default=Path("artifacts"))
    workflow.add_argument("--image",default="openfix-runner:local")
    audit = commands.add_parser("audit")
    audit.add_argument("id")
    audit.add_argument("--store",type=Path,default=Path("artifacts"))
    export = commands.add_parser("export")
    export.add_argument("id")
    export.add_argument("--out",required=True,type=Path)
    export.add_argument("--store",type=Path,default=Path("artifacts"))
    verify = commands.add_parser("verify")
    verify.add_argument("id")
    verify.add_argument("--image",default="openfix-runner:local")
    verify.add_argument("--store",type=Path,default=Path("artifacts"))
    run = commands.add_parser("run")
    run.add_argument("--repo",required=True)
    run.add_argument("--revision",required=True)
    run.add_argument("--image",required=True)
    run.add_argument("--timeout",type=int,default=60)
    run.add_argument("--store",type=Path,default=Path("artifacts"))
    run.add_argument("command",nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.action=="serve":
            from .web import serve
            return serve(args.store,args.port)
        if args.action in ("demo","audit","run","export","verify","workflow"):
            from .evidence import EvidenceStore
            from .runner import bundled_demo,docker_run
            store = EvidenceStore(args.store)
            if args.action=="workflow":
                from .workflow import investigate
                print(json.dumps(investigate(store,image=args.image),indent=2,ensure_ascii=False))
                return
            if args.action=="export":
                from .report import export_report
                print(export_report(store,args.id,args.out))
                return
            if args.action=="verify":
                from .verification import verify_proposal
                print(json.dumps(verify_proposal(store,args.id,args.image),indent=2,ensure_ascii=False))
                return
            if args.action=="demo":
                result = bundled_demo(store)
            elif args.action=="audit":
                result = store.audit(args.id)
            else:
                argv = args.command[1:] if args.command[:1]==["--"] else args.command
                execution = docker_run(args.repo,args.revision,argv,args.image,args.timeout)
                result = store.create({"kind":"repository_execution","status":"command_passed" if execution["exit_code"]==0 and execution["termination"]=="exited" else "command_failed","execution":execution})
            print(json.dumps(result,indent=2,ensure_ascii=False))
            return
        source = json.loads(args.input.read_text())
        result = intake(source) if args.action == "intake" else diagnose(source)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print(args.out)
    except (ValueError, KeyError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"openfix: {exc}\n")


if __name__ == "__main__":
    main()
