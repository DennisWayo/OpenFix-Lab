"""Stage a model diff without execution; verify it only in Docker."""
import ast
import json
from pathlib import Path
import tempfile

from .case_sam3 import ROOT, SOURCE
from .evidence import digest
from .runner import capture, docker_run


def stage_patch(diff, original):
    if not isinstance(diff,str) or not diff.strip() or len(diff.encode())>100000:
        raise ValueError("Expected a unified diff under 100 KB")
    if any(line.startswith(("diff --git ","rename ","copy ","Binary files ","GIT binary patch")) for line in diff.splitlines()):
        # Plain unified diffs are accepted. Git-style preambles are handled below.
        lines=diff.splitlines()
        if any(line.startswith(("rename ","copy ","Binary files ","GIT binary patch")) for line in lines):
            raise ValueError("Binary, copy, and rename patches are not supported")
        for line in lines:
            if line.startswith("diff --git ") and line != "diff --git a/sam3/eval/cgf1_eval.py b/sam3/eval/cgf1_eval.py":
                raise ValueError("Patch must modify only sam3/eval/cgf1_eval.py")
    headers=[line for line in diff.splitlines() if line.startswith(("--- ","+++ "))]
    if headers != ["--- a/sam3/eval/cgf1_eval.py","+++ b/sam3/eval/cgf1_eval.py"]:
        raise ValueError("Patch must modify exactly sam3/eval/cgf1_eval.py")
    if any(line.startswith(("old mode ","new mode ","new file mode ","deleted file mode ")) for line in diff.splitlines()):
        raise ValueError("File mode changes are not accepted")
    with tempfile.TemporaryDirectory(prefix="openfix-patch-") as tmp:
        root=Path(tmp)
        source=root/"sam3/eval/cgf1_eval.py"
        source.parent.mkdir(parents=True)
        source.write_text(original)
        patch=root/"candidate.patch"
        patch.write_text(diff)
        result=capture(["git","apply","--whitespace=nowarn",str(patch)],cwd=root,timeout=10,max_bytes=4000)
        if result["exit_code"]!=0:
            raise ValueError("The diff does not apply cleanly to the pinned source")
        if source.is_symlink():
            raise ValueError("Symlink candidates are not accepted")
        candidate=source.read_text()
    try:
        before,after=ast.parse(original),ast.parse(candidate)
    except SyntaxError:
        raise ValueError("The proposed candidate is not valid Python") from None
    def without_evaluate(tree):
        found=[]
        for node in tree.body:
            if isinstance(node,ast.ClassDef) and node.name=="CGF1Eval":
                found=[method for method in node.body if isinstance(method,ast.FunctionDef) and method.name=="evaluateImg"]
                node.body=[method for method in node.body if method not in found]
        if len(found)!=1:
            raise ValueError("Expected exactly one CGF1Eval.evaluateImg method")
        return ast.dump(tree,include_attributes=False)
    if without_evaluate(before)!=without_evaluate(after):
        raise ValueError("This verifier covers changes to CGF1Eval.evaluateImg only; other edits need a broader test plan")
    return candidate


def verify_proposal(store, proposal_id, image="openfix-runner:local"):
    envelope=store.read(proposal_id)
    if not store.audit(proposal_id)["passed"]:
        raise ValueError("Proposal integrity failed")
    proposal=envelope["record"]
    if proposal.get("kind")!="model_repair" or not proposal.get("proposal"):
        raise ValueError("Select a structured model repair proposal")
    original=SOURCE.read_text()
    # A model request may wrap the source in a JSON file map; ensure the issue/revision match.
    if proposal.get("issue_url")!="https://github.com/facebookresearch/sam3/issues/585":
        raise ValueError("This verifier is limited to SAM 3 #585")
    from .case_sam3 import REVISION
    if proposal.get("revision")!=REVISION:
        raise ValueError("The proposal revision does not match the pinned verifier")
    diff=proposal["proposal"].get("unified_diff")
    candidate=stage_patch(diff,original)
    record={"kind":"model_verification","parent_evidence_id":proposal_id,"issue_url":proposal["issue_url"],
            "revision":proposal["revision"],"candidate_sha256":digest(candidate.encode()),
            "verification_scope":"SAM 3 evaluateImg methods and tiny geometry; provisional crowd policy"}
    head=capture(["git","rev-parse","HEAD"],cwd=ROOT,timeout=5,max_bytes=2000)
    if head["exit_code"]!=0:
        raise ValueError("The OpenFix runner must be committed in git before Docker verification")
    try:
        execution=docker_run(ROOT,head["stdout"].strip(),["python","-m","openfix.case_sam3","--candidate","candidate/source.py"],image,
                             overlays={"candidate/source.py":candidate})
    except RuntimeError as exc:
        record.update({"status":"verification_blocked","reason":str(exc),"execution":[]})
        return store.create(record,{"model-proposal.patch":diff,"candidate.py":candidate})
    record["execution"]={k:v for k,v in execution.items() if k!="stdout"}
    record["status"]="verification_failed"
    if execution["exit_code"]==0 and execution["termination"]=="exited":
        try:
            payload=json.loads(execution["stdout"])
            record["test_results"]=payload["record"]
            if payload["record"]["status"]=="conditional_local_pass":
                record["status"]="conditional_local_pass"
        except (ValueError,KeyError,TypeError):
            record["reason"]="Container output was not a valid fixture result"
    return store.create(record,{"model-proposal.patch":diff,"candidate.py":candidate,"container-stdout.txt":execution["stdout"]})
