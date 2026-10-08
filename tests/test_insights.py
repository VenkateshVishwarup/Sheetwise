from backend.insights import insights


def weekly(records, partial_last=False, rates=()):
    starts = ['2026-08-03', '2026-08-10', '2026-08-17', '2026-08-24', '2026-08-31', '2026-09-07'][:len(records)]
    buckets = [{'start': s, 'records': n, 'partial': False} for s, n in zip(starts, records)]
    buckets[-1]['partial'] = partial_last
    return {'dateKey': 'c0', 'dateName': 'created_date', 'coverage': 100.0, 'grain': 'week', 'first': starts[0], 'last': starts[-1], 'buckets': buckets, 'rates': list(rates)}


def profile(series=None, columns=(), rows=1000):
    return {'rowCount': rows, 'columns': list(columns), 'timeSeries': series}


def category(key, name, distribution, missing=0, queryable=True):
    return {'key': key, 'name': name, 'type': 'category', 'queryable': queryable, 'coverage': 100.0, 'distinctCount': len(distribution), 'missingCount': missing, 'distribution': distribution}


def texts(p):
    return [i['text'] for i in insights(p)]


def test_steady_record_growth_is_described_from_complete_periods():
    assert texts(profile(weekly([100, 150, 200, 260, 50], partial_last=True))) == [
        'Records per week rose steadily, from 100 in the week of 3 Aug to 260 in the week of 24 Aug (about +53 per week).',
    ]
    assert insights(profile(weekly([100, 150, 200, 260])))[0]['source'] == 'created_date'


def test_uneven_records_name_the_peak_and_the_latest_complete_period():
    assert texts(profile(weekly([100, 300, 500, 200, 50, 30], partial_last=True))) == [
        'No steady trend in records per week: the peak was 500 in the week of 17 Aug, and the latest complete week (31 Aug) had 50, 90% below the peak.',
    ]


def test_flat_records_are_called_level():
    assert texts(profile(weekly([100, 104, 98, 101, 99]))) == ['Records per week held roughly level at about 100.']


def test_rate_trends_report_known_values_and_how_often_the_field_is_answered():
    rate = {'key': 'c1', 'name': 'is_converted', 'coverage': 20.9, 'known': [100] * 5, 'true': [8, 6, 4, 2, 1]}
    found = insights(profile(weekly([100] * 5, rates=[rate])))
    assert found[1] == {
        'text': 'is_converted was true for 8.0% of known records in the week of 3 Aug, falling steadily to 1.0% in the week of 31 Aug. It is known for 20.9% of records.',
        'source': 'is_converted · created_date',
    }


def test_dominant_categories_and_true_rates_without_dates():
    columns = [
        category('c1', 'call_status', [{'label': 'connected', 'count': 620}, {'label': 'busy', 'count': 300}, {'label': 'failed', 'count': 80}]),
        category('c2', 'region', [{'label': 'west', 'count': 400}, {'label': 'east', 'count': 350}, {'label': 'north', 'count': 250}]),
        category('c3', 'stage', [{'label': 'Unknown', 'count': 700}, {'label': 'new', 'count': 250}, {'label': 'won', 'count': 50}], missing=700),
        category('c4', 'caller_city', [{'label': 'pune', 'count': 990}, {'label': 'goa', 'count': 10}], queryable=False),
        {'key': 'c5', 'name': 'demo_scheduled', 'type': 'boolean', 'queryable': True, 'coverage': 20.9, 'missingCount': 791, 'trueCount': 15, 'falseCount': 194, 'distribution': []},
    ]
    found = insights(profile(columns=columns))
    assert [i['text'] for i in found] == [
        '“new” makes up 83% of known stage values (250 of 300).',
        '“connected” makes up 62% of known call_status values (620 of 1,000).',
        'demo_scheduled is true for 7.2% of the 209 records where it is known; 79.1% of records leave it blank.',
    ]
    assert [i['source'] for i in found] == ['stage', 'call_status', 'demo_scheduled']


def test_at_most_five_insights():
    columns = [category(f'c{i}', f'field_{i}', [{'label': 'a', 'count': 900}, {'label': 'b', 'count': 100}]) for i in range(1, 5)]
    columns += [{'key': f'c{i}', 'name': f'flag_{i}', 'type': 'boolean', 'queryable': True, 'coverage': 100.0, 'missingCount': 0, 'trueCount': 500, 'falseCount': 500, 'distribution': []} for i in range(5, 7)]
    assert len(insights(profile(weekly([100] * 5), columns))) == 5
