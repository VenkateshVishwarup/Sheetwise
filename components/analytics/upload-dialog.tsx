'use client';
import { useRef, useState } from 'react';
import { FileSpreadsheet, UploadCloud, LoaderCircle, ShieldCheck } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { upload as uploadBlob } from '@vercel/blob/client';
import type { Dataset, Status } from '@/lib/types';

export function UploadDialog({ open, setOpen, onUploaded }: { open: boolean; setOpen: (v:boolean)=>void; onUploaded:(d:Dataset)=>void }) {
  const [file,setFile]=useState<File|null>(null);
  const [sheet,setSheet]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [drag,setDrag]=useState(false);
  const input=useRef<HTMLInputElement>(null);
  function choose(chosen:File|undefined) {
    setError('');
    if (!chosen) return;
    if (!/\.(csv|xlsx)$/i.test(chosen.name)) { setError('Choose a CSV or XLSX file.'); return; }
    if (chosen.size>100*1024*1024) { setError('This file is larger than 100 MB.'); return; }
    setFile(chosen);
  }
  async function upload() {
    if (!file) return;
    setBusy(true);setError('');
    try {
      const status=await api<Status>('/status');
      let dataset:Dataset;
      if(status.directUploads) {
        const extension=file.name.toLowerCase().endsWith('.xlsx')?'xlsx':'csv';
        const pathname=`uploads/${crypto.randomUUID()}.${extension}`;
        await uploadBlob(pathname,file,{access:'private',handleUploadUrl:'/api/blob-upload',multipart:true,contentType:'application/octet-stream'});
        dataset=await api<Dataset>('/imports',{method:'POST',body:JSON.stringify({pathname,filename:file.name,sheetName:sheet.trim()||null})});
      } else {
        const body=new FormData();body.append('file',file);if(sheet.trim())body.append('sheetName',sheet.trim());
        dataset=await api<Dataset>('/datasets',{method:'POST',body});
      }
      onUploaded(dataset);setFile(null);setSheet('');setOpen(false);
    } catch(e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <Dialog open={open} onOpenChange={value=>!busy && setOpen(value)}><DialogContent className="upload-modal" showCloseButton={!busy}>
    <div className="upload-symbol"><FileSpreadsheet size={24}/></div><DialogTitle>Bring your data into focus</DialogTitle>
    <DialogDescription>Upload a spreadsheet to create your dashboard and start asking questions.</DialogDescription>
    <input ref={input} type="file" accept=".csv,.xlsx" hidden onChange={e=>choose(e.target.files?.[0])}/>
    <button className={`dropzone ${drag?'dragging':''}`} disabled={busy} onClick={()=>input.current?.click()} onDragOver={e=>{e.preventDefault();setDrag(true);}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);choose(e.dataTransfer.files[0]);}}>
      <UploadCloud size={30}/><strong>{file?file.name:'Drop your spreadsheet here'}</strong><span>{file?`${(file.size/1024/1024).toFixed(1)} MB · Click to change`:'or click to browse your files'}</span><small>CSV or XLSX · Up to 100 MB</small>
    </button>
    {file?.name.toLowerCase().endsWith('.xlsx') && <label className="field-label">Worksheet name <span>(optional)</span><input value={sheet} onChange={e=>setSheet(e.target.value)} placeholder="First worksheet by default" disabled={busy}/></label>}
    <div className="privacy-note"><ShieldCheck size={17}/><span>Personal values are masked. Secret fields are excluded from analysis. Uploaded data stays in your private workspace storage.</span></div>
    {error && <p className="error-note" role="alert">{error}</p>}
    <Button className="primary-button wide" disabled={!file||busy} onClick={upload}>{busy?<><LoaderCircle className="spin"/> Reading and profiling your data…</>:<>Create dashboard <span>↗</span></>}</Button>
  </DialogContent></Dialog>;
}
