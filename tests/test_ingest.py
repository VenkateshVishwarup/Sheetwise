import csv
import importlib


def make_csv(tmp_path):
    path = tmp_path / 'users.csv'
    with path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['user_id', 'lead_status', 'lead.is_converted', 'access_token', 'email', 'spend'])
        writer.writerows([
            ['001', 'Hot', 'true', 'SECRET123', 'a@example.com', '10'],
            ['002', 'hot', 'false', 'SECRET456', 'b@example.com', '20'],
            ['003', 'Cold', '', '', '', '0'],
        ])
    return path


def test_import_preserves_unknowns_and_excludes_secrets(tmp_path):
    ingest = importlib.import_module('backend.ingest')
    profile = ingest.ingest_file(make_csv(tmp_path), 'users.csv', tmp_path / 'data')
    assert profile['rowCount'] == 3
    assert profile['inputColumnCount'] == 6
    assert len(profile['columns']) == 5
    columns = {c['name']: c for c in profile['columns']}
    assert columns['lead.is_converted']['type'] == 'boolean'
    assert columns['lead.is_converted']['trueCount'] == 1
    assert columns['lead.is_converted']['falseCount'] == 1
    assert columns['lead.is_converted']['missingCount'] == 1
    assert columns['spend']['min'] == 0
    assert columns['user_id']['type'] == 'identifier'
    assert columns['email']['sensitive'] is True
    assert columns['lead_status']['distribution'][0]['count'] == 2
    assert all('SECRET' not in str(c) for c in profile['columns'])
    rows = ingest.preview_rows(profile, 0, 20)
    assert rows['rows'][0]['c0'] == '••••'
    assert rows['rows'][0]['c4'] == '••••'


def test_xlsx_first_sheet_and_duplicate_headers(tmp_path):
    import openpyxl
    ingest = importlib.import_module('backend.ingest')
    workbook = openpyxl.Workbook()
    workbook.active.append(['region', 'count'])
    workbook.active.append(['West', 4])
    path = tmp_path / 'input.xlsx'
    workbook.save(path)
    profile = ingest.ingest_file(path, 'input.xlsx', tmp_path / 'data')
    assert profile['rowCount'] == 1
    assert profile['sheetName'] == 'Sheet'
    invalid = tmp_path / 'bad.csv'
    invalid.write_text('a,a\n1,2\n')
    import pytest
    with pytest.raises(ValueError, match='unique'):
        ingest.ingest_file(invalid, 'bad.csv', tmp_path / 'data')


def test_phone_and_large_integer_values_are_not_analytical_measures(tmp_path):
    ingest = importlib.import_module('backend.ingest')
    path=tmp_path/'private.csv'
    path.write_text('region,alternate,big_value\nWest,9876543210,9007199254740993\nEast,9876543211,9007199254740992\n')
    p=ingest.ingest_file(path,path.name,tmp_path/'data')
    assert p['columns'][1]['sensitive']
    assert not p['columns'][2]['queryable']
    assert ingest.preview_rows(p)['rows'][0]['c1']=='••••'


def test_imprecise_decimal_and_scientific_values_stay_text(tmp_path):
    ingest=importlib.import_module('backend.ingest')
    path=tmp_path/'precise.csv'
    path.write_text('region,amount,scientific\nWest,9007199254740993.0,9.007199254740993e15\nEast,9007199254740992.0,9.007199254740992e15\n')
    p=ingest.ingest_file(path,path.name,tmp_path/'data')
    assert all(not c['queryable'] for c in p['columns'][1:])
    assert ingest.preview_rows(p)['rows'][0]['c1']=='9007199254740993.0'


def test_timestamps_in_common_export_formats_become_queryable_dates(tmp_path):
    import datetime as dt
    import duckdb
    ingest=importlib.import_module('backend.ingest')
    seconds=int(dt.datetime(2026,8,3,10,0,tzinfo=dt.timezone.utc).timestamp())
    path=tmp_path/'journey.csv'
    with path.open('w',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['region','timestamp','created_at','contacted_date','agent_endtime','callback_date'])
        writer.writerow(['West',str(seconds),str(seconds*1000),'03-08-2026, 10:23:45','2026-08-03T10:23:45.123Z','15-08-2026'])
        writer.writerow(['East',str(seconds+86400),str(seconds*1000+86400000),'04/08/2026 09:15','2026-08-04T09:00:00Z',''])
        writer.writerow(['North',str(seconds+172800),str(seconds*1000+172800000),'05/08/2026 11:00:00','2026-08-05T09:00:00Z',''])
    p=ingest.ingest_file(path,path.name,tmp_path/'data')
    columns={c['name']:c for c in p['columns']}
    for name in ('timestamp','created_at','contacted_date','agent_endtime','callback_date'):
        assert (columns[name]['type'],columns[name]['queryable'],columns[name]['sensitive'])==('date',True,False), name
    with duckdb.connect(p['databasePath'],read_only=True) as con:
        stamp,millis,contacted=con.execute(f"SELECT {columns['timestamp']['key']},{columns['created_at']['key']},{columns['contacted_date']['key']} FROM dataset ORDER BY 1").fetchall()[0]
    assert stamp==millis==dt.datetime(2026,8,3,10,0)
    assert contacted==dt.datetime(2026,8,3,10,23,45)
    assert any('timestamp' in w and 'Unix time' in w and 'UTC' in w for w in p['warnings'])


def test_date_rules_keep_birth_dates_contact_details_and_unlabelled_numbers_protected(tmp_path):
    ingest=importlib.import_module('backend.ingest')
    path=tmp_path/'people.csv'
    path.write_text('region,date_of_birth,contact_number,reference,response_time\nWest,15-08-1990,9876543210,1785751200,12\nEast,01-01-1985,9876543211,1785837600,30\n')
    p=ingest.ingest_file(path,path.name,tmp_path/'data')
    columns={c['name']:c for c in p['columns']}
    assert columns['date_of_birth']['sensitive'] is True
    assert columns['contact_number']['sensitive'] is True
    assert columns['reference']['sensitive'] is True
    assert columns['response_time']['type']=='number'
