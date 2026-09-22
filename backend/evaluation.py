"""Bounded, server-only evaluation of recorded binary outcomes."""
import json
import math
import os
import random
import re
import subprocess
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

MAX_LABELLED=20_000
TIMEOUT=30
OUTCOME_WORDS=re.compile(r'(^|[._\s-])(conver(?:t|sion)\w*|qualif\w*|status|outcome|result|dropoff|appointment|followup|disposition)([._\s-]|$)',re.I)


def eligible_feature(column):
    name=re.sub(r'([A-Z]+)([A-Z][a-z])',r'\1_\2',column['name'])
    name=re.sub(r'([a-z0-9])([A-Z])',r'\1_\2',name)
    return (column.get('queryable') and not column.get('sensitive') and column['type'] in ('category','boolean')
            and not OUTCOME_WORDS.search(name) and column.get('distinctCount',0)<=100)


def validate_definition(profile,d):
    columns={c['key']:c for c in profile['columns']}
    target=columns.get(d.get('targetKey'))
    if not target or target['type']!='boolean' or not target.get('queryable') or target.get('sensitive'):
        raise ValueError('Choose an unprotected true/false outcome.')
    keys=d.get('featureKeys',[])
    if not 1<=len(keys)<=12 or len(keys)!=len(set(keys)):
        raise ValueError('Choose between 1 and 12 different input columns.')
    if any(k==target['key'] or k not in columns or not eligible_feature(columns[k]) for k in keys):
        raise ValueError('Inputs cannot include the outcome, protected data, status fields, or unsupported columns.')
    if any(not re.fullmatch(r'c[0-9]{1,3}',k) for k in [target['key'],*keys]):
        raise ValueError('Invalid column selection.')
    if d.get('purpose') not in ('snapshot','future'):
        raise ValueError('Choose current status or a future outcome.')
    if any(not isinstance(d.get(k),str) or not 3<=len(d[k].strip())<=200 for k in ('positiveMeaning','negativeMeaning')):
        raise ValueError('Describe both outcomes in 3 to 200 characters.')
    return target,[columns[k] for k in keys]


def score_predictions(labels,probabilities):
    """Tie-aware ROC AUC and average precision; no arbitrary ranking of ties."""
    n=len(labels);positive=sum(labels);negative=n-positive
    groups=defaultdict(lambda:[0,0])
    for y,p in zip(labels,probabilities,strict=True):
        groups[p][int(y)]+=1
    preceding_negative=0;wins=0.;tp=0;seen=0;ap=0.
    for p,(zeros,ones) in sorted(groups.items()):
        wins+=ones*(preceding_negative+.5*zeros);preceding_negative+=zeros
    for p,(zeros,ones) in sorted(groups.items(),reverse=True):
        tp+=ones;seen+=zeros+ones;ap+=(ones/positive)*(tp/seen)
    return {'rocAuc':wins/(positive*negative),'averagePrecision':ap,
            'brier':sum((p-y)**2 for y,p in zip(labels,probabilities,strict=True))/n}


