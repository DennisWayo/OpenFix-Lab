"""Reviewed small-fixture demonstration of SAM 3 #585.

Uses unchanged upstream evaluateImg/accumulate methods, tiny exact matching,
and locally computed bbox/bitmap overlap. Not a full COCO or model inference run.
"""
import ast
import copy
import difflib
import itertools
import json
from pathlib import Path
import types

import numpy as np

from .evidence import digest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "vendor/sam3/cgf1_eval.py"
REVISION = "f1647e8d0c1d280991f4d1b7d974c2704537fe66"


def candidate_source(source):
    old = """        # compute matching
        if len(ious) == 0:"""
    new = """        # Preserve crowd overlaps before removing ignored GT columns.
        crowd_gt = np.array([bool(g.get("iscrowd", 0)) for g in all_gts], dtype=bool)
        crowd_ious = (
            ious[keep_dt, :][:, crowd_gt]
            if len(ious) and np.any(crowd_gt)
            else np.zeros((len(dt), 0))
        )

        # compute matching
        if len(ious) == 0:"""
    if source.count(old) != 1:
        raise ValueError("Upstream source differs from the reviewed patch context")
    source = source.replace(old, new)
    old = """            FP = len(dt) - TP
            FN = len(gt) - TP"""
    new = """            # Only unmatched detections may be ignored for crowd overlap.
            ordinary_matched = np.zeros(len(dt), dtype=bool)
            ordinary_matched[matched_dt[match_scores >= thresh]] = True
            crowd_ignored = (
                np.any(crowd_ious >= thresh, axis=1) & ~ordinary_matched
                if crowd_ious.shape[1]
                else np.zeros(len(dt), dtype=bool)
            )
            FP = len(dt) - TP - crowd_ignored.sum()
            FN = len(gt) - TP"""
    if source.count(old) != 1:
        raise ValueError("Upstream matching block differs from the reviewed patch context")
    return source.replace(old, new)


def exact_assignment(cost):
    """Exhaustive min-cost assignment for <= 7 x 7 fixtures; no SciPy dependency."""
    rows, cols = cost.shape
    if max(rows, cols) > 7:
        raise ValueError("Demo matching adapter is limited to seven objects")
    if not rows or not cols:
        return np.array([], dtype=int), np.array([], dtype=int)
    if rows > cols:
        c, r = exact_assignment(cost.T)
        return r, c
    permutation = min(itertools.permutations(range(cols), rows),
                      key=lambda p: sum(cost[i, p[i]] for i in range(rows)))
    return np.arange(rows), np.array(permutation, dtype=int)


def methods(source):
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "CGF1Eval")
    nodes = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ("evaluateImg", "accumulate")]
    namespace = {"np": np, "linear_sum_assignment": exact_assignment}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


def overlap(detection, ground_truth, crowd, mode):
    if mode == "bbox":
        x, y, w, h = detection
        a, b, c, d = ground_truth
        intersection = max(0, min(x+w, a+c)-max(x, a)) * max(0, min(y+h, b+d)-max(y, b))
        detection_area, gt_area = w*h, c*d
    else:
        # Integer pixel rectangles, represented as actual binary arrays.
        def mask(rect):
            x, y, w, h = rect
            result = np.zeros((64, 64), dtype=bool)
            result[y:y+h, x:x+w] = True
            return result
        dm, gm = mask(detection), mask(ground_truth)
        intersection, detection_area, gt_area = np.logical_and(dm, gm).sum(), dm.sum(), gm.sum()
    denominator = detection_area if crowd else detection_area + gt_area - intersection
    return float(intersection / denominator) if denominator else 0.0


def evaluate(namespace, gts, dts, mode, threshold=.5):
    gt = [{"bbox": b, "iscrowd": crowd, "ignore": crowd} for b, crowd in gts]
    dt = [{"bbox": b, "score": score} for b, score in dts]
    matrix = np.array([[overlap(d["bbox"], g["bbox"], g["iscrowd"], mode) for g in gt] for d in dt], dtype=float).reshape(len(dt), len(gt))
    obj = types.SimpleNamespace(params=types.SimpleNamespace(useCats=False, catIds=[1], iouThrs=np.array([.5, .75, .95])),
                                threshold=threshold, _gts={(1, 1):gt}, _dts={(1, 1):dt}, ious={(1, -1):matrix})
    return namespace["evaluateImg"](obj, 1, -1, [0, 1e10], 1000000)


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(x) for x in value]
    return value


