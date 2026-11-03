let state={token:'',run:null,integrity:null,mode:'bbox',tab:'results',busy:false,execution:null,supporting:{}};
const $=id=>document.getElementById(id);
function text(id,value){$(id).textContent=value??'';}
function notice(message,error=false){text('notice',message);$('notice').hidden=false;$('notice').classList.toggle('error',error);}
async function api(path,data){
  if(window.OPENFIX_REPORT){
    if(data)throw new Error('This is an exported execution report. Start the local OpenFix app for new runs or live Meta requests.');
    if(path==='/api/status')return {token:'export',model:{configured:false,model:'Exported execution evidence'}};
    if(path==='/api/runs')return {runs:[{id:window.OPENFIX_REPORT.run.id,created_at:window.OPENFIX_REPORT.run.created_at,kind:window.OPENFIX_REPORT.run.record.kind,status:window.OPENFIX_REPORT.run.record.status}]};
    if(path.startsWith('/api/runs/'))return window.OPENFIX_REPORT;
    throw new Error('Unavailable in exported report');
  }
  const response=await fetch(path,data?{method:'POST',headers:{'Content-Type':'application/json','X-OpenFix-Token':state.token},body:JSON.stringify(data)}:{});
  const value=await response.json();
  if(!response.ok)throw new Error(value.error||'Request failed');
  return value;
}
function busy(value){state.busy=value;document.querySelectorAll('button').forEach(button=>button.disabled=value);}
async function task(label,fn){if(state.busy)return;busy(true);notice(label);try{await fn();}catch(error){notice(error.message,true);}finally{busy(false);}}
function label(value){return value.replaceAll('_',' ').replace(/^./,character=>character.toUpperCase());}
function isPass(status){return ['conditional_local_pass','passed','proposal_ready'].includes(status);}
function download(name,value,type='text/plain'){const anchor=document.createElement('a');anchor.href=URL.createObjectURL(new Blob([value],{type}));anchor.download=name;anchor.click();setTimeout(()=>URL.revokeObjectURL(anchor.href),1000);}

