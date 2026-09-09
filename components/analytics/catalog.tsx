'use client';

import { A2uiSurface, createComponentImplementation, type ReactComponentImplementation } from '@a2ui/react/v0_9';
import { A2uiMessageSchema, Catalog, CommonSchemas, MessageProcessor } from '@a2ui/web_core/v0_9';
import { z } from 'zod';
import { useMemo } from 'react';
import { CartesianGrid, Line, LineChart as RechartsLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export const CATALOG_ID = 'https://sheetwise.local/catalogs/analytics/v1';
const heading = { title: CommonSchemas.DynamicString, subtitle: CommonSchemas.DynamicString };
const fmt = (v: unknown): string => {
  if (v == null) return 'Unknown';
  if (typeof v === 'number') return new Intl.NumberFormat('en', { maximumFractionDigits: 2 }).format(v);
  if (typeof v === 'string') return v;
  if (typeof v === 'boolean' || typeof v === 'bigint') return v.toString();
  return JSON.stringify(v) ?? '';
};
const palette = ['#3467eb', '#5985ef', '#86a5f4', '#adc2f8', '#d0defc', '#60748c'];
type Row = Record<string, unknown>;
const rowsOf = (value: unknown): Row[] => Array.isArray(value) ? value.filter((r): r is Row => !!r && typeof r === 'object' && !Array.isArray(r)) : [];

function Heading({ title, subtitle }: { title: unknown; subtitle: unknown }) {
  return <div className="viz-heading"><h3>{fmt(title ?? '')}</h3>{!!subtitle && <p>{fmt(subtitle)}</p>}</div>;
}

const Metric = createComponentImplementation({ name: 'Metric', schema: z.object({ ...heading, value: CommonSchemas.DynamicValue, detail: CommonSchemas.DynamicValue }).strict() }, ({ props }) => <div className="viz-metric"><Heading title={props.title} subtitle={props.subtitle}/><strong>{fmt(props.value)}</strong><p>{String(props.detail ?? '')}</p></div>);

const BarChart = createComponentImplementation({ name: 'BarChart', schema: z.object({ ...heading, rows: CommonSchemas.DynamicValue, labelKey: z.string(), valueKey: z.string() }).strict() }, ({ props }) => {
  const rows = rowsOf(props.rows);
  const max = Math.max(1, ...rows.map(r => Math.abs(Number(r[props.valueKey]) || 0)));
  return <div className="viz-bars"><Heading title={props.title} subtitle={props.subtitle}/><ul className="bar-list" aria-label={String(props.title)}>{rows.map((r, i) => <li className="bar-row" key={i}>
    <div className="bar-label"><span title={fmt(r[props.labelKey])}>{fmt(r[props.labelKey])}</span><strong>{fmt(r[props.valueKey])}</strong></div>
    <div className="bar-track"><div style={{ width: `${Math.max(0, Math.abs(Number(r[props.valueKey]) || 0) / max * 100)}%`, background: r[props.labelKey] === 'Unknown' ? '#c4ccd8' : palette[i % palette.length] }}/></div>
  </li>)}</ul>{!rows.length && <p className="muted">No matching records.</p>}{rows.length>0 && <div className="chart-foot">{rows.length} groups <span>·</span> Values calculated from your data</div>}</div>;
});

const LineChart = createComponentImplementation({ name: 'LineChart', schema: z.object({ ...heading, rows: CommonSchemas.DynamicValue, labelKey: z.string(), valueKey: z.string() }).strict() }, ({ props }) => <div><Heading title={props.title} subtitle={props.subtitle}/><div style={{ width:'100%', height:220 }}><ResponsiveContainer><RechartsLine data={rowsOf(props.rows)}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey={props.labelKey} tick={{fontSize:12}}/><YAxis tick={{fontSize:12}} width={45}/><Tooltip/><Line type="linear" dataKey={props.valueKey} stroke="#3467eb" strokeWidth={2} dot={false} isAnimationActive={false}/></RechartsLine></ResponsiveContainer></div><details className="chart-data"><summary>View chart data</summary><table><tbody>{rowsOf(props.rows).map((r,i)=><tr key={i}><td>{fmt(r[props.labelKey])}</td><td>{fmt(r[props.valueKey])}</td></tr>)}</tbody></table></details></div>);

const DataTable = createComponentImplementation({ name: 'DataTable', schema: z.object({ ...heading, rows: CommonSchemas.DynamicValue, columns: z.array(z.string()).max(500) }).strict() }, ({ props }) => <div><Heading title={props.title} subtitle={props.subtitle}/><div className="result-table"><table><thead><tr>{props.columns.map(String).map(c=><th key={c}>{c.replaceAll('_',' ')}</th>)}</tr></thead><tbody>{rowsOf(props.rows).map((r,i)=><tr key={i}>{props.columns.map(String).map(c=><td key={c}>{fmt(r[c])}</td>)}</tr>)}</tbody></table></div></div>);
const Notice = createComponentImplementation({ name: 'Notice', schema: z.object({ ...heading, text: CommonSchemas.DynamicString }).strict() }, ({ props }) => <div className="viz-notice"><Heading title={props.title} subtitle={props.subtitle}/><p>{String(props.text ?? '')}</p></div>);

const catalog = new Catalog<ReactComponentImplementation>(CATALOG_ID, [Metric, BarChart, LineChart, DataTable, Notice], []);

export function createAnalyticsProcessor(messages: unknown[]) {
  if (messages.length > 100) throw new Error('Too many UI messages.');
  const parsed = A2uiMessageSchema.array().parse(messages);
  // This catalog contains no links, scripts, remote media or client actions.
  for (const message of parsed) {
    if ('createSurface' in message && message.createSurface.catalogId !== CATALOG_ID) throw new Error('Unapproved display catalog.');
  }
  const processor = new MessageProcessor([catalog], undefined, { version: 'v0.9.1' });
  processor.processMessages(parsed);
  return processor;
}

export function AnalyticsSurface({ messages }: { messages: unknown[] }) {
  const rendered = useMemo(() => {
    try { return { processor: createAnalyticsProcessor(messages), error: false }; }
    catch { return { processor: null, error: true }; }
  }, [messages]);
  if (rendered.error) return <p role="alert" className="error-note">This visualization could not be displayed. The query result is still available below.</p>;
  return <>{Array.from(rendered.processor!.model.surfacesMap.values()).map(surface => <A2uiSurface key={surface.id} surface={surface}/>)}</>;
}
