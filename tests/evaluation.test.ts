import test from 'node:test';
import assert from 'node:assert/strict';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {eligibleEvaluationFeature} from '../lib/evaluation';
import {ReadinessSummary} from '../components/analytics/evaluation-panel';
import type {Column, Readiness} from '../lib/types';
const column={key:'c0',name:'channel',type:'category',queryable:true,sensitive:false,distinctCount:3} as Column;
void test('input eligibility excludes protected and outcome columns',()=>{
 assert.equal(eligibleEvaluationFeature(column,'c1'),true);
 for(const c of [{...column,name:'lead_status'},...['isConverted','leadStatus','isQualified','appointmentBooked','conversion','APIConversion'].map(name=>({...column,name})),{...column,sensitive:true},{...column,queryable:false},{...column,type:'text' as const},{...column,distinctCount:101}])assert.equal(eligibleEvaluationFeature(c,'c1'),false);
 assert.equal(eligibleEvaluationFeature(column,'c0'),false);
});
void test('readiness shows unknown outcomes separately and blockers as actionable text',()=>{
 const r={ready:false,totalRows:240,knownRows:200,unknownRows:40,positiveRows:100,negativeRows:100,targetName:'converted',features:[],issues:[{code:'HISTORY_REQUIRED',severity:'blocker',columnKey:null,message:'Historical observations are needed.'}]} as Readiness;
 const html=renderToStaticMarkup(createElement(ReadinessSummary,{report:r}));
 assert.match(html,/200/);assert.match(html,/40/);assert.match(html,/Unknown/);assert.match(html,/Historical observations are needed/);assert.match(html,/Resolve before evaluation/);
});
