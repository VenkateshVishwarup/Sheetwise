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
