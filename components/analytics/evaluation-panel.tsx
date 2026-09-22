'use client';
import {useEffect,useState} from 'react';
import {CheckCircle2, FlaskConical, LoaderCircle, ShieldCheck, TriangleAlert} from 'lucide-react';
import {api,number} from '@/lib/api';
import {eligibleEvaluationFeature} from '@/lib/evaluation';
import type {Dataset,EvaluationDefinition,EvaluationRun,Readiness} from '@/lib/types';

export function ReadinessSummary({report}:{report:Readiness}) {
  return <section className="evaluation-card" aria-label="Data readiness"><div className="evaluation-title">{report.ready?<CheckCircle2 size={19}/>:<TriangleAlert size={19}/>}<h2>{report.ready?'Ready for a pilot evaluation':'Resolve before evaluation'}</h2></div>
    <div className="evaluation-counts">{[['Known outcomes',report.knownRows],['Unknown · excluded',report.unknownRows],['True',report.positiveRows],['False',report.negativeRows]].map(([label,value])=><div key={label}><strong>{number(Number(value))}</strong><span>{label}</span></div>)}</div>
    {report.issues.length>0&&<ul className="evaluation-issues">{report.issues.map((issue,i)=><li key={`${issue.code}-${i}`} className={issue.severity}><strong>{issue.severity==='blocker'?'Action needed':'Keep in mind'}{issue.columnKey?` · ${report.features.find(f=>f.key===issue.columnKey)?.name??issue.columnKey}`:''}</strong><p>{issue.message}</p></li>)}</ul>}
    {report.features.length>0&&<div className="evaluation-table-scroll"><table className="evaluation-table"><caption>Input coverage</caption><thead><tr><th>Input</th><th>Known outcomes</th><th>Unknown outcomes</th></tr></thead><tbody>{report.features.map(f=><tr key={f.key}><th>{f.name}</th><td>{number(f.knownCoverage)}%</td><td>{f.unknownCoverage===null?'—':`${number(f.unknownCoverage)}%`}</td></tr>)}</tbody></table></div>}
  </section>;
}

export function EvaluationResult({run}:{run:EvaluationRun}) {
  return <section className="evaluation-card" aria-label="Evaluation result"><div className="evaluation-title"><FlaskConical size={19}/><h2>Recorded-status comparison</h2><span className="evaluation-tag">Pilot</span></div>
    <p className="evaluation-muted">{run.readiness.targetName} · {new Date(run.createdAt).toLocaleString()}</p>
    <dl className="evaluation-definition"><div><dt>True means</dt><dd>{run.definition.positiveMeaning}</dd></div><div><dt>False means</dt><dd>{run.definition.negativeMeaning}</dd></div></dl>
    <p>{number(run.trainRows)} examples · {number(run.testRows)} withheld records · {number(run.testPositiveRows)} true outcomes in the test</p>
    <div className="evaluation-table-scroll"><table className="evaluation-table"><caption>Measured on the same withheld records</caption><thead><tr><th>Method</th><th>Ranking</th><th>Average precision</th><th>Probability error</th></tr></thead><tbody>{run.models.map(m=><tr key={m.name}><th>{m.name}</th><td>{m.rocAuc.toFixed(3)}</td><td>{m.averagePrecision.toFixed(3)}</td><td>{m.brier.toFixed(3)}</td></tr>)}</tbody></table></div>
    <p className="evaluation-muted">Ranking is ROC AUC: 0.5 is chance, 1 is perfect. Higher average precision and lower probability error (Brier score) are better. These are not accuracy percentages.</p>
    <ul className="evaluation-limitations">{run.limitations.map(text=><li key={text}>{text}</li>)}</ul>
    <details><summary>Readiness and reproducibility</summary><p className="evaluation-muted">Fixed stratified 75/25 holdout · seed {run.seed} · {run.algorithmVersion}. Category counts are learned on training records only.</p><ReadinessSummary report={run.readiness}/></details>
  </section>;
}

