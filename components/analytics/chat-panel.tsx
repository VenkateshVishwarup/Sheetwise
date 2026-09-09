'use client';
import { useEffect, useRef, useState } from 'react';
import { ArrowUp, ArrowUpRight, Check, Code2, LoaderCircle, Pin, Sparkles, ShieldCheck, MessageSquarePlus } from 'lucide-react';
import type { Answer, Dataset, Status } from '@/lib/types';
import { AnalyticsSurface } from './catalog';

export function SqlDisclosure({ sql, result }: { sql: string; result?: Answer['result'] }) {
  return <details className="sql-disclosure"><summary><Code2 size={13}/> View SQL {result&&<span>{(result.elapsedMs/1000).toFixed(2)}s</span>}</summary><pre>{sql}</pre>{result&&<details className="raw-result"><summary>View result table</summary><div className="result-table"><table><thead><tr>{result.columns.map((c,i)=><th key={i}>{c}</th>)}</tr></thead><tbody>{result.rows.map((row,i)=><tr key={i}>{row.map((v,j)=><td key={j}>{v==null?'Unknown':String(v)}</td>)}</tr>)}</tbody></table></div></details>}</details>;
}

export function ChatPanel({ dataset, status, answers, busy, error, pendingQuestion, onAsk, onPin }: { dataset:Dataset|null; status:Status|null; answers:Answer[]; busy:boolean; error:string; pendingQuestion:string; onAsk:(q:string)=>void; onPin:(a:Answer)=>void }) {
  const [question,setQuestion]=useState('');
  const bottom=useRef<HTMLDivElement>(null);
  const input=useRef<HTMLTextAreaElement>(null);
  useEffect(()=>{bottom.current?.scrollIntoView({behavior:'smooth',block:'nearest'});},[answers,busy,error]);
  const usable=dataset?.columns.filter(c=>c.queryable)??[];
  const dimension=usable.find(c=>c.type==='category'&&c.distinctCount>1);
  const boolean=usable.find(c=>c.type==='boolean');
  const suggestions=[ 'How many records are in this dataset?', ...(dimension?[`Break down records by ${dimension.name}`]:[]), ...(boolean?[`Show true, false and unknown counts for ${boolean.name}`]:[]) ];
  function submit(q=question) { if(!q.trim()||busy||!dataset) return;onAsk(q.trim());setQuestion(''); }
  return <aside className="chat-panel" aria-label="Chat with your data"><div className="chat-header"><div className="chat-title"><span className="spark-icon"><Sparkles size={17}/></span><h2>Ask your data</h2></div><span className="ai-badge">AI</span></div><div className="chat-context"><span className="status-dot"/>{dataset?'Connected to this dataset':'Upload a dataset to begin'}</div>
    <div className="chat-scroll">
      {!answers.length&&!busy&&<div className="chat-welcome"><div className="chat-art"><MessageSquarePlus size={26}/><span>✦</span></div><h3>A question is all it takes.</h3><p>Explore patterns, compare groups, and find answers in your spreadsheet.</p>{dataset&&<div className="suggestions"><span className="eyebrow">TRY ASKING</span>{suggestions.map(q=><button key={q} onClick={()=>submit(q)} disabled={!status?.aiConfigured}>{q}<ArrowUpRight size={15}/></button>)}</div>}</div>}
      {answers.map(answer=><div className="conversation-turn" key={answer.id}><div className="question-bubble">{answer.question}</div><div className="answer-label"><Sparkles size={13}/> Sheetwise <span><Check size={11}/>{answer.kind==='answer'?'Query verified':'Clarification'}</span></div><p className="answer-summary">{answer.summary}</p>{answer.kind==='answer'?<><div className="answer-viz"><AnalyticsSurface messages={answer.messages}/></div>{answer.sql&&<SqlDisclosure sql={answer.sql} result={answer.result}/>}<button className={`pin-button ${answer.pinned?'pinned':''}`} onClick={()=>onPin(answer)}><Pin size={13}/>{answer.pinned?'Saved to dashboard':'Save this insight'}</button></>:<div className="clarification-choices">{answer.choices.map(choice=><button key={choice} disabled={busy} onClick={()=>submit(choice)}>{choice}<ArrowUpRight size={13}/></button>)}</div>}</div>)}
      {busy&&<div className="conversation-turn"><div className="question-bubble">{pendingQuestion}</div><output className="thinking"><LoaderCircle size={16} className="spin"/><span>Reading the question and checking your data…</span></output></div>}
      {error&&<div role="alert" className="chat-error"><p>{error}</p><button onClick={()=>{setQuestion(pendingQuestion);input.current?.focus();}}>Edit and try again</button></div>}<div ref={bottom}/>
    </div>
    <div className="chat-composer">{status&&!status.aiConfigured&&<p className="configuration-note">Chat needs an OpenAI API key configured on the app server. Your dashboard is ready to use.</p>}<form onSubmit={e=>{e.preventDefault();submit();}}><textarea ref={input} aria-label="Ask a question about your data" placeholder={dataset?'Ask anything about this dataset…':'Upload a spreadsheet first…'} value={question} onChange={e=>setQuestion(e.target.value)} maxLength={2000} disabled={!dataset||busy||!status?.aiConfigured} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();submit();}}}/><div className="composer-bottom"><span>{question.length?`${question.length}/2000`:'↵ to send · Shift ↵ for a new line'}</span><button type="submit" aria-label="Send question" disabled={!question.trim()||busy||!dataset||!status?.aiConfigured}>{busy?<LoaderCircle size={16} className="spin"/>:<ArrowUp size={18}/>}</button></div></form><p className="chat-privacy"><ShieldCheck size={12}/> Raw rows are never sent to the AI</p></div>
  </aside>;
}
