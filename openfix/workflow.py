"""Run the first evidence-driven Meta investigation with bounded repair attempts."""
import json
import os

from .case_sam3 import ROOT, SOURCE
from .model import request_model
from .runner import bundled_demo
from .verification import verify_proposal


def investigate(store, api_key=None, image="openfix-runner:local"):
    if not (api_key or os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY")):
        raise ValueError("A Meta API key is required for the Meta workflow. The bundled verification remains available without one.")
    from .__main__ import intake
    investigation=intake(json.loads((ROOT/"examples/sam3-585.json").read_text()))
    source=SOURCE.read_text()
    stages=[]
    def stage(name,envelope):
        stages.append({"stage":name,"evidence_id":envelope["id"],"status":envelope["record"]["status"],"sha256":envelope["sha256"]})
        return envelope
    def model_step(action,execution,parent):
        result=request_model(investigation,source,action=action,api_key=api_key,execution=execution)
        result.update({"parent_evidence_id":parent,"issue_url":investigation["issue_url"],"revision":investigation["revision"]})
        files={}
        if action=="repair" and result.get("proposal") and isinstance(result["proposal"].get("unified_diff"),str):
            files["model-proposal.patch"]=result["proposal"]["unified_diff"]
        return store.create(result,files)
    status="workflow_failed"
    error=None
    try:
        seed=stage("reviewed_reproduction",bundled_demo(store))
        if seed["record"]["status"]!="conditional_local_pass":
            raise ValueError("The reviewed reproduction failed; repair generation is blocked")
        diagnosis=stage("meta_diagnosis",model_step("diagnose",seed["record"],seed["id"]))
        if not diagnosis["record"].get("proposal"):
            raise ValueError("Meta diagnosis was not valid structured output")
        evidence={"reproduction":seed["record"],"diagnosis":diagnosis["record"]}
        for attempt in (1,2):
            repair=stage(f"meta_repair_{attempt}",model_step("repair",evidence,stages[-1]["evidence_id"]))
            if not repair["record"].get("proposal"):
                raise ValueError("Meta repair was not valid structured output")
            try:
                verification=verify_proposal(store,repair["id"],image)
            except ValueError as exc:
                verification=store.create({"kind":"model_verification","status":"proposal_rejected",
                                           "reason":str(exc),"parent_evidence_id":repair["id"],"execution":[]})
            stage(f"candidate_verification_{attempt}",verification)
            verdict=verification["record"]["status"]
            if verdict in ("conditional_local_pass","verification_blocked"):
                status=verdict
                break
            evidence={"reproduction":seed["record"],"diagnosis":diagnosis["record"],
                      "previous_repair":repair["record"],"verification":verification["record"]}
            status="candidate_failed"
        review=stage("meta_challenge",model_step("review",{"proposed_repair":repair["record"],"verification":verification["record"]},verification["id"]))
        if not review["record"].get("proposal"):
            status="review_incomplete"
    except (ValueError,RuntimeError,OSError,KeyError) as exc:
        error=str(exc)
    return store.create({"kind":"meta_workflow","status":status,"issue_url":investigation["issue_url"],
                         "revision":investigation["revision"],"stages":stages,"error":error,
                         "policy":investigation["candidate_policy"],"maximum_repair_attempts":2,
                         "limitations":["A passing candidate is conditional on the provisional crowd policy.",
                                        "Fixture verification covers selected evaluator methods, not full SAM 3 inference.",
                                        "Model review is another model opinion; test execution provides the behavioral evidence."]})
