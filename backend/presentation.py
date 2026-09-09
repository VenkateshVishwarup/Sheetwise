"""A2UI messages contain only application-approved components and executed data."""
import uuid

CATALOG_ID = 'https://sheetwise.local/catalogs/analytics/v1'


def surface(title, component, data, subtitle='', surface_id=None):
    sid = surface_id or str(uuid.uuid4())
    props = {'id':'root', 'component':component, 'title':title, 'subtitle':subtitle}
    if component == 'Metric':
        props.update({'value': {'path':'/value'}, 'detail': {'path':'/detail'}})
    elif component in ('BarChart','LineChart'):
        props.update({'rows':{'path':'/rows'},'labelKey':data['labelKey'],'valueKey':data['valueKey']})
    elif component == 'DataTable':
        props.update({'rows':{'path':'/rows'},'columns':data['columns']})
    elif component == 'Notice':
        props.update({'text': {'path':'/text'}})
    return [
        {'version':'v0.9.1','createSurface':{'surfaceId':sid,'catalogId':CATALOG_ID}},
        {'version':'v0.9.1','updateComponents':{'surfaceId':sid,'components':[props]}},
        {'version':'v0.9.1','updateDataModel':{'surfaceId':sid,'value':data}},
    ]


def answer_surface(title, chart_type, result):
    names, rows = result['columns'], result['rows']
    objects = [dict(zip(names, row)) for row in rows]
    if len(rows)==1 and len(names)==1:
        return surface(title,'Metric',{'value':rows[0][0], 'detail':'Calculated from the selected dataset.'})
    numeric = [i for i in range(len(names)) if rows and all(r[i] is None or isinstance(r[i], (float,int)) for r in rows) and any(r[i] is not None for r in rows)]
    labels = [i for i in range(len(names)) if i not in numeric]
    if chart_type in ('bar','line') and len(numeric)==1 and len(labels)==1 and len(rows)>1:
        return surface(title,'LineChart' if chart_type=='line' else 'BarChart',{'rows':objects,'labelKey':names[labels[0]],'valueKey':names[numeric[0]]}, 'Showing up to 200 groups' if result['truncated'] else f'{len(rows):,} groups')
    return surface(title,'DataTable',{'rows':objects, 'columns':names}, 'No matching records' if not rows else f'{len(rows):,} result rows')


def dashboard(profile):
    cards=[]
    usable=[c for c in profile['columns'] if c['queryable']]
    categories=[c for c in usable if c['type']=='category' and c['distinctCount']>1]
    priorities=('lead_status','lead.source','lead_source','campaign_name','region','channel','source','status','category')
    categories.sort(key=lambda c: (next((i for i,p in enumerate(priorities) if c['name']==p),99), -c['coverage']))
    for c in categories[:4]:
        rows=[{'category':r['label'],'records':r['count']} for r in c['distribution']]
        sql=f'SELECT {c["key"]} AS category, COUNT(*) AS records FROM dataset GROUP BY {c["key"]} ORDER BY records DESC LIMIT 12'
        cards.append({'id':c['key'],'title':c['name'],'source':c['name'],'sql':sql,'messages':surface(c['name'].replace('_',' ').replace('.',' · ').capitalize(),'BarChart',{'rows':rows,'labelKey':'category','valueKey':'records'},f'{c["coverage"]}% populated · top 12 values')})
    bools=[c for c in usable if c['type']=='boolean']
    bools.sort(key=lambda c:(0 if 'convert' in c['name'] else 1, -c['coverage']))
    for c in bools[:2]:
        rows=[{'value':'True','records':c['trueCount']},{'value':'False','records':c['falseCount']},{'value':'Unknown','records':c['missingCount']}]
        cards.append({'id':c['key'],'title':c['name'],'source':c['name'],'sql':f'SELECT {c["key"]} AS value, COUNT(*) AS records FROM dataset GROUP BY {c["key"]}', 'messages':surface(c['name'].replace('_',' ').replace('.',' · ').capitalize(),'BarChart',{'rows':rows,'labelKey':'value','valueKey':'records'},'True, false and unknown shown separately')})
    for c in [c for c in usable if c['type']=='number'][:max(0,4-len(cards))]:
        cards.append({'id':c['key'],'title':c['name'],'source':c['name'],'sql':f'SELECT AVG({c["key"]}) AS average FROM dataset','messages':surface(f'Average {c["name"]}','Metric',{'value':c['mean'],'detail':f'{c["coverage"]}% populated · missing values excluded'})})
    if not cards:
        cards.append({'id':'coverage','title':'Data coverage','source':'All columns','sql':'','messages':surface('Data coverage','Notice',{'text':'This table has no suitable aggregate dimensions yet. Review the column explorer for empty, personal, or unstructured fields.'})})
    return cards