def _analyze(profile,d,evaluate=False):
    import duckdb
    target,features=validate_definition(profile,d)
    issues=[]
    def issue(code,message,blocking=False,column=None):
        issues.append({'code':code,'message':message,'severity':'blocker' if blocking else 'warning','columnKey':column})
    t=target['key']
    with duckdb.connect(profile['databasePath'],read_only=True,config={'threads':1,'memory_limit':'128MB','enable_external_access':False}) as con:
        # Preserve source category distinctions. The general analytics table lowercases
        # categories for grouping, which would hide precisely the collisions we check.
        expressions=[]
        for column in [*features,target]:
            key=column['key']
            source=f'CAST("{key}" AS VARCHAR)'
            expression=(f"TRY_CAST(NULLIF(TRIM({source}), '') AS BOOLEAN)" if column['type']=='boolean'
                        else f"CASE WHEN TRIM({source}) = '' THEN NULL ELSE {source} END")
            expressions.append(f'{expression} AS "{key}"')
        con.execute('CREATE TEMP VIEW evaluation_data AS SELECT '+','.join(expressions)+' FROM original')
        total,known,pos,neg=con.execute(f'SELECT count(*),count("{t}"),count(*) FILTER(WHERE "{t}"=true),count(*) FILTER(WHERE "{t}"=false) FROM evaluation_data').fetchone()
        if d['purpose']=='future':issue('HISTORY_REQUIRED','Future outcomes need dated historical inputs, an outcome window and sufficient follow-up. This pilot evaluates recorded status only.',True)
        if not d.get('labelsConfirmed'):issue('CONFIRM_LABELS','Confirm that the definitions match how this outcome was recorded.',True)
        if not d.get('featuresConfirmed'):issue('CONFIRM_INPUTS','Confirm that the inputs are appropriate for this comparison and do not reveal the outcome.',True)
        if known<100 or min(pos,neg)<20:issue('TOO_FEW_OUTCOMES','Need at least 100 known outcomes, including 20 true and 20 false.',True)
        if known>MAX_LABELLED:issue('TOO_MANY_ROWS','This pilot supports at most 20,000 known outcomes. Upload a smaller, representative cohort.',True)
        if known and min(pos,neg)/known<.1:issue('CLASS_IMBALANCE','One outcome is uncommon. A small holdout may give unstable quality estimates.')
        if total and known/total<.8:issue('LOW_LABEL_COVERAGE','Many outcomes are unknown. Results on known outcomes may not represent the rest of this dataset.')
        feature_reports=[];varying=0
        for column in features:
            k=column['key']
            present,distinct=con.execute(f'SELECT count("{k}"),count(DISTINCT "{k}") FROM evaluation_data WHERE "{t}" IS NOT NULL').fetchone()
            unknown_present=con.execute(f'SELECT count("{k}") FROM evaluation_data WHERE "{t}" IS NULL').fetchone()[0]
            if distinct>100:issue('TOO_MANY_CATEGORIES','An input has more than 100 categories in the labelled cohort.',True,k)
            if distinct<2:issue('LOW_VARIATION','This input has fewer than two observed values; any signal may come from missingness.',False,k)
            if distinct>1:varying+=1
            groups=defaultdict(set)
            values=con.execute(f'SELECT DISTINCT "{k}" FROM evaluation_data WHERE "{k}" IS NOT NULL LIMIT 102').fetchall()
            for (value,) in values:
                text=str(value)
                if len(text)>1000:issue('LONG_VALUE','An input contains values too long for this categorical evaluation.',True,k)
                groups[re.sub(r'\s+','',text.casefold())].add(text)
            collisions=sum(len(v)>1 for v in groups.values())
            if collisions:issue('CATEGORY_COLLISION','Some category names differ only by case or spacing. Verify whether the distinctions are intentional; values will not be merged.',not d.get('categoriesReviewed'),k)
            known_coverage=present/known if known else 0
            unknown_coverage=unknown_present/(total-known) if total>known else None
            if unknown_coverage is not None and abs(known_coverage-unknown_coverage)>.3:
                issue('COVERAGE_SHIFT','Input coverage differs by over 30 percentage points between known and unknown outcomes.',False,k)
            feature_reports.append({'key':k,'name':column['name'],'knownCoverage':round(known_coverage*100,2),'unknownCoverage':round(unknown_coverage*100,2) if unknown_coverage is not None else None,'distinctKnown':distinct,'collisionGroups':collisions})
        if not varying:issue('NO_VARYING_INPUTS','Choose at least one input with two or more observed values.',True)
        readiness={'ready':not any(i['severity']=='blocker' for i in issues),'totalRows':total,'knownRows':known,'unknownRows':total-known,'positiveRows':pos,'negativeRows':neg,'targetName':target['name'],'features':feature_reports,'issues':issues}
        if not evaluate:return readiness
        if not readiness['ready']:raise ValueError('Resolve the readiness blockers before running an evaluation.')
        keys=[c['key'] for c in features]
        rows=con.execute('SELECT '+','.join('"'+k+'"' for k in [*keys,t])+f' FROM evaluation_data WHERE "{t}" IS NOT NULL').fetchall()
    # Split first. All category counts and encodings are learned on the training subset.
    groups={v:[i for i,r in enumerate(rows) if bool(r[-1])==v] for v in (False,True)}
    rng=random.Random(42);train=[];test=[]
    for indices in groups.values():
        rng.shuffle(indices);cut=max(1,round(len(indices)*.25));test.extend(indices[:cut]);train.extend(indices[cut:])
    def token(value):return ('missing',) if value is None else ('value',str(value))
    counts=Counter(int(rows[i][-1]) for i in train)
    vocab=[set(token(rows[i][j]) for i in train) for j in range(len(keys))]
    conditional={(y,j):Counter(token(rows[i][j]) for i in train if int(rows[i][-1])==y) for y in (0,1) for j in range(len(keys))}
    predictions=[]
    for i in test:
        logs=[]
        for y in (0,1):
            log=math.log(counts[y]/len(train))
            for j in range(len(keys)):
                log+=math.log((conditional[y,j][token(rows[i][j])]+1)/(counts[y]+len(vocab[j])+1))
            logs.append(log)
        delta=max(-700,min(700,logs[0]-logs[1]));predictions.append(1/(1+math.exp(delta)))
    labels=[int(rows[i][-1]) for i in test];rate=counts[1]/len(train)
    return {'id':str(uuid.uuid4()),'datasetId':profile['id'],'createdAt':datetime.now(timezone.utc).isoformat(),'definition':d,'readiness':readiness,
            'trainRows':len(train),'testRows':len(test),'testPositiveRows':sum(labels),'seed':42,'algorithmVersion':'snapshot-categorical-v1',
            'models':[{'name':'Prevalence reference',**score_predictions(labels,[rate]*len(test))},{'name':'Categorical naive Bayes',**score_predictions(labels,predictions)}],
            'limitations':['Recorded status at export time; not future conversion.','One stratified holdout; small differences are not evidence of a reliable winner.','Input timing and category meanings are confirmed by the user, not independently verified.','Unknown outcomes were excluded. No individual predictions were saved or enabled.']}


def run_evaluation(profile,definition,evaluate=False):
    validate_definition(profile,definition)
    env={k:os.environ[k] for k in ('PATH','LANG','SYSTEMROOT','LD_LIBRARY_PATH') if k in os.environ}
    env['PYTHONPATH']=os.pathsep.join(sys.path)
    process=subprocess.Popen([sys.executable,'-m','backend.evaluation_worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,cwd=Path(__file__).resolve().parents[1])
    try:
        stdout,_=process.communicate(json.dumps({'profile':profile,'definition':definition,'evaluate':evaluate}),timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill();process.communicate();raise ValueError('The evaluation exceeded 30 seconds. Try fewer inputs or a smaller dataset.') from None
    if process.returncode:raise RuntimeError('The evaluation worker could not complete this dataset.')
    result=json.loads(stdout)
    if 'error' in result:raise ValueError(result['error'])
    return result