async function history(loadLatest=false){
  const {runs}=await api('/api/runs');
  $('history').replaceChildren();
  for(const run of runs.slice(0,9)){
    const item=document.createElement('div');
    item.className='history-item '+(isPass(run.status)?'history-pass':'history-warn');
    if(state.run?.id===run.id)item.classList.add('active');
    item.tabIndex=0;
    item.dataset.runId=run.id;
    item.setAttribute('role','button');
    const title=document.createElement('span');
    title.textContent=label(run.kind||'Investigation');
    const small=document.createElement('small');
    small.textContent=label(run.status||'Saved')+' · '+new Date(run.created_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
    item.append(title,small);
    item.onclick=()=>task('Loading evidence…',async()=>{await show(await api('/api/runs/'+run.id));await history();notice('Saved evidence loaded.');});
    item.onkeydown=event=>{if(event.key==='Enter')item.click();};
    $('history').append(item);
  }
  if(loadLatest&&runs[0])await show(await api('/api/runs/'+runs[0].id));
}

function setTab(tab){
  state.tab=tab;
  document.querySelectorAll('.tab').forEach(button=>{button.classList.toggle('active',button.dataset.tab===tab);button.setAttribute('aria-selected',button.dataset.tab===tab);});
  document.querySelectorAll('.tab-panel').forEach(panel=>panel.hidden=panel.id!=='tab-'+tab);
}
function executionRecord(){
  const record=state.execution?.record||state.run?.record||{};
  return record.kind==='model_verification'?(record.test_results||{}):record;
}
function renderJourney(record){
  const journey=$('workflow-journey');
  journey.replaceChildren();
  if(record.kind!=='meta_workflow'){journey.hidden=true;return;}
  journey.hidden=false;
  for(const stage of record.stages||[]){
    const item=document.createElement('div');
    item.className='journey-step '+(isPass(stage.status)?'done':'attention');
    const mark=document.createElement('span');
    mark.textContent=isPass(stage.status)?'✓':'!';
    const copy=document.createElement('div');
    const strong=document.createElement('strong');
    strong.textContent=label(stage.stage.replace(/_\d+$/,''));
    const small=document.createElement('small');
    small.textContent=label(stage.status);
    copy.append(strong,small);
    item.append(mark,copy);
    journey.append(item);
  }
}
function renderOutcome(record,executed){
  const passed=record.status==='conditional_local_pass';
  text('outcome-kicker',record.kind==='meta_workflow'?'LIVE META WORKFLOW':'RECORDED EVIDENCE');
  text('outcome-title',passed?(record.kind==='meta_workflow'?'Meta candidate passed the reviewed verification scope':'Candidate passed the reviewed verification scope'):label(record.status||'Evidence loaded'));
  const hasChecks=executed.fixture_count&&executed.no_crowd_invariants;
  text('outcome-copy',passed&&hasChecks?`The executed candidate passed ${executed.passed_fixtures}/${executed.fixture_count} geometry fixtures and ${executed.no_crowd_invariants.passed}/${executed.no_crowd_invariants.total} compatibility checks. The policy remains provisional pending maintainer guidance.`:record.kind.startsWith('model_')?'This is a model hypothesis. Select a verification record before treating it as executed evidence.':'Open the evidence details to inspect provenance, limits, and recorded stages.');
  text('outcome-badge',passed?'CONDITIONAL PASS':label(record.status||'RECORDED'));
  $('outcome-card').classList.toggle('attention',!passed);
}
function table(){
  const record=executionRecord();
  $('fixture-table').replaceChildren();
  for(const item of (record.results||[]).filter(result=>result.mode===state.mode)){
    const row=document.createElement('tr');
    const before=item.before.FPs?.[0]??'—';
    const after=item.after.FPs?.[0]??'—';
    if(before!==after)row.className='changed';
    for(const value of [label(item.name),before,after]){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}
    const cell=document.createElement('td');
    const badge=document.createElement('span');
    badge.className='pass'+(item.passed?'':' fail');
    badge.textContent=item.passed?'PASS':'FAIL';
    cell.append(badge);row.append(cell);$('fixture-table').append(row);
  }
  const hasResults=(record.results||[]).length>0;
  text('results-title',state.run?.record.kind==='meta_workflow'?'Executed Meta candidate':'Before and after');
  text('results-tag',hasResults?'Localization false positives at overlap ≥ 0.50':'No execution results in this record');
  text('result-explanation',hasResults?'Full results retain overlap thresholds 0.50, 0.75, and 0.95. Crowd-only classification is preserved and explicitly flagged. These checks exercise selected evaluator methods, not full SAM 3 inference or dataset-scale evaluation.':'This record is a hypothesis or intake step. Select a verification or completed workflow to see executed results.');
}
async function loadStage(record,name){
  const stage=(record.stages||[]).find(item=>item.stage===name||item.stage.startsWith(name+'_'));
  if(!stage||window.OPENFIX_REPORT)return null;
  return api('/api/runs/'+stage.evidence_id);
}
async function artifactText(run){
  const artifact=run?.artifacts?.find(item=>item.name.endsWith('.patch'));
  if(!artifact)return null;
  if(window.OPENFIX_REPORT)return window.OPENFIX_REPORT.files[artifact.name];
  return fetch('/api/artifact?id='+run.id+'&name='+encodeURIComponent(artifact.name)).then(response=>response.text());
}
async function show(payload){
  state.run=payload.run;
  state.integrity=payload.integrity;
  state.execution=null;
  state.supporting={};
  $('empty-state').hidden=true;
  $('result').hidden=false;
  const record=state.run.record;
  if(record.kind==='meta_workflow'){
    const [verification,repair,challenge]=await Promise.all([loadStage(record,'candidate_verification'),loadStage(record,'meta_repair'),loadStage(record,'meta_challenge')]);
    state.execution=verification?.run||null;
    state.supporting={repair:repair?.run||null,challenge:challenge?.run||null};
  }else if(record.kind==='model_verification')state.execution=state.run;
  const executed=executionRecord();
  const demo=record.kind==='sam3_demo';
  text('metric-status',label(record.status||'Recorded'));
  text('metric-scope',record.kind==='meta_workflow'?'Live Meta workflow · repair executed in Docker':demo?'Reviewed baseline fixture execution':record.evidence_level==='model_hypothesis'?'Model proposal · not execution evidence':'Recorded investigation evidence');
  text('metric-cases',executed.fixture_count?`${executed.passed_fixtures} / ${executed.fixture_count}`:'—');
  text('metric-invariants',executed.no_crowd_invariants?`${executed.no_crowd_invariants.passed} / ${executed.no_crowd_invariants.total}`:'—');
  text('metric-integrity',payload.integrity?.passed?'Verified':'Check failed');
  text('evidence-view',JSON.stringify(payload,null,2));
  $('limitations').replaceChildren();
  for(const value of record.limitations||['Model suggestions and issue reports require execution before being treated as verified behavior.']){const item=document.createElement('li');item.textContent=value;$('limitations').append(item);}
  const challenge=state.supporting.challenge?.record;
  text('model-view',challenge?.proposal?JSON.stringify({workflow_status:record.status,final_challenge:challenge.proposal},null,2):record.proposal?JSON.stringify(record.proposal,null,2):record.raw_response||'No Meta reasoning is attached to this view.');
  let diff=await artifactText(state.run);
  if(!diff)diff=await artifactText(state.supporting.repair);
  text('patch-view',diff||'No candidate patch in this evidence record.');
  text('patch-hint',record.kind==='meta_workflow'?'Meta-generated candidate patch executed by the recorded Docker verification. The policy remains provisional.':demo?'Built-in reviewed baseline candidate under the provisional policy.':'Patch attached to this evidence record; execution status is shown above.');
  renderOutcome(record,executed);
  renderJourney(record);
  table();
  if(record.kind==='meta_workflow'||record.kind==='model_verification'||demo)setTab('results');
  else if(record.kind.startsWith('model_'))setTab('meta');
  else setTab('evidence');
  if(record.kind==='meta_workflow'&&record.status==='conditional_local_pass')text('model-status','Live Meta workflow recorded');
  document.querySelectorAll('.history-item').forEach(item=>item.classList.toggle('active',item.dataset.runId===state.run.id));
}

$('run-demo').onclick=()=>task('Running the reviewed baseline fixtures and compatibility checks…',async()=>{await show(await api('/api/demo',{}));await history();notice('Baseline verification complete. Inspect the results, candidate patch, and evidence limits.');});
$('intake-form').onsubmit=event=>{event.preventDefault();task('Reading issue and pinning source context…',async()=>{await show(await api('/api/intake',{issue_url:$('issue-url').value.trim(),source_paths:$('source-paths').value.split('\n').map(value=>value.trim()).filter(Boolean),refresh:$('fresh-intake').checked}));await history();notice('Issue intake saved. Source and claims are ready for inspection.');});};
document.querySelectorAll('.tab').forEach(button=>button.onclick=()=>setTab(button.dataset.tab));
document.querySelectorAll('[data-mode]').forEach(button=>button.onclick=()=>{state.mode=button.dataset.mode;document.querySelectorAll('[data-mode]').forEach(item=>item.classList.toggle('selected',item===button));table();});
document.querySelectorAll('[data-model-action]').forEach(button=>button.onclick=()=>task('Meta is examining the source and evidence. This request may take a minute…',async()=>{if(!state.run)throw new Error('Run verification or inspect an issue first.');const key=$('api-key').value;try{await show(await api('/api/model',{run_id:state.run.id,action:button.dataset.modelAction,api_key:key}));await history();notice('Meta response saved as an unverified proposal. Inspect its reasoning and open questions.');}finally{$('api-key').value='';}}));
$('download-record').onclick=()=>download('openfix-'+state.run.id+'.json',JSON.stringify({run:state.run,integrity:state.integrity},null,2),'application/json');
$('verify-proposal').onclick=()=>task('Staging the model patch and checking the Docker verification environment…',async()=>{if(state.run?.record.kind!=='model_repair')throw new Error('Select a Meta repair proposal from evidence history first.');await show(await api('/api/verify',{run_id:state.run.id}));await history();notice('Verification record saved. Inspect its status and execution evidence.');});
$('run-workflow').onclick=()=>task('Running the complete Meta workflow. Diagnosis, repair, verification, and challenge can take several minutes…',async()=>{const key=$('api-key').value;try{await show(await api('/api/workflow',{api_key:key}));await history();notice('Workflow finished with status: '+label(state.run.record.status)+'. Each stage is saved separately.');}finally{$('api-key').value='';}});
$('download-patch').onclick=()=>download('openfix-candidate.patch',$('patch-view').textContent);
$('refresh').onclick=()=>task('Refreshing evidence history…',async()=>{await history();notice('Evidence history refreshed.');});

(async()=>{try{
  const status=await api('/api/status');
  state.token=status.token;
  text('model-status',status.model.configured?'Meta key configured on server':'Meta key accepted per request');
  text('model-name',status.model.model);
  if(window.OPENFIX_REPORT){await show(window.OPENFIX_REPORT);text('model-status','Execution report · read only');notice('Exported from a real local fixture run. New runs and Meta requests require the local application.');}
  else await history(true);
}catch(error){notice(error.message,true);}})();
