"""OpenAI-written insights from the overview's aggregate totals, generated only on request.
Sent: totals for unprotected columns. Never sent: rows, protected columns or their names, or category values held by fewer than five records."""
import datetime as dt
import uuid

from .agent import model_name, provider_call
from .privacy import mask_text
from .trends import percents

SMALL_GROUP = 5
OTHER = f'other (groups under {SMALL_GROUP} records)'


def ai_summary(profile):
    columns = []
    for c in profile['columns']:
        if not c['queryable']:
            continue
        item = {'key': c['key'], 'name': c['name'], 'type': c['type'], 'coverage': c['coverage']}
        if c['type'] == 'category':
            shown = [d for d in c['distribution'] if d['count'] >= SMALL_GROUP or d['label'] == 'Unknown']
            small = sum(d['count'] for d in c['distribution'] if d not in shown)
            item['values'] = shown + ([{'label': OTHER, 'count': small}] if small else [])
            item['distinctValues'] = c['distinctCount']
        elif c['type'] == 'boolean':
            item.update({'trueCount': c['trueCount'], 'falseCount': c['falseCount'], 'unknownCount': c['missingCount']})
        elif c['type'] == 'number':
            item.update({k: c[k] for k in ('min', 'max', 'mean')})
        columns.append(item)
    summary = {'rowCount': profile['rowCount'], 'columns': columns}
    series = profile.get('timeSeries')
    if series:
        summary['timeSeries'] = {
            'dateKey': series['dateKey'], 'grain': series['grain'],
            'periods': [{'start': b['start'], 'records': b['records'], 'partial': b['partial']} for b in series['buckets']],
            'percentTrue': [{'key': r['key'], 'values': percents(r)} for r in series['rates']],
        }
    return summary


def generate_ai_insights(profile, provider=None):
    provider = provider or provider_call
    summary = ai_summary(profile)
    names = {c['key']: c['name'] for c in summary['columns']}
    result = provider('insights', {'dataset': summary})
    insights = []
    for item in result.get('insights', [])[:5]:
        cited = list(dict.fromkeys(item.get('columns', [])))
        # An insight must rest on columns that were actually sent.
        if not cited or any(k not in names for k in cited):
            continue
        insights.append({'title': mask_text(item['title'].strip())[:120], 'text': mask_text(item['text'].strip())[:600], 'source': ' · '.join(names[k] for k in cited)})
    if not insights:
        raise RuntimeError('The AI service returned no usable insights for this dataset. Try again.')
    return {'id': str(uuid.uuid4()), 'datasetId': profile['id'], 'createdAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'model': model_name(), 'insights': insights}
