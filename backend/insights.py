"""Plain-language observations written by fixed rules from stored aggregates. Nothing is sent to the AI."""
from .presentation import dashboard_booleans, dashboard_categories, period_label
from .trends import chosen_rates, linear_fit, percents, shape

MAX_INSIGHTS = 5


def _label(series, index):
    buckets = series['buckets']
    return period_label(buckets[index]['start'], series['grain'], len({b['start'][:4] for b in buckets}) > 1)


def _when(series, index):
    label = _label(series, index)
    return {'day': f'on {label}', 'week': f'in the week of {label}'}.get(series['grain'], f'in {label}')


def _records(series):
    buckets, grain = series['buckets'], series['grain']
    values = [b['records'] for b in buckets]
    fit = linear_fit(values, buckets)
    if not fit:
        return None
    kind, mean = shape(fit)
    (x0, y0), (xn, yn) = fit['points'][0], fit['points'][-1]
    if kind == 'level':
        text = f'Records per {grain} held roughly level at about {mean:,.0f}.'
    elif kind == 'steady':
        direction = 'rose' if fit['slope'] > 0 else 'fell'
        text = f'Records per {grain} {direction} steadily, from {y0:,} {_when(series, x0)} to {yn:,} {_when(series, xn)} (about {fit["slope"]:+,.0f} per {grain}).'
    else:
        xp, peak = max(fit['points'], key=lambda p: p[1])
        if xp == xn:
            text = f'No steady trend in records per {grain}, but the latest complete {grain} was the busiest: {peak:,} {_when(series, xp)}.'
        else:
            text = f'No steady trend in records per {grain}: the peak was {peak:,} {_when(series, xp)}, and the latest complete {grain} ({_label(series, xn)}) had {yn:,}, {round((peak - yn) / peak * 100)}% below the peak.'
    return {'text': text, 'source': series['dateName']}


def _rate(series, rate):
    buckets, grain = series['buckets'], series['grain']
    values = percents(rate)
    fit = linear_fit(values, buckets)
    kind, mean = shape(fit)
    (x0, y0), (xn, yn) = fit['points'][0], fit['points'][-1]
    name = rate['name']
    if kind == 'level':
        text = f'{name} held roughly level at about {mean:.1f}% true per {grain}.'
    elif kind == 'steady':
        direction = 'rising' if fit['slope'] > 0 else 'falling'
        text = f'{name} was true for {y0:.1f}% of known records {_when(series, x0)}, {direction} steadily to {yn:.1f}% {_when(series, xn)}.'
    else:
        low, high = min(v for _, v in fit['points']), max(v for _, v in fit['points'])
        text = f'{name} varied between {low:.1f}% and {high:.1f}% true per {grain} with no steady trend.'
    if rate['coverage'] < 90:
        text += f' It is known for {rate["coverage"]}% of records.'
    return {'text': text, 'source': f'{name} · {series["dateName"]}'}


def _dominant(profile):
    found = []
    for c in dashboard_categories(profile):
        known = profile['rowCount'] - c['missingCount']
        top = next((d for d in c['distribution'] if d['label'] != 'Unknown'), None)
        if top and known and top['count'] / known >= 0.5:
            share = top['count'] / known * 100
            found.append((share, {'text': f'“{top["label"]}” makes up {share:.0f}% of known {c["name"]} values ({top["count"]:,} of {known:,}).', 'source': c['name']}))
    return [item for _, item in sorted(found, key=lambda f: -f[0])]


def _true_rates(profile, trended):
    found = []
    for c in dashboard_booleans(profile):
        known = c['trueCount'] + c['falseCount']
        if c['key'] in trended or not known:
            continue
        text = f'{c["name"]} is true for {c["trueCount"] / known * 100:.1f}% of the {known:,} records where it is known'
        text += f'; {c["missingCount"] / profile["rowCount"] * 100:.1f}% of records leave it blank.' if c['coverage'] < 90 else '.'
        found.append({'text': text, 'source': c['name']})
    return found


def insights(profile):
    found, trended = [], set()
    series = profile.get('timeSeries')
    if series:
        records = _records(series)
        found += [records] if records else []
        for rate in chosen_rates(series):
            found.append(_rate(series, rate))
            trended.add(rate['key'])
    found += _dominant(profile) + _true_rates(profile, trended)
    return found[:MAX_INSIGHTS]
