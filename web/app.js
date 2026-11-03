let state={token:'',run:null,integrity:null,mode:'bbox',tab:'results',busy:false,execution:null,supporting:{},wizard:{intake:null,diagnosis:null,repair:null,model:'muse-spark-1.3'}};
const $=id=>document.getElementById(id);
let noticeTimer=null;
let museProgressTimer=null;
let museProgressHideTimer=null;
let museProgressStarted=0;
let verificationClockTimer=null;
let verificationPollTimer=null;
let verificationHideTimer=null;
let verificationStarted=0;
function text(id,value){$(id).textContent=value??'';}
function notice(message,error=false){
  clearTimeout(noticeTimer);text('notice',message);$('notice').hidden=false;$('notice').classList.toggle('error',error);
  noticeTimer=setTimeout(()=>{$('notice').hidden=true;},error?8000:4200);
}
async function api(path,data){
  if(window.OPENFIX_REPORT){
    if(data)throw new Error('This is an exported execution report. Start the local OpenFix app for new runs.');
    if(path==='/api/status')return {token:'export',model:{configured:false,model:'Exported evidence',models:[]}};
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
async function task(message,fn){if(state.busy)return;busy(true);notice(message);try{await fn();}catch(error){notice(error.message,true);}finally{busy(false);}}
function label(value){return String(value||'').replaceAll('_',' ').replace(/^./,character=>character.toUpperCase());}
function isPass(status){return ['conditional_local_pass','passed','proposal_ready','intake_only'].includes(status);}
function download(name,value,type='text/plain'){const anchor=document.createElement('a');anchor.href=URL.createObjectURL(new Blob([value],{type}));anchor.download=name;anchor.click();setTimeout(()=>URL.revokeObjectURL(anchor.href),1000);}
function openStep(number){
  for(const index of [1,2,3]){const step=$('step-'+index);if(index<=number)step.hidden=false;step.open=index===number;}
  $('step-'+number).scrollIntoView({behavior:'smooth',block:'start'});
}
function setStepStatus(number,value,kind=''){text(`step-${number}-status`,value);$(`step-${number}-status`).className='step-state '+kind;}
function progressTime(seconds){return `${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;}
function updateMuseClock(){text('muse-progress-time',progressTime(Math.floor((Date.now()-museProgressStarted)/1000)));}
function setMuseProgress(stage){
  const progress=$('muse-progress');progress.hidden=false;progress.classList.remove('error','complete');
  const diagnosis=$('muse-stage-diagnose');const repair=$('muse-stage-repair');diagnosis.className='';repair.className='';
  if(stage==='diagnose'){
    diagnosis.className='active';text('muse-progress-title','Muse is diagnosing the issue');text('muse-progress-copy','Reading the pinned source and policy questions.');
  }else if(stage==='repair'){
    diagnosis.className='done';repair.className='active';text('muse-progress-title','Diagnosis ready. Muse is generating a patch');text('muse-progress-copy','Turning the identified contract into a focused candidate repair.');
  }else if(stage==='complete'){
    diagnosis.className='done';repair.className='done';progress.classList.add('complete');text('muse-progress-title','Candidate patch ready');text('muse-progress-copy','Structured output received. Preparing it for review.');
  }
}
function startMuseProgress(){
  clearInterval(museProgressTimer);clearTimeout(museProgressHideTimer);museProgressStarted=Date.now();setMuseProgress('diagnose');updateMuseClock();museProgressTimer=setInterval(updateMuseClock,1000);
}
function finishMuseProgress(){
  clearInterval(museProgressTimer);updateMuseClock();setMuseProgress('complete');museProgressHideTimer=setTimeout(()=>{$('muse-progress').hidden=true;},1600);
}
function failMuseProgress(message){
  clearInterval(museProgressTimer);const progress=$('muse-progress');progress.hidden=false;progress.classList.add('error');text('muse-progress-title','Muse request stopped');text('muse-progress-copy',message||'Review the message and try again.');
}
const verificationPhases=['preparing','docker','challenging','recording'];
const verificationMessages={
  preparing:['Preparing the candidate','Validating scope and applying the exact proposed patch.'],
  docker:['Running isolated Docker checks','Executing geometry fixtures without network access.'],
  challenging:['Muse is challenging the evidence','Looking for unsupported claims and missing checks.'],
  recording:['Sealing the evidence record','Hashing artifacts and linking every workflow stage.'],
  complete:['Verification complete','The recorded results are ready for review.']
};
function updateVerificationClock(){text('verification-progress-time',progressTime(Math.floor((Date.now()-verificationStarted)/1000)));}
function setVerificationProgress(phase){
  const progress=$('verification-progress');progress.hidden=false;progress.classList.remove('error','complete');
  const index=verificationPhases.indexOf(phase);
  verificationPhases.forEach((name,position)=>{$(`verify-stage-${name}`).className=phase==='complete'||position<index?'done':position===index?'active':'';});
  const message=verificationMessages[phase]||verificationMessages.preparing;text('verification-progress-title',message[0]);text('verification-progress-copy',message[1]);
  if(phase==='complete')progress.classList.add('complete');
}
function startVerificationProgress(progressId){
  clearInterval(verificationClockTimer);clearInterval(verificationPollTimer);clearTimeout(verificationHideTimer);verificationStarted=Date.now();setVerificationProgress('preparing');updateVerificationClock();
  verificationClockTimer=setInterval(updateVerificationClock,1000);
  verificationPollTimer=setInterval(async()=>{try{const status=await api('/api/progress?id='+encodeURIComponent(progressId));if(status.phase&&!['complete','failed'].includes(status.phase))setVerificationProgress(status.phase);}catch{}},700);
}
function finishVerificationProgress(){clearInterval(verificationClockTimer);clearInterval(verificationPollTimer);updateVerificationClock();setVerificationProgress('complete');verificationHideTimer=setTimeout(()=>{$('verification-progress').hidden=true;},1800);}
function failVerificationProgress(message){
  clearInterval(verificationClockTimer);clearInterval(verificationPollTimer);clearTimeout(verificationHideTimer);const progress=$('verification-progress');progress.hidden=false;progress.classList.add('error');text('verification-progress-title','Verification stopped');text('verification-progress-copy',message||'Review the message and try again.');
}
function patchFigures(diff){
  const files=new Set();let additions=0;let removals=0;
  for(const line of String(diff||'').split('\n')){
    if(line.startsWith('+++ ')&&line.slice(4).trim()!=='/dev/null')files.add(line.slice(4).trim().replace(/^b\//,''));
    else if(line.startsWith('+'))additions++;
    if(line.startsWith('-')&&!line.startsWith('--- '))removals++;
  }
  return {files:files.size,additions,removals};
}
async function copyProposal(){
  const value=$('proposal-view').textContent;if(!value)return;
  try{await navigator.clipboard.writeText(value);}catch{
    const area=document.createElement('textarea');area.value=value;area.style.position='fixed';area.style.opacity='0';document.body.append(area);area.select();document.execCommand('copy');area.remove();
  }
  const button=$('copy-proposal');button.firstChild.textContent='Copied ';setTimeout(()=>{button.firstChild.textContent='Copy patch ';},1600);notice('Candidate patch copied.');
}

async function history(){
  const {runs}=await api('/api/runs');
  $('history').replaceChildren();
  for(const run of runs.slice(0,9)){
    const item=document.createElement('div');
    item.className='history-item '+(isPass(run.status)?'history-pass':'history-warn');
    if(state.run?.id===run.id)item.classList.add('active');
    item.tabIndex=0;item.dataset.runId=run.id;item.setAttribute('role','button');
    const title=document.createElement('span');title.textContent=label(run.kind||'Investigation');
    const small=document.createElement('small');small.textContent=label(run.status||'Saved')+' · '+new Date(run.created_at).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
    item.append(title,small);
    item.onclick=()=>task('Loading saved evidence…',async()=>{await show(await api('/api/runs/'+run.id));await history();notice('Saved evidence loaded.');});
    item.onkeydown=event=>{if(event.key==='Enter')item.click();};
    $('history').append(item);
  }
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
  const journey=$('workflow-journey');journey.replaceChildren();
  if(record.kind!=='meta_workflow'){journey.hidden=true;return;}
  journey.hidden=false;
  for(const stage of record.stages||[]){
    const item=document.createElement('div');item.className='journey-step '+(isPass(stage.status)?'done':'attention');
    const mark=document.createElement('span');mark.textContent=isPass(stage.status)?'✓':'!';
    const copy=document.createElement('div');const strong=document.createElement('strong');strong.textContent=label(stage.stage.replace(/_\d+$/,''));
    const small=document.createElement('small');small.textContent=label(stage.status);copy.append(strong,small);item.append(mark,copy);journey.append(item);
  }
}
function renderOutcome(record,executed){
  const passed=record.status==='conditional_local_pass';
  text('outcome-kicker',record.kind==='meta_workflow'?'COMPLETED INVESTIGATION':'RECORDED EVIDENCE');
  text('outcome-title',passed?'Candidate passed the reviewed verification scope':label(record.status||'Evidence loaded'));
  const hasChecks=executed.fixture_count&&executed.no_crowd_invariants;
  text('outcome-copy',passed&&hasChecks?`The exact candidate passed ${executed.passed_fixtures}/${executed.fixture_count} geometry fixtures and ${executed.no_crowd_invariants.passed}/${executed.no_crowd_invariants.total} compatibility checks. The policy remains provisional pending maintainer guidance.`:record.kind.startsWith('model_')?'This is a model hypothesis. It is not execution evidence until Step 03 completes.':'Inspect the provenance and limitations before acting on this result.');
  text('outcome-badge',passed?'CONDITIONAL PASS':label(record.status||'RECORDED'));
  $('outcome-card').classList.toggle('attention',!passed);
}
function table(){
  const record=executionRecord();$('fixture-table').replaceChildren();
  for(const item of (record.results||[]).filter(result=>result.mode===state.mode)){
    const row=document.createElement('tr');const before=item.before.FPs?.[0]??'—';const after=item.after.FPs?.[0]??'—';if(before!==after)row.className='changed';
    for(const value of [label(item.name),before,after]){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}
    const cell=document.createElement('td');const badge=document.createElement('span');badge.className='pass'+(item.passed?'':' fail');badge.textContent=item.passed?'PASS':'FAIL';cell.append(badge);row.append(cell);$('fixture-table').append(row);
  }
  const hasResults=(record.results||[]).length>0;
  text('results-title',state.run?.record.kind==='meta_workflow'?'Executed candidate':'Before and after');
  text('results-tag',hasResults?'Localization false positives at overlap ≥ 0.50':'No execution results in this record');
  text('result-explanation',hasResults?'Results retain overlap thresholds 0.50, 0.75, and 0.95. Crowd-only classification remains explicitly flagged. These checks exercise selected evaluator methods, not full SAM 3 inference or dataset-scale evaluation.':'Select a completed workflow or verification record to see executed results.');
}
async function loadStage(record,name){const stage=(record.stages||[]).find(item=>item.stage===name||item.stage.startsWith(name+'_'));if(!stage||window.OPENFIX_REPORT)return null;return api('/api/runs/'+stage.evidence_id);}
async function artifactText(run){const artifact=run?.artifacts?.find(item=>item.name.endsWith('.patch'));if(!artifact)return null;if(window.OPENFIX_REPORT)return window.OPENFIX_REPORT.files[artifact.name];return fetch('/api/artifact?id='+run.id+'&name='+encodeURIComponent(artifact.name)).then(response=>response.text());}

async function show(payload){
  state.run=payload.run;state.integrity=payload.integrity;state.execution=null;state.supporting={};
  const record=state.run.record;
  if(record.kind==='meta_workflow'){
    const [verification,repair,challenge]=await Promise.all([loadStage(record,'candidate_verification'),loadStage(record,'meta_repair'),loadStage(record,'meta_challenge')]);
    state.execution=verification?.run||null;state.supporting={repair:repair?.run||null,challenge:challenge?.run||null};
  }else if(record.kind==='model_verification')state.execution=state.run;
  const executed=executionRecord();
  $('result').hidden=false;$('verification-intro').hidden=true;openStep(3);
  setStepStatus(1,'ISSUE READY','complete');setStepStatus(2,'CANDIDATE READY','complete');setStepStatus(3,label(record.status||'RECORDED').toUpperCase(),isPass(record.status)?'complete':'attention');
  text('metric-status',label(record.status||'Recorded'));
  text('metric-scope',record.kind==='meta_workflow'?'Muse candidate · isolated Docker execution':record.evidence_level==='model_hypothesis'?'Model proposal · not execution evidence':'Recorded investigation evidence');
  text('metric-cases',executed.fixture_count?`${executed.passed_fixtures} / ${executed.fixture_count}`:'—');
  text('metric-invariants',executed.no_crowd_invariants?`${executed.no_crowd_invariants.passed} / ${executed.no_crowd_invariants.total}`:'—');
  text('metric-integrity',payload.integrity?.passed?'Verified':'Check failed');
  text('evidence-view',JSON.stringify(payload,null,2));
  $('limitations').replaceChildren();for(const value of record.limitations||['Model suggestions require execution before they become behavioral evidence.']){const item=document.createElement('li');item.textContent=value;$('limitations').append(item);}
  const challenge=state.supporting.challenge?.record;
  text('model-view',challenge?.proposal?JSON.stringify(challenge.proposal,null,2):record.proposal?JSON.stringify(record.proposal,null,2):record.raw_response||'No model challenge is attached to this view.');
  text('model-name',record.model||challenge?.model||'Muse');
  let diff=await artifactText(state.run);if(!diff)diff=await artifactText(state.supporting.repair);
  text('patch-view',diff||'No candidate patch in this evidence record.');
  text('patch-hint',record.kind==='meta_workflow'?'Muse-generated candidate patch executed by the recorded Docker verification. The policy remains provisional.':'Patch attached to this evidence record; execution status is shown above.');
  renderOutcome(record,executed);renderJourney(record);table();setTab('results');
  document.querySelectorAll('.history-item').forEach(item=>item.classList.toggle('active',item.dataset.runId===state.run.id));
}

function renderIssue(record){
  text('issue-title','SAM 3 · Crowd annotations and false positives');text('issue-body',record.issue_body||record.title||'Issue context loaded.');
  try{const url=new URL(record.issue_url);text('issue-repository',url.pathname.split('/').slice(1,3).join('/'));}catch{text('issue-repository','Public GitHub repository');}
  text('issue-revision',(record.revision||'not pinned').slice(0,12));text('issue-questions',(record.policy_questions||[]).join(' · ')||'Review the recorded issue context.');
  $('issue-preview').hidden=false;setStepStatus(1,'INSPECTED','complete');
}

$('intake-form').onsubmit=event=>{event.preventDefault();task('Inspecting the issue and pinning source context…',async()=>{
  const payload=await api('/api/intake',{issue_url:$('issue-url').value.trim(),source_paths:$('source-paths').value.split('\n').map(value=>value.trim()).filter(Boolean),refresh:$('fresh-intake').checked});
  state.wizard.intake=payload.run;renderIssue(payload.run.record);await history();notice('Issue inspected. Review the context, then choose whether to ask Muse for a repair.');$('solve-dialog').showModal();
});};
function advanceToMuse(){setStepStatus(1,'ISSUE READY','complete');$('step-2').hidden=false;setTimeout(()=>openStep(2),0);}
$('confirm-solve').onclick=advanceToMuse;
$('continue-muse').onclick=advanceToMuse;

const modelInputs=[...document.querySelectorAll('input[name="muse-model"]')];
function selectedModel(){return modelInputs.find(input=>input.checked)||modelInputs[0];}
modelInputs.forEach(input=>input.onchange=()=>{state.wizard.model=selectedModel().value;});
$('generate-candidate').onclick=()=>task('Muse is diagnosing the issue and generating a focused candidate patch…',async()=>{
  if(!state.wizard.intake)throw new Error('Complete Step 01 before asking Muse for a repair.');
  const apiKey=$('api-key').value;const selection=selectedModel();const model=selection.value;state.wizard.model=model;setStepStatus(2,'MUSE WORKING');startMuseProgress();
  try{
    const diagnosis=await api('/api/model',{run_id:state.wizard.intake.id,action:'diagnose',api_key:apiKey,model});
    if(diagnosis.run.record.status!=='proposal_ready')throw new Error('Muse diagnosis was not valid structured output. Inspect the saved evidence and try again.');
    state.wizard.diagnosis=diagnosis.run;setMuseProgress('repair');
    const repair=await api('/api/model',{run_id:diagnosis.run.id,action:'repair',api_key:apiKey,model});
    if(repair.run.record.status!=='proposal_ready')throw new Error('Muse did not return a valid candidate patch. Inspect the saved evidence and try again.');
    state.wizard.repair=repair.run;
    const modelName=selection.dataset.name;
    text('diagnosis-summary',`${modelName} identified a candidate contract violation.`);text('repair-summary','Structured patch ready · not executed yet');
    const diff=repair.run.record.proposal.unified_diff;const figures=patchFigures(diff);
    text('proposal-view',diff);text('candidate-files',figures.files);text('candidate-additions',`+${figures.additions}`);text('candidate-removals',`−${figures.removals}`);$('candidate-preview').hidden=false;setStepStatus(2,'CANDIDATE READY','complete');finishMuseProgress();await history();notice('Candidate generated. Inspect the patch, then continue to the execution gate.');
  }catch(error){setStepStatus(2,'TRY AGAIN','attention');failMuseProgress(error.message);throw error;}
});
$('copy-proposal').onclick=copyProposal;
$('continue-verify').onclick=()=>{setStepStatus(2,'CANDIDATE READY','complete');$('step-3').hidden=false;openStep(3);};
$('verify-candidate').onclick=()=>task('Executing the candidate in isolated Docker, then asking Muse to challenge the evidence…',async()=>{
  if(!state.wizard.repair)throw new Error('Complete Step 02 before verification.');
  setStepStatus(3,'VERIFYING');const progressId=globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random().toString(16).slice(2)}`;startVerificationProgress(progressId);
  try{
    const payload=await api('/api/finalize',{repair_id:state.wizard.repair.id,api_key:$('api-key').value,model:state.wizard.model,progress_id:progressId});
    $('api-key').value='';await show(payload);finishVerificationProgress();await history();notice('Verification and challenge complete. Review what passed and what remains uncertain.');
  }catch(error){setStepStatus(3,'TRY AGAIN','attention');failVerificationProgress(error.message);throw error;}
});

document.querySelectorAll('.tab').forEach(button=>button.onclick=()=>setTab(button.dataset.tab));
document.querySelectorAll('[data-mode]').forEach(button=>button.onclick=()=>{state.mode=button.dataset.mode;document.querySelectorAll('[data-mode]').forEach(item=>item.classList.toggle('selected',item===button));table();});
$('download-record').onclick=()=>download('openfix-'+state.run.id+'.json',JSON.stringify({run:state.run,integrity:state.integrity},null,2),'application/json');
$('download-patch').onclick=()=>download('openfix-candidate.patch',$('patch-view').textContent);
$('refresh').onclick=()=>task('Refreshing past evidence…',async()=>{await history();notice('Past evidence refreshed.');});
$('reset-workflow').onclick=()=>window.location.reload();

(async()=>{try{
  const status=await api('/api/status');state.token=status.token;state.wizard.model=status.model.model||'muse-spark-1.3';
  const configuredModel=modelInputs.find(input=>input.value===state.wizard.model);if(configuredModel)configuredModel.checked=true;else state.wizard.model=selectedModel().value;
  text('model-status',`${status.model.models?.length||3} Muse models · key per request`);
  await history();
  if(window.OPENFIX_REPORT){await show(window.OPENFIX_REPORT);text('model-status','Execution report · read only');notice('This is a recorded execution report.');}
}catch(error){notice(error.message,true);}})();
