import test from 'node:test';
import assert from 'node:assert/strict';
import { act, createElement } from 'react';
import { Window } from 'happy-dom';
import { createRoot } from 'react-dom/client';
import { A2uiSurface } from '@a2ui/react/v0_9';
import { createAnalyticsProcessor, CATALOG_ID } from '../components/analytics/catalog';

// The official renderer is client-only (useSyncExternalStore has no server snapshot).
const window = new Window();
Object.assign(globalThis, { window, document: window.document, HTMLElement: window.HTMLElement, IS_REACT_ACT_ENVIRONMENT: true });

async function renderSurface(surface: Parameters<typeof A2uiSurface>[0]['surface']) {
  const container = document.createElement('div');
  const root = createRoot(container);
  try {
    await act(async () => { root.render(createElement(A2uiSurface, { surface })); });
    return container.cloneNode(true) as HTMLElement;
  } finally { await act(async () => { root.unmount(); }); }
}

function messages(component: Record<string,unknown>, value:Record<string,unknown>) {
  return [
    {version:'v0.9.1',createSurface:{surfaceId:'test',catalogId:CATALOG_ID}},
    {version:'v0.9.1',updateComponents:{surfaceId:'test',components:[{id:'root',title:'Users',subtitle:'',...component}]}},
    {version:'v0.9.1',updateDataModel:{surfaceId:'test',value}},
  ];
}

void test('renders real metric bindings through the official A2UI React renderer', async () => {
  const processor=createAnalyticsProcessor(messages({component:'Metric',value:{path:'/value'},detail:{path:'/detail'}},{value:4628,detail:'All records'}));
  assert.equal(processor.model.surfacesMap.size,1);
  const surface=Array.from(processor.model.surfacesMap.values())[0];
  const element=await renderSurface(surface);
  const html=element.innerHTML;
  assert.match(html,/4,628/);
  assert.match(html,/All records/);
});

void test('escapes uploaded labels and binds real chart counts', async () => {
  const processor=createAnalyticsProcessor(messages({component:'BarChart',rows:{path:'/rows'},labelKey:'category',valueKey:'records'},{rows:[{category:'<script>alert(1)</script>',records:193}]}));
  const surface=Array.from(processor.model.surfacesMap.values())[0];
  const element=await renderSurface(surface);
  const html=element.innerHTML;
  assert.match(html,/193/);
  assert.equal(element.querySelectorAll('script').length, 0);
  assert.match(html,/&lt;script&gt;/);
});

void test('rejects unregistered display catalogs and invalid wire messages', () => {
  assert.throws(()=>createAnalyticsProcessor([{version:'v0.9.1',createSurface:{surfaceId:'evil',catalogId:'https://evil.test'}}]));
  assert.throws(()=>createAnalyticsProcessor([{html:'<script>alert(1)</script>'}]));
});