def fixtures():
    ordinary = ([0, 0, 8, 8], False)
    crowd = ([20, 20, 20, 20], True)
    correct = ([0, 0, 8, 8], .9)
    inside = ([22, 22, 4, 4], .9)
    second = ([30, 30, 4, 4], .8)
    background = ([48, 48, 4, 4], .9)
    # Expected localization FP at IoU .5, .75, .95 for baseline and candidate.
    return [
        ("ordinary_match", [ordinary], [correct], [0,0,0], [0,0,0]),
        ("ordinary_plus_crowd", [ordinary,crowd], [correct,inside], [1,1,1], [0,0,0]),
        ("multiple_crowd_detections", [ordinary,crowd], [correct,inside,second], [2,2,2], [0,0,0]),
        ("background_error", [ordinary,crowd], [correct,background], [1,1,1], [1,1,1]),
        ("crowd_and_background", [ordinary,crowd], [correct,inside,background], [2,2,2], [1,1,1]),
        ("crowd_only_detection", [crowd], [inside], [1,1,1], [0,0,0]),
        ("crowd_only_empty", [crowd], [], None, None),
        ("empty_query", [], [], None, None),
        ("negative_query_detection", [], [background], [1,1,1], [1,1,1]),
        ("missed_ordinary", [ordinary,crowd], [], [0,0,0], [0,0,0]),
        ("low_confidence_crowd", [ordinary,crowd], [correct,([22,22,4,4],.49)], [0,0,0], [0,0,0]),
        ("score_threshold_inclusive", [ordinary,crowd], [correct,([22,22,4,4],.5)], [1,1,1], [0,0,0]),
        ("ordinary_match_overlapping_crowd", [ordinary,([0,0,20,20],True)], [correct], [0,0,0], [0,0,0]),
        ("crowd_overlap_half", [ordinary,crowd], [correct,([18,22,4,4],.9)], [1,1,1], [0,1,1]),
        ("crowd_overlap_below_half", [ordinary,crowd], [correct,([17,22,4,4],.9)], [1,1,1], [1,1,1]),
        ("duplicate_ordinary_without_crowd", [ordinary], [correct,correct], [1,1,1], [1,1,1]),
    ]


def run_demo(candidate_override=None):
    original = SOURCE.read_text()
    patched = candidate_override if candidate_override is not None else candidate_source(original)
    baseline, candidate = methods(original), methods(patched)
    results = []
    for mode in ("bbox", "bitmap"):
        base_images, candidate_images = [], []
        for index, (name, gt, dt, expected_b, expected_c) in enumerate(fixtures(), 1):
            before, after = evaluate(baseline, gt, dt, mode), evaluate(candidate, gt, dt, mode)
            bp, ap = plain(before), plain(after)
            unchanged = all(bp[k] == ap[k] for k in ("IL_TP", "IL_FP", "IL_TN", "IL_FN", "num_dt"))
            passed = bp.get("FPs") == expected_b and ap.get("FPs") == expected_c and unchanged and bp.get("TPs") == ap.get("TPs") and bp.get("FNs") == ap.get("FNs")
            results.append({"name": name, "mode": mode, "passed": passed,
                            "before": bp, "after": ap, "expected_before_fp": expected_b,
                            "expected_after_fp": expected_c, "classification_preserved": unchanged})
            before["image_id"] = after["image_id"] = index
            base_images.append(before)
            candidate_images.append(after)
        for ns, images in ((baseline, base_images), (candidate, candidate_images)):
            obj = types.SimpleNamespace(params=types.SimpleNamespace(iouThrs=np.array([.5,.75,.95]),imgIds=list(range(1,len(images)+1))),evalImgs=images)
            ns["accumulate"](obj)
            if ns is baseline:
                aggregate_before = plain({k:v for k,v in obj.eval.items() if k!="params"})
            else:
                aggregate_after = plain({k:v for k,v in obj.eval.items() if k!="params"})
        if mode == "bbox":
            aggregate = {"before": aggregate_before, "after": aggregate_after}
    rng = np.random.default_rng(585)
    invariant_passes = 0
    for _ in range(500):
        gt = [(rng.integers(0,40,4).tolist(), False) for _ in range(int(rng.integers(0,4)))]
        dt = [(rng.integers(0,40,4).tolist(), float(rng.random())) for _ in range(int(rng.integers(0,5)))]
        before, after = evaluate(baseline, gt, dt, "bbox"), evaluate(candidate, gt, dt, "bbox")
        invariant_passes += plain(before) == plain(after)
    patch = "".join(difflib.unified_diff(original.splitlines(True), patched.splitlines(True),
                    fromfile="a/sam3/eval/cgf1_eval.py", tofile="b/sam3/eval/cgf1_eval.py"))
    record = {
        "kind": "sam3_demo", "status": "conditional_local_pass" if all(r["passed"] for r in results) and invariant_passes == 500 else "failed",
        "issue_url": "https://github.com/facebookresearch/sam3/issues/585", "revision": REVISION,
        "source_sha256": digest(original.encode()), "candidate_sha256": digest(patched.encode()),
        "evidence_level": "executed_reviewed_fixtures", "model_involvement": "external_candidate_under_test" if candidate_override is not None else "none_in_this_run",
        "fixture_count": len(results), "passed_fixtures": sum(r["passed"] for r in results),
        "no_crowd_invariants": {"passed": invariant_passes, "total": 500},
        "results": results, "aggregate": aggregate,
        "policy": {"status": "provisional", "maintainer_endorsed": False,
                   "crowd_only_classification": "existing behavior preserved; semantics unresolved"},
        "limitations": ["Method-level evaluator test, not full CGF1Evaluator/pycocotools execution.",
                       "Bitmap geometry uses tiny binary masks, not compressed COCO RLE.",
                       "Exhaustive assignment adapter replaces SciPy for at most seven objects.",
                       "Candidate supplied by a separate proposal record." if candidate_override is not None else "The candidate is a reviewed built-in patch; no Meta model generated it in this run.",
                       "No model inference, dataset-scale performance, or upstream policy endorsement established."],
    }
    return record, {"candidate.patch": patch, "source.py": original, "candidate.py": patched}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate",type=Path)
    args = parser.parse_args()
    result, files = run_demo(args.candidate.read_text() if args.candidate else None)
    print(json.dumps({"record":result,"files":files}, ensure_ascii=False, allow_nan=False))
