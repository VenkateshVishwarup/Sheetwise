import csv
from backend.ingest import ingest_file


def write_rows(tmp_path, header, rows, name='events.csv'):
    path = tmp_path / name
    with path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return ingest_file(path, name, tmp_path / 'data')


def test_weekly_series_fills_empty_weeks_and_marks_the_unfinished_last_week(tmp_path):
    profile = write_rows(tmp_path, ['created_date', 'converted'], [
        ['2026-08-03', 'true'], ['2026-08-04', 'false'], ['2026-08-05', ''],
        ['2026-08-10', 'true'], ['2026-08-11', 'true'],
        ['2026-08-24', 'false'], ['2026-08-31', 'true'], ['2026-09-10', ''],
        ['', 'true'],
    ])
    series = profile['timeSeries']
    assert (series['dateKey'], series['dateName'], series['grain'], series['coverage']) == ('c0', 'created_date', 'week', 88.9)
    assert [b['start'] for b in series['buckets']] == ['2026-08-03', '2026-08-10', '2026-08-17', '2026-08-24', '2026-08-31', '2026-09-07']
    assert [b['records'] for b in series['buckets']] == [3, 2, 0, 1, 1, 1]
    assert [b['partial'] for b in series['buckets']] == [False, False, False, False, False, True]
    assert series['rates'] == [{'key': 'c1', 'name': 'converted', 'coverage': 77.8, 'known': [2, 2, 0, 1, 1, 0], 'true': [1, 2, 0, 0, 1, 0]}]


def test_grain_follows_the_date_range_and_a_late_start_marks_the_first_bucket_partial(tmp_path):
    daily = write_rows(tmp_path, ['event_date', 'n'], [['2026-08-01', '1'], ['2026-08-02', '2'], ['2026-08-04', '3']], 'daily.csv')
    assert daily['timeSeries']['grain'] == 'day'
    assert [b['records'] for b in daily['timeSeries']['buckets']] == [1, 1, 0, 1]
    monthly = write_rows(tmp_path, ['order_date'], [['2025-01-15'], ['2025-06-01'], ['2026-03-31']], 'monthly.csv')
    buckets = monthly['timeSeries']['buckets']
    assert monthly['timeSeries']['grain'] == 'month'
    assert (buckets[0]['start'], buckets[-1]['start'], len(buckets)) == ('2025-01-01', '2026-03-01', 15)
    assert (buckets[0]['partial'], buckets[-1]['partial']) == (True, False)


def test_no_series_without_a_well_populated_date_spanning_three_periods(tmp_path):
    assert write_rows(tmp_path, ['region'], [['west'], ['east']], 'nodate.csv')['timeSeries'] is None
    assert write_rows(tmp_path, ['created_date'], [['2026-08-01'], ['2026-08-02']], 'short.csv')['timeSeries'] is None
    sparse = [['2026-08-01'], ['2026-08-09'], ['2026-08-20']] + [['']] * 30
    assert write_rows(tmp_path, ['created_date'], sparse, 'sparse.csv')['timeSeries'] is None


def weekly(records, partial_last=True, rates=()):
    starts = ['2026-08-03', '2026-08-10', '2026-08-17', '2026-08-24', '2026-08-31', '2026-09-07'][:len(records)]
    buckets = [{'start': s, 'records': n, 'partial': False} for s, n in zip(starts, records)]
    buckets[-1]['partial'] = partial_last
    return {'columns': [], 'timeSeries': {'dateKey': 'c0', 'dateName': 'created_date', 'coverage': 88.9, 'grain': 'week', 'first': starts[0], 'last': '2026-09-10', 'buckets': buckets, 'rates': list(rates)}}


def card_data(card):
    return card['messages'][2]['updateDataModel']['value']


