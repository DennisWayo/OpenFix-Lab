import io
from email.message import Message
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from openfix.__main__ import intake
from openfix.case_sam3 import run_demo
from openfix.evidence import EvidenceStore
from openfix.model import parse_object, request_model
from openfix.report import export_report
from openfix.runner import capture, docker_run
from openfix.verification import stage_patch
from openfix.web import handler_class, LoopbackThreadingHTTPServer
from openfix.workflow import investigate

ROOT = Path(__file__).resolve().parents[1]


class EvidenceTests(unittest.TestCase):
    def test_artifact_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(tmp)
            record = store.create({"kind":"test"},{"candidate.patch":"real bytes"})
            self.assertTrue(store.audit(record["id"])["passed"])
            (Path(tmp)/record["id"]/"candidate.patch").write_text("changed")
            self.assertFalse(store.audit(record["id"])["passed"])

    def test_record_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(tmp)
            record = store.create({"status":"failed"})
            path = Path(tmp)/record["id"]/"record.json"
            data=json.loads(path.read_text()); data["record"]["status"]="passed"
            path.write_text(json.dumps(data))
            self.assertFalse(store.audit(record["id"])["passed"])

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=EvidenceStore(tmp)
            with self.assertRaises(ValueError): store.read("../../private")
            with self.assertRaises(ValueError): store.create({}, {"../escape":"x"})

    def test_export_escapes_script_content_and_rejects_bad_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=EvidenceStore(Path(tmp)/"store")
            record=store.create({"kind":"intake","issue_body":"</script><script>bad()</script>"})
            path=export_report(store,record["id"],Path(tmp)/"report.html")
            self.assertNotIn("</script><script>bad()",path.read_text())
            (store.root/record["id"]/"record.json").write_text('{}')
            with self.assertRaises(ValueError): export_report(store,record["id"],path)


class RunnerTests(unittest.TestCase):
    def test_timeout_is_recorded(self):
        result=capture([sys.executable,"-c","import time; time.sleep(5)"],timeout=.15)
        self.assertEqual(result["termination"],"timeout")
        self.assertNotEqual(result["exit_code"],0)

    def test_output_limit_is_recorded(self):
        result=capture([sys.executable,"-c","print('x'*100000)"],max_bytes=1000)
        self.assertEqual(result["termination"],"output_limit")
        self.assertLessEqual(len(result["stdout"])+len(result["stderr"]),1000)

    def test_exit_failure_cannot_become_pass(self):
        result=capture([sys.executable,"-c","raise SystemExit(3)"])
        self.assertEqual(result["exit_code"],3)

    @patch("openfix.runner.shutil.which",return_value=None)
    @patch("openfix.runner.capture")
    def test_no_docker_never_falls_back_to_host(self,capture_mock,_):
        with self.assertRaises(RuntimeError): docker_run(ROOT,"a"*40,["arbitrary"],"python:3")
        capture_mock.assert_not_called()


class ModelTests(unittest.TestCase):
    @patch.dict(os.environ,{},clear=True)
    def test_missing_key_fails_before_network(self):
        with self.assertRaises(ValueError): request_model({},"source")

    @patch.dict(os.environ,{"META_API_KEY":"test-secret"},clear=True)
    @patch("openfix.model.build_opener")
    def test_live_shape_and_no_key_in_saved_record(self,opener):
        content={k:[] for k in ("failure_hypothesis","violated_contract","minimal_reproducer","verification_plan","unresolved_questions")}
        response=io.BytesIO(json.dumps({"choices":[{"message":{"content":json.dumps(content)}}],"usage":{"total_tokens":42}}).encode())
        opener.return_value.open.return_value=response
        result=request_model({"revision":"a"*40},"source")
        request=opener.return_value.open.call_args.args[0]
        self.assertEqual(request.headers["Authorization"],"Bearer test-secret")
        payload=json.loads(request.data)
        self.assertEqual(payload["messages"][0]["role"],"developer")
        self.assertEqual(result["evidence_level"],"model_hypothesis")
        self.assertEqual(result["execution"],[])
        self.assertNotIn("test-secret",json.dumps(result))

    @patch.dict(os.environ,{"META_API_KEY":"test","META_API_URL":"http://invalid"},clear=True)
    def test_non_https_endpoint_rejected(self):
        with self.assertRaises(ValueError): request_model({},"source")

    def test_invalid_response_cannot_become_structured_proposal(self):
        with self.assertRaises(ValueError): parse_object("I ran all tests!",["findings"])
        with self.assertRaises(ValueError): parse_object('{}',["findings"])
        self.assertEqual(parse_object('```json\n{"findings": []}\n```',["findings"]),{"findings":[]})