export function EvaluationPanel({dataset}:{dataset:Dataset}) {
  const [definition,setDefinition]=useState<EvaluationDefinition>({targetKey:'',featureKeys:[],purpose:'snapshot',positiveMeaning:'',negativeMeaning:'',labelsConfirmed:false,featuresConfirmed:false,categoriesReviewed:false});
  const [readiness,setReadiness]=useState<Readiness|null>(null);
  const [history,setHistory]=useState<EvaluationRun[]>([]);
  const [result,setResult]=useState<EvaluationRun|null>(null);
  const [busy,setBusy]=useState<'check'|'run'|null>(null);
  const [error,setError]=useState('');
  const [historyLoading,setHistoryLoading]=useState(true);
  const [historyError,setHistoryError]=useState('');
  useEffect(()=>{
    let active=true;
    void api<EvaluationRun[]>(`/datasets/${dataset.id}/evaluations`).then(r=>{if(active)setHistory(r);}).catch(e=>{if(active)setHistoryError((e as Error).message);}).finally(()=>{if(active)setHistoryLoading(false);});
    return ()=>{active=false;};
  },[dataset.id]);
  const outcomes=dataset.columns.filter(c=>c.queryable&&!c.sensitive&&c.type==='boolean');
  const inputs=dataset.columns.filter(c=>eligibleEvaluationFeature(c,definition.targetKey));
  const canCheck=!!definition.targetKey&&definition.featureKeys.length>0&&definition.positiveMeaning.trim().length>=3&&definition.negativeMeaning.trim().length>=3;
  function change(patch:Partial<EvaluationDefinition>) {setDefinition(d=>({...d,...patch}));setReadiness(null);setResult(null);setError('');}
  async function check() {
    setBusy('check');setError('');setResult(null);
    try{setReadiness(await api<Readiness>(`/datasets/${dataset.id}/readiness`,{method:'POST',body:JSON.stringify(definition)}));}
    catch(e){setReadiness(null);setError((e as Error).message);}finally{setBusy(null);}
  }
  async function run() {
    if(!readiness?.ready)return;
    setBusy('run');setError('');
    try{const r=await api<EvaluationRun>(`/datasets/${dataset.id}/evaluations`,{method:'POST',body:JSON.stringify(definition)});setResult(r);setHistory(h=>[r,...h].slice(0,20));}
    catch(e){setError((e as Error).message);}finally{setBusy(null);}
  }
  return <div className="evaluation-panel"><div className="evaluation-intro"><FlaskConical size={23}/><div><h2>Is your data ready to learn from?</h2><p>Define an outcome, check the evidence, then compare two simple methods. This pilot measures recorded status; it does not score new leads.</p></div></div>
    <section className="evaluation-card"><h2>1. Define your comparison</h2>{!outcomes.length?<p>This dataset has no unprotected true/false outcome. Upload a sheet with a binary outcome to use this pilot.</p>:<fieldset disabled={!!busy} className="evaluation-form"><label>Outcome column<select value={definition.targetKey} onChange={e=>change({targetKey:e.target.value,featureKeys:definition.featureKeys.filter(k=>k!==e.target.value),labelsConfirmed:false,featuresConfirmed:false,categoriesReviewed:false})}><option value="">Choose a true/false column</option>{outcomes.map(c=><option key={c.key} value={c.key}>{c.name}</option>)}</select></label>
      <label>What are you evaluating?<select value={definition.purpose} onChange={e=>change({purpose:e.target.value as EvaluationDefinition['purpose']})}><option value="snapshot">Status recorded in this export</option><option value="future">A future outcome</option></select></label>
      {definition.purpose==='future'&&<p className="evaluation-callout">Future predictions need historical inputs, a time window and enough follow-up. This pilot will flag that setup as not ready.</p>}
      <div className="evaluation-two"><label>True means<input maxLength={200} placeholder="Converted by the time of export" value={definition.positiveMeaning} onChange={e=>change({positiveMeaning:e.target.value,labelsConfirmed:false})}/></label><label>False means<input maxLength={200} placeholder="Not converted at the time of export" value={definition.negativeMeaning} onChange={e=>change({negativeMeaning:e.target.value,labelsConfirmed:false})}/></label></div>
      <div><h3>Inputs to compare <span>{definition.featureKeys.length}/12</span></h3><p className="evaluation-muted">Choose categorical or true/false fields that do not reveal the outcome. Protected data and common status fields are excluded.</p><div className="evaluation-inputs">{inputs.map(c=><label key={c.key}><input type="checkbox" checked={definition.featureKeys.includes(c.key)} disabled={!definition.featureKeys.includes(c.key)&&definition.featureKeys.length>=12} onChange={e=>change({featureKeys:e.target.checked?[...definition.featureKeys,c.key]:definition.featureKeys.filter(k=>k!==c.key),featuresConfirmed:false,categoriesReviewed:false})}/><span>{c.name}</span></label>)}{!inputs.length&&<p>No supported inputs are available for this outcome.</p>}</div></div>
      <label className="evaluation-check"><input type="checkbox" checked={definition.labelsConfirmed} onChange={e=>change({labelsConfirmed:e.target.checked})}/>These definitions match how the outcome was recorded. Blank outcomes mean unknown.</label>
      <label className="evaluation-check"><input type="checkbox" checked={definition.featuresConfirmed} onChange={e=>change({featuresConfirmed:e.target.checked})}/>I checked the input meanings and timing. They do not directly reveal or result from the outcome.</label>
      {(definition.categoriesReviewed||readiness?.issues.some(i=>i.code==='CATEGORY_COLLISION'))&&<label className="evaluation-check"><input type="checkbox" checked={definition.categoriesReviewed} onChange={e=>change({categoriesReviewed:e.target.checked})}/>I reviewed the flagged category names and confirm their distinctions are intentional. Keep them separate.</label>}
      <div className="evaluation-actions"><button className="primary-button" disabled={!canCheck||!!busy} onClick={()=>void check()}>{busy==='check'?<LoaderCircle className="spin" size={16}/>:<ShieldCheck size={16}/>}Check readiness</button><button className="evaluation-run" disabled={!readiness?.ready||!!busy} onClick={()=>void run()}>{busy==='run'?<LoaderCircle className="spin" size={16}/>:<FlaskConical size={16}/>}Run evaluation</button></div>
      <p className="evaluation-muted">Runs on your server without an external AI service. Supports up to 20,000 known outcomes. Changing setup requires a fresh readiness check.</p>
    </fieldset>}</section>
    {error&&<p className="error-banner" role="alert">{error}</p>}
    {busy&&<output>{busy==='check'?'Checking data quality…':'Evaluating withheld records and saving the comparison…'}</output>}
    {readiness&&<ReadinessSummary report={readiness}/>}
    {result&&<EvaluationResult run={result}/>}
    <section className="evaluation-card"><h2>Saved evaluations</h2>{historyLoading?<p>Loading evaluations…</p>:historyError?<p role="alert">{historyError}</p>:history.length?<div className="evaluation-history">{history.map(r=><button key={r.id} disabled={!!busy} aria-pressed={result?.id===r.id} onClick={()=>setResult(r)}><span><strong>{r.readiness.targetName}</strong><small>{new Date(r.createdAt).toLocaleString()} · {number(r.testRows)} test records</small></span><span>View results →</span></button>)}</div>:<p className="evaluation-muted">Completed comparisons will appear here, with their definitions and checks. Latest 20 runs are shown.</p>}</section>
  </div>;
}
