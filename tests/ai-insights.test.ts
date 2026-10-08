import test from 'node:test';
import assert from 'node:assert/strict';
import { act, createElement } from 'react';
import { Window } from 'happy-dom';
import { createRoot } from 'react-dom/client';
import { AiInsightsPanel } from '../components/analytics/ai-insights-panel';
import type { AiInsightRun } from '../lib/types';

const window = new Window();
Object.assign(globalThis, { window, document: window.document, HTMLElement: window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true });

const saved: AiInsightRun = { id: 'r1', datasetId: 'd1', createdAt: '2026-10-09T09:30:00+00:00', model: 'gpt-5.6-sol', insights: [{ title: 'Demo bookings are falling', text: 'From 7.8% to 1.4% of known records.', source: 'demo_scheduled · timestamp' }] };

async function mount(aiConfigured: boolean, responses: Record<string, unknown>) {
  const requests: string[] = [];
  globalThis.fetch = (async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${url}`;
    requests.push(key);
    return { ok: true, json: async () => responses[key] } as Response;
  }) as typeof fetch;
  const container = document.createElement('div');
  const root = createRoot(container);
  await act(async () => { root.render(createElement(AiInsightsPanel, { datasetId: 'd1', aiConfigured })); });
  return { container, requests, root };
}

void test('shows the latest saved AI insights with their model and what was sent', async () => {
  const { container, root } = await mount(true, { 'GET /api/datasets/d1/ai-insights': [saved] });
  const text = container.textContent ?? '';
  assert.match(text, /Demo bookings are falling/);
  assert.match(text, /demo_scheduled · timestamp/);
  assert.match(text, /gpt-5\.6-sol/);
  assert.match(text, /no rows or protected columns/);
  assert.equal(container.querySelector('button')?.textContent, 'Regenerate');
  await act(async () => { root.unmount(); });
});

void test('generates on request and replaces the empty state', async () => {
  const { container, requests, root } = await mount(true, { 'GET /api/datasets/d1/ai-insights': [], 'POST /api/datasets/d1/ai-insights': saved });
  const button = container.querySelector('button')!;
  assert.equal(button.textContent, 'Generate AI insights');
  await act(async () => { button.click(); });
  assert.deepEqual(requests, ['GET /api/datasets/d1/ai-insights', 'POST /api/datasets/d1/ai-insights']);
  assert.match(container.textContent ?? '', /Demo bookings are falling/);
  await act(async () => { root.unmount(); });
});

void test('explains why generation is unavailable without an OpenAI key', async () => {
  const { container, root } = await mount(false, { 'GET /api/datasets/d1/ai-insights': [] });
  assert.equal(container.querySelector('button')?.disabled, true);
  assert.match(container.textContent ?? '', /needs an OpenAI API key/);
  await act(async () => { root.unmount(); });
});