def test_records_trend_fits_a_dashed_line_through_complete_periods_only():
    from backend.presentation import trend_cards
    card = trend_cards(weekly([10, 20, 30, 5]))[0]
    data = card_data(card)
    assert (card['id'], card['source']) == ('trend-records', 'created_date')
    assert (data['labelKey'], data['valueKey'], data['trendKey']) == ('period', 'records', 'trend')
    assert data['rows'] == [
        {'period': '3 Aug', 'records': 10, 'trend': 10.0},
        {'period': '10 Aug', 'records': 20, 'trend': 20.0},
        {'period': '17 Aug', 'records': 30, 'trend': 30.0},
        {'period': '24 Aug (partial)', 'records': 5, 'trend': None},
    ]
    assert card['sql'] == "SELECT date_trunc('week', c0) AS period, COUNT(*) AS records FROM dataset WHERE c0 IS NOT NULL GROUP BY period ORDER BY period"
    component = card['messages'][1]['updateComponents']['components'][0]
    assert (component['component'], component['trendKey']) == ('LineChart', 'trend')
    assert 'partial' in component['subtitle'] and '88.9%' in component['subtitle']


def test_rate_trends_skip_thin_periods_and_prefer_conversion_fields():
    from backend.presentation import trend_cards
    rates = [
        {'key': 'c2', 'name': 'callback', 'coverage': 90.0, 'known': [25, 30, 10, 40, 40], 'true': [5, 3, 9, 2, 2]},
        {'key': 'c3', 'name': 'is_converted', 'coverage': 50.0, 'known': [20, 20, 20, 20, 20], 'true': [2, 4, 6, 8, 10]},
        {'key': 'c4', 'name': 'rarely_answered', 'coverage': 95.0, 'known': [5, 5, 5, 5, 5], 'true': [1, 1, 1, 1, 1]},
    ]
    cards = trend_cards(weekly([30, 30, 30, 30, 30], partial_last=False, rates=rates))
    assert [c['id'] for c in cards] == ['trend-records', 'trend-c3', 'trend-c2']
    converted, callback = card_data(cards[1]), card_data(cards[2])
    assert [r['percent_true'] for r in converted['rows']] == [10.0, 20.0, 30.0, 40.0, 50.0]
    assert [r['trend'] for r in converted['rows']] == [10.0, 20.0, 30.0, 40.0, 50.0]
    assert [r['percent_true'] for r in callback['rows']] == [20.0, 10.0, None, 5.0, 5.0]
    assert callback['rows'][2]['trend'] is not None
    assert cards[2]['sql'] == "SELECT date_trunc('week', c0) AS period, 100.0 * COUNT(*) FILTER (WHERE c2 = true) / NULLIF(COUNT(c2), 0) AS percent_true FROM dataset WHERE c0 IS NOT NULL GROUP BY period ORDER BY period"


def test_profiles_imported_before_trends_ask_for_a_fresh_import():
    from backend.presentation import trend_cards
    dated = {'key': 'c0', 'name': 'created_date', 'type': 'date', 'queryable': True, 'coverage': 100.0}
    legacy = trend_cards({'columns': [dated]})
    assert [c['id'] for c in legacy] == ['trends-reimport']
    assert 'Upload this file again' in card_data(legacy[0])['text']
    assert trend_cards({'columns': [dated], 'timeSeries': None}) == []
    assert trend_cards({'columns': []}) == []


def test_no_dashed_line_when_the_periods_have_no_steady_trend():
    from backend.presentation import trend_cards
    card = trend_cards(weekly([100, 300, 500, 200, 50, 30]))[0]
    assert all(r['trend'] is None for r in card_data(card)['rows'])
    assert 'no steady trend, so no trend line' in card['messages'][1]['updateComponents']['components'][0]['subtitle']


def test_too_few_complete_periods_are_named_as_the_reason_for_no_line():
    from backend.presentation import trend_cards
    profile = weekly([10, 20, 30])
    profile['timeSeries']['buckets'][0]['partial'] = True
    subtitle = trend_cards(profile)[0]['messages'][1]['updateComponents']['components'][0]['subtitle']
    assert 'too few complete weeks for a trend line' in subtitle