class CaseTests(unittest.TestCase):
    def test_reviewed_patch_applies_without_execution(self):
        record,files=run_demo()
        self.assertEqual(stage_patch(files['candidate.patch'],files['source.py']),files['candidate.py'])

    def test_patch_for_another_path_is_rejected(self):
        with self.assertRaises(ValueError): stage_patch('--- a/private\n+++ b/private\n@@ -1 +1 @@\n-x\n+y\n','x\n')

    def test_provisional_policy_survives_intake(self):
        record=intake(json.loads((ROOT/"examples/sam3-585.json").read_text()))
        self.assertIs(record["candidate_policy"]["maintainer_endorsed"],False)
        self.assertEqual(record["candidate_policy"]["status"],"provisional")

    def test_geometry_and_no_crowd_contract(self):
        record,files=run_demo()
        self.assertEqual(record["status"],"conditional_local_pass")
        self.assertEqual(record["passed_fixtures"],32)
        self.assertEqual(record["no_crowd_invariants"]["passed"],500)
        results={r["name"]:r for r in record["results"] if r["mode"]=="bbox"}
        self.assertEqual(results["crowd_only_detection"]["after"]["IL_FP"],True)
        self.assertEqual(results["background_error"]["after"]["FPs"],[1,1,1])
        self.assertEqual(results["crowd_overlap_half"]["after"]["FPs"],[0,1,1])
        self.assertIn("crowd_ignored",files["candidate.patch"])


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.handler=handler_class(self.tmp.name)

    def request(self,method,path,data=None,token=None,host='127.0.0.1:8765',origin=None):
        handler=self.handler.__new__(self.handler)
        handler.path=path
        handler.command=method
        handler.request_version='HTTP/1.1'
        handler.requestline=method+' '+path+' HTTP/1.1'
        handler.headers=Message()
        handler.headers['Host']=host
        if origin: handler.headers['Origin']=origin
        if token: handler.headers['X-OpenFix-Token']=token
        body=json.dumps(data).encode() if data is not None else b''
        handler.headers['Content-Length']=str(len(body))
        handler.rfile=io.BytesIO(body)
        handler.wfile=io.BytesIO()
        getattr(handler,'do_'+method)()
        header,body=handler.wfile.getvalue().split(b'\r\n\r\n',1)
        return int(header.split(b' ')[1]),json.loads(body)

    @patch("openfix.web.TCPServer.server_bind")
    def test_local_server_bind_skips_reverse_dns(self, bind):
        server=LoopbackThreadingHTTPServer.__new__(LoopbackThreadingHTTPServer)
        server.server_address=("127.0.0.1",8765)
        server.server_bind()
        bind.assert_called_once_with(server)
        self.assertEqual(server.server_name,"localhost")
        self.assertEqual(server.server_port,8765)

    def test_bundled_intake_and_integrity_routes(self):
        status,settings=self.request('GET','/api/status')
        self.assertEqual(status,200)
        status,result=self.request('POST','/api/intake',{'issue_url':'https://github.com/facebookresearch/sam3/issues/585'},settings['token'])
        self.assertEqual(status,200)
        self.assertTrue(result['integrity']['passed'])
        self.assertIn('source_files',result['run']['record'])
        run_id=result['run']['id']
        status,reloaded=self.request('GET','/api/runs/'+run_id)
        self.assertEqual(status,200)
        self.assertEqual(reloaded['run']['id'],run_id)

    def test_foreign_origin_and_host_are_blocked(self):
        self.assertEqual(self.request('GET','/api/status',host='evil.example')[0],403)
        self.assertEqual(self.request('GET','/api/status',origin='https://evil.example')[0],403)

    def test_configured_https_proxy_origin_is_allowed(self):
        origin='https://openfix.example.ts.net'
        with patch.dict(os.environ,{'OPENFIX_TRUSTED_ORIGINS':origin}):
            self.handler=handler_class(self.tmp.name)
        status,settings=self.request('GET','/api/status',host='openfix.example.ts.net')
        self.assertEqual(status,200)
        status,_=self.request('POST','/api/demo',{},settings['token'],
                              host='openfix.example.ts.net',origin=origin)
        self.assertEqual(status,200)
        self.assertEqual(self.request('GET','/api/status',host='evil.example')[0],403)

    def test_post_without_token_is_blocked(self):
        self.assertEqual(self.request('POST','/api/demo',{})[0],403)

    def test_model_request_without_key_has_clear_failure(self):
        with patch.dict(os.environ,{},clear=True):
            _,settings=self.request('GET','/api/status')
            _,intake_result=self.request('POST','/api/intake',{'issue_url':'https://github.com/facebookresearch/sam3/issues/585'},settings['token'])
            status,result=self.request('POST','/api/model',{'run_id':intake_result['run']['id']},settings['token'])
            self.assertEqual(status,400)
            self.assertIn('META_API_KEY',result['error'])


class WorkflowTests(unittest.TestCase):
    @patch.dict(os.environ,{},clear=True)
    def test_key_required_before_workflow_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError): investigate(EvidenceStore(tmp))

    @patch('openfix.workflow.verify_proposal')
    @patch('openfix.workflow.request_model')
    def test_blocked_verification_stays_blocked_despite_model_review(self,model,verify):
        with tempfile.TemporaryDirectory() as tmp:
            store=EvidenceStore(tmp)
            def response(record,source,**kwargs):
                action=kwargs['action']
                return {'kind':'model_'+action,'status':'proposal_ready','proposal':{'unified_diff':'test diff'} if action=='repair' else {'verdict':'looks good'},'execution':[]}
            model.side_effect=response
            verify.side_effect=lambda *args:store.create({'kind':'model_verification','status':'verification_blocked','reason':'Docker unavailable','execution':[]})
            result=investigate(store,api_key='test-key')
            self.assertEqual(result['record']['status'],'verification_blocked')
            self.assertEqual(len(result['record']['stages']),5)
            self.assertNotIn('test-key',json.dumps(result))
            self.assertEqual(model.call_count,3)


if __name__=="__main__":
    unittest.main()
