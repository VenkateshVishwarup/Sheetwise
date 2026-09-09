'use client';
import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowUpRight, Bookmark, ChartNoAxesCombined, Check, ChevronDown, ChevronRight, Columns3, FileSpreadsheet, LayoutDashboard, LoaderCircle, LockKeyhole, LogOut, MessageSquare, Plus, Search, ShieldCheck, Sparkles, Table2, Upload, Users, X, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { UploadDialog } from '@/components/analytics/upload-dialog';
import { AnalyticsSurface } from '@/components/analytics/catalog';
import { ChatPanel, SqlDisclosure } from '@/components/analytics/chat-panel';
import { DataExplorer } from '@/components/analytics/data-explorer';
import { api, number } from '@/lib/api';
import type { Answer, Dataset, Status } from '@/lib/types';

type View='overview'|'data'|'saved';
export default function Home() {
  const [status,setStatus]=useState<Status|null>(null);
  const [datasets,setDatasets]=useState<Dataset[]>([]);
  const [dataset,setDataset]=useState<Dataset|null>(null);
  const [answers,setAnswers]=useState<Answer[]>([]);
  const [view,setView]=useState<View>('overview');
  const [uploadOpen,setUploadOpen]=useState(false);
  const [loading,setLoading]=useState(true);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [chatError,setChatError]=useState('');
  const [pendingQuestion,setPendingQuestion]=useState('');
  const [chatOpen,setChatOpen]=useState(false);
  const [password,setPassword]=useState('');
  const [loginBusy,setLoginBusy]=useState(false);
  const [warningsOpen,setWarningsOpen]=useState(false);
  const [search,setSearch]=useState('');
  const requestId=useRef(0);

  async function selectDataset(id:string) {
    const version=++requestId.current;setLoading(true);setError('');setChatError('');setWarningsOpen(false);
    try { const [p,a]=await Promise.all([api<Dataset>(`/datasets/${id}`),api<Answer[]>(`/datasets/${id}/answers`)]);if(version===requestId.current){setDataset(p);setAnswers(a);setView('overview');} }
    catch(e){if(version===requestId.current)setError((e as Error).message);} finally{if(version===requestId.current)setLoading(false);}
  }
  async function initialize() {
    try {const s=await api<Status>('/status');setError('');setStatus(s);if(!s.authenticated){setLoading(false);return;}const list=await api<Dataset[]>('/datasets');setDatasets(list);if(list.length)await selectDataset(list[0].id);else setLoading(false);}
    catch(e){setError((e as Error).message);setLoading(false);}
  }
  // Initial data loading updates state as requests complete; no render-derived state is synchronized.
  // oxlint-disable-next-line react/react-compiler
  useEffect(()=>{void initialize();},[]);
  async function uploaded(p:Dataset) {setDataset(p);setAnswers([]);setView('overview');setLoading(false);setError('');setDatasets(await api<Dataset[]>('/datasets'));}
  async function demo() {setLoading(true);setError('');try{await uploaded(await api<Dataset>('/demo',{method:'POST'}));}catch(e){setError((e as Error).message);setLoading(false);}}
  async function ask(question:string) {
    if(!dataset||busy)return;
    setBusy(true);setChatError('');setPendingQuestion(question);setChatOpen(true);
    try{const answer=await api<Answer>(`/datasets/${dataset.id}/chat`,{method:'POST',body:JSON.stringify({question})});setAnswers(a=>[...a,answer]);}
    catch(e){setChatError((e as Error).message);}finally{setBusy(false);}
  }
  async function pin(answer:Answer) {
    if(!dataset)return;
    try{await api(`/datasets/${dataset.id}/pins`,{method:'POST',body:JSON.stringify({answerId:answer.id,pinned:!answer.pinned})});setAnswers(a=>a.map(x=>x.id===answer.id?{...x,pinned:!x.pinned}:x));}
    catch(e){setError((e as Error).message);}
  }
  async function login(e:React.SyntheticEvent<HTMLFormElement>) {e.preventDefault();setLoginBusy(true);setError('');try{await api('/session',{method:'POST',body:JSON.stringify({password})});setPassword('');await initialize();}catch(e){setError((e as Error).message);}finally{setLoginBusy(false);}}
  const pins=answers.filter(a=>a.pinned);
  const available=dataset?.columns.filter(c=>c.queryable).length??0;
  const coverage=dataset?.columns.length?dataset.columns.reduce((sum,c)=>sum+c.coverage,0)/dataset.columns.length:0;
  const shownDatasets=datasets.filter(d=>d.name.toLowerCase().includes(search.toLowerCase()));
  if(status&&!status.authenticated)return <div className="login-screen"><form className="login-card" onSubmit={login}><div className="brand"><span className="brand-mark"><ChartNoAxesCombined size={23}/></span>sheetwise<span className="brand-dot">.</span></div><LockKeyhole size={28}/><h1>Your team’s data workspace</h1><p>Enter your workspace password to continue.</p><label className="field-label">Workspace password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required autoComplete="current-password"/></label>{error&&<p role="alert" className="error-note">{error}</p>}<Button type="submit" className="primary-button wide" disabled={loginBusy}>{loginBusy?'Signing in…':'Open workspace'}<ArrowUpRight size={16}/></Button></form></div>;
  return <div className="workspace">
    <aside className="sidebar"><Link href="/" className="brand" aria-label="Sheetwise home"><span className="brand-mark"><ChartNoAxesCombined size={23}/></span>sheetwise<span className="brand-dot">.</span></Link><div className="workspace-select"><span className="workspace-avatar">W</span><div><strong>Team workspace</strong><small>Internal analytics</small></div><LockKeyhole size={13}/></div>
      <nav className="main-nav" aria-label="Workspace navigation"><button className={view==='overview'?'selected':''} onClick={()=>setView('overview')}><LayoutDashboard size={17}/> Overview</button><button className={view==='data'?'selected':''} onClick={()=>setView('data')} disabled={!dataset}><Table2 size={17}/> Data explorer</button><button className={view==='saved'?'selected':''} onClick={()=>setView('saved')} disabled={!dataset}><Bookmark size={17}/> Saved insights{pins.length>0&&<span className="nav-count">{pins.length}</span>}</button></nav>
      <div className="dataset-section"><div className="sidebar-label">YOUR DATASETS<button aria-label="Upload a dataset" onClick={()=>setUploadOpen(true)} disabled={busy}><Plus size={16}/></button></div>{datasets.length>4&&<label className="sidebar-search"><Search size={14}/><input aria-label="Search datasets" placeholder="Search datasets" value={search} onChange={e=>setSearch(e.target.value)}/></label>}<div className="dataset-list">{shownDatasets.map(d=><button className={`dataset-item ${dataset?.id===d.id?'active':''}`} key={d.id} disabled={busy||loading} title={d.name} onClick={()=>selectDataset(d.id)}><FileSpreadsheet size={16}/><span>{d.name}</span>{dataset?.id===d.id&&<i/>}</button>)}</div>{!datasets.length&&<p className="sidebar-empty">Your uploaded spreadsheets will appear here.</p>}</div>
      <div className="sidebar-bottom"><div className="private-workspace"><ShieldCheck size={17}/><div><strong>Private by design</strong><p>Your data stays on your server.</p></div></div><div className="account-row"><span className="account-avatar">TW</span><div><strong>Team member</strong><small>{status?.localMode?'Local workspace':'Shared workspace'}</small></div>{status?.passwordRequired&&<button aria-label="Sign out" onClick={async()=>{await api('/session',{method:'DELETE'});location.reload();}}><LogOut size={16}/></button>}</div></div>
    </aside>
    <div className="workspace-body"><header className="topbar"><div className="breadcrumbs">Workspace <ChevronRight size={13}/><span>Analytics</span></div><div className="topbar-right"><span className="private-badge"><LockKeyhole size={12}/> Private workspace</span><button className="mobile-chat-toggle" onClick={()=>setChatOpen(!chatOpen)} aria-label="Toggle chat"><MessageSquare size={18}/></button><span className="topbar-avatar">TW</span></div></header>
      <div className="work-area"><main className="main-content">
        <div className="page-heading"><div><div className="eyebrow">YOUR DATA, A CLEARER PICTURE</div><h1>{view==='saved'?'Saved insights':view==='data'?'Data explorer':'Overview'}</h1><p>{view==='saved'?'The answers worth coming back to.':view==='data'?'Understand your columns and inspect the source.':'A starting point for your next good question.'}</p></div><Button className="primary-button upload-button" onClick={()=>setUploadOpen(true)} disabled={busy}><Plus size={16}/> Upload spreadsheet</Button></div>
        {error&&<div className="error-banner" role="alert"><p>{error}</p><button aria-label="Dismiss error" onClick={()=>setError('')}><X size={16}/></button></div>}
        {loading?<output className="loading-state"><LoaderCircle className="spin" size={24}/><span>Preparing your workspace…</span></output>:!dataset?<section className="empty-workspace"><div className="empty-visual"><div className="empty-grid"><span/><span/><span/><span/><span/><span/><span/><span/><span/></div><div className="empty-sheet"><FileSpreadsheet size={34}/></div><span className="empty-spark"><Sparkles size={19}/></span></div><h2>There’s a story in your spreadsheet.</h2><p>Upload a table. Get a dashboard.<br/>Ask the questions that matter to you.</p><Button className="primary-button" onClick={()=>setUploadOpen(true)}><Upload size={16}/> Upload your first spreadsheet</Button><button className="demo-button" onClick={demo}>Explore a sample dataset <ArrowUpRight size={15}/></button><div className="file-types"><span>CSV</span><span>XLSX</span><small>Up to 100 MB per file</small></div></section>:<>
          <div className="dataset-banner"><div className="dataset-icon"><FileSpreadsheet size={20}/></div><div className="dataset-banner-name"><strong title={dataset.filename}>{dataset.name}</strong><span>{dataset.isDemo?'Synthetic demo · ':''}{dataset.filename.toLowerCase().endsWith('.xlsx')?`XLSX · ${dataset.sheetName}`:'CSV'} <i>·</i> {(dataset.sizeBytes/1024/1024).toFixed(1)} MB <i>·</i> {number(dataset.rowCount)} records</span></div><span className="ready-badge"><Check size={12}/> Ready to explore</span></div>
          <div className="view-tabs" role="tablist"><button role="tab" aria-selected={view==='overview'} className={view==='overview'?'active':''} onClick={()=>setView('overview')}><LayoutDashboard size={15}/> Overview</button><button role="tab" aria-selected={view==='data'} className={view==='data'?'active':''} onClick={()=>setView('data')}><Columns3 size={15}/> Data</button><button role="tab" aria-selected={view==='saved'} className={view==='saved'?'active':''} onClick={()=>setView('saved')}><Bookmark size={15}/> Saved{pins.length>0&&<span>{pins.length}</span>}</button><span className="view-tabs-note">{view==='overview'?'Automatically generated from your data':''}</span></div>
          {view==='overview'&&<><section className="metrics-grid" aria-label="Dataset summary">{[{label:'Total records',value:number(dataset.rowCount),detail:'Rows in this dataset',icon:Users},{label:'Attributes',value:number(dataset.inputColumnCount),detail:`${dataset.excludedCount} secret fields excluded`,icon:Columns3},{label:'Ready for analysis',value:number(available),detail:'Usable columns for questions',icon:Sparkles},{label:'Average coverage',value:`${coverage.toFixed(1)}%`,detail:'Populated values across columns',icon:ChartNoAxesCombined}].map(m=><article className="metric-card" key={m.label}><div><span>{m.label}</span><m.icon size={16}/></div><strong>{m.value}</strong><small>{m.detail}</small></article>)}</section>
            {dataset.warnings.length>0&&<div className="data-note"><button onClick={()=>setWarningsOpen(!warningsOpen)} aria-expanded={warningsOpen}><Info size={16}/><span><strong>A note about this data</strong> {dataset.warnings.length} things to keep in mind</span><ChevronDown className={warningsOpen?'rotate':''} size={16}/></button>{warningsOpen&&<ul>{dataset.warnings.map(w=><li key={w}>{w}</li>)}</ul>}</div>}
            <div className="section-heading"><h2>At a glance</h2><span><span className="tiny-dot"/> Calculated from all records</span></div><section className="charts-grid">{dataset.dashboard.map(card=><article className="chart-card" key={card.id}><AnalyticsSurface messages={card.messages}/><div className="chart-source"><span>Source: <code>{card.source}</code></span>{card.sql&&<SqlDisclosure sql={card.sql}/>}</div></article>)}</section><div className="dashboard-bottom"><ShieldCheck size={14}/><p>Missing values stay unknown. Each insight shows the field it comes from.</p></div></>}
          {view==='data'&&<DataExplorer key={dataset.id} dataset={dataset}/>}
          {view==='saved'&&(pins.length?<section className="charts-grid saved-grid">{pins.map(a=><article className="chart-card" key={a.id}><div className="saved-question"><Bookmark size={14}/><span>{a.question}</span><button aria-label="Remove saved insight" onClick={()=>pin(a)}><X size={14}/></button></div><AnalyticsSurface messages={a.messages}/>{a.sql&&<SqlDisclosure sql={a.sql} result={a.result}/>}</article>)}</section>:<div className="saved-empty"><Bookmark size={28}/><h2>Keep your best discoveries.</h2><p>Ask a question, then choose “Save this insight” to find it here.</p><button onClick={()=>setChatOpen(true)}>Ask your data <ArrowUpRight size={15}/></button></div>)}
        </>}
      </main><div className={`chat-wrapper ${chatOpen?'open':''}`}><button className="chat-mobile-close" onClick={()=>setChatOpen(false)} aria-label="Close chat"><X size={20}/></button><ChatPanel key={dataset?.id ?? "empty"} dataset={dataset} status={status} answers={answers} busy={busy} error={chatError} pendingQuestion={pendingQuestion} onAsk={ask} onPin={pin}/></div></div>
    </div><UploadDialog open={uploadOpen} setOpen={setUploadOpen} onUploaded={p=>void uploaded(p)}/>
  </div>;
}
