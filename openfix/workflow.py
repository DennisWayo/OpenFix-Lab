"""Run the first evidence-driven Meta investigation with bounded repair attempts."""
import json
import os

from .case_sam3 import ROOT, SOURCE
from .model import configuration, request_model
from .runner import bundled_demo
from .verification import verify_proposal


def compact(record):
    """Keep model context useful without nesting saved prompts or raw fixture output."""
    keys=("kind","status","reason","error","fixture_count","passed_fixtures",
          "no_crowd_invariants","proposal","validation_error","limitations")
    result={key:record[key] for key in keys if record.get(key) is not None}
    tests=record.get("test_results")
    if isinstance(tests,dict):
        result["executed_checks"]={key:tests[key] for key in
                                   ("status","fixture_count","passed_fixtures","no_crowd_invariants")
                                   if tests.get(key) is not None}
    execution=record.get("execution")
    if isinstance(execution,dict):
        result["execution"]={key:execution[key] for key in ("exit_code","termination","isolation","revision")
                             if execution.get(key) is not None}
    return result


def investigate(store, api_key=None, image="openfix-runner:local", model=None):
    if not (api_key or os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY")):
        raise ValueError("A Meta API key is required for the Meta workflow. The bundled verification remains available without one.")
    from .__main__ import intake
    selected_model=model or configuration()["model"]
    investigation=intake(json.loads((ROOT/"examples/sam3-585.json").read_text()))
    source=SOURCE.read_text()
    stages=[]
    def stage(name,envelope):
        stages.append({"stage":name,"evidence_id":envelope["id"],"status":envelope["record"]["status"],"sha256":envelope["sha256"]})
        return envelope
    def model_step(action,execution,parent):
        result=request_model(investigation,source,action=action,api_key=api_key,execution=execution,model=selected_model)
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
        evidence={"reproduction":compact(seed["record"]),"diagnosis":compact(diagnosis["record"]),
                  "candidate_policy":investigation["candidate_policy"]}
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
            evidence={"reproduction":compact(seed["record"]),"diagnosis":compact(diagnosis["record"]),
                      "previous_repair":compact(repair["record"]),"verification":compact(verification["record"]),
                      "candidate_policy":investigation["candidate_policy"]}
            status="candidate_failed"
        review=stage("meta_challenge",model_step("review",{"proposed_repair":compact(repair["record"]),
                                                            "verification":compact(verification["record"]),
                                                            "candidate_policy":investigation["candidate_policy"]},verification["id"]))
        if not review["record"].get("proposal"):
            status="review_incomplete"
    except (ValueError,RuntimeError,OSError,KeyError) as exc:
        error=str(exc)
    return store.create({"kind":"meta_workflow","status":status,"model":selected_model,"issue_url":investigation["issue_url"],
                         "revision":investigation["revision"],"stages":stages,"error":error,
                         "policy":investigation["candidate_policy"],"maximum_repair_attempts":2,
                         "limitations":["A passing candidate is conditional on the provisional crowd policy.",
                                        "Fixture verification covers selected evaluator methods, not full SAM 3 inference.",
                                        "Model review is another model opinion; test execution provides the behavioral evidence."]})


def finalize_candidate(store, repair_id, api_key=None, image="openfix-runner:local", model=None, progress=None):
    """Verify one saved repair, challenge the evidence, and save a linked workflow."""
    if not (api_key or os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY")):
        raise ValueError("A Meta API key is required to challenge the verification evidence")
    repair=store.read(repair_id)
    repair_record=repair["record"]
    if repair_record.get("kind")!="model_repair" or not repair_record.get("proposal"):
        raise ValueError("Select a structured Meta repair proposal")
    investigation_id=repair_record.get("investigation_id")
    if not investigation_id:
        raise ValueError("The repair is not linked to an issue investigation")
    investigation=store.read(investigation_id)
    investigation_record=investigation["record"]
    diagnosis_id=repair_record.get("parent_evidence_id")
    diagnosis=store.read(diagnosis_id) if diagnosis_id else None
    if progress:
        progress("preparing")
    try:
        verification=verify_proposal(store,repair_id,image,progress=progress) if progress else verify_proposal(store,repair_id,image)
    except ValueError as exc:
        verification=store.create({"kind":"model_verification","status":"proposal_rejected",
                                   "reason":str(exc),"parent_evidence_id":repair_id,
                                   "investigation_id":investigation_id,
                                   "model":model or repair_record.get("model"),"execution":[]})
    if progress:
        progress("challenging")
    try:
        review_result=request_model(
            investigation_record,
            SOURCE.read_text(),
            action="review",
            api_key=api_key,
            model=model or repair_record.get("model"),
            execution={"proposed_repair":compact(repair_record),
                       "verification":compact(verification["record"]),
                       "candidate_policy":investigation_record.get("candidate_policy")},
        )
    except (ValueError,RuntimeError,OSError) as exc:
        review_result={"kind":"model_review","status":"invalid_model_response","proposal":None,
                       "validation_error":str(exc),"model":model or repair_record.get("model"),"execution":[]}
    review_result.update({"parent_evidence_id":verification["id"],"investigation_id":investigation_id,
                          "issue_url":investigation_record.get("issue_url"),
                          "revision":investigation_record.get("revision")})
    review=store.create(review_result)
    if progress:
        progress("recording")
    status=verification["record"]["status"]
    if not review["record"].get("proposal"):
        status="review_incomplete"
    stages=[
        {"stage":"issue_intake","evidence_id":investigation["id"],"status":investigation_record.get("status","intake_only"),"sha256":investigation["sha256"]},
    ]
    if diagnosis:
        stages.append({"stage":"meta_diagnosis","evidence_id":diagnosis["id"],"status":diagnosis["record"]["status"],"sha256":diagnosis["sha256"]})
    stages.extend([
        {"stage":"meta_repair","evidence_id":repair["id"],"status":repair_record["status"],"sha256":repair["sha256"]},
        {"stage":"candidate_verification","evidence_id":verification["id"],"status":verification["record"]["status"],"sha256":verification["sha256"]},
        {"stage":"meta_challenge","evidence_id":review["id"],"status":review["record"]["status"],"sha256":review["sha256"]},
    ])
    return store.create({"kind":"meta_workflow","status":status,"model":model or repair_record.get("model"),
                         "issue_url":investigation_record.get("issue_url"),"revision":investigation_record.get("revision"),
                         "stages":stages,"error":None,"policy":investigation_record.get("candidate_policy"),
                         "maximum_repair_attempts":1,
                         "limitations":["A passing candidate is conditional on the provisional crowd policy.",
                                        "Fixture verification covers selected evaluator methods, not full SAM 3 inference.",
                                        "Model review is another model opinion; test execution provides the behavioral evidence."]})
