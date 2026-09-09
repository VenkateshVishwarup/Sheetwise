from backend.privacy import field_privacy


def test_iso_date_is_not_a_phone_number():
    assert field_privacy('created_date',['2026-08-01'])[0] is False


def test_contact_values_beyond_sample_window_are_protected(tmp_path):
    from backend.ingest import ingest_file
    path=tmp_path/'data.csv'
    path.write_text('detail,region\n'+''.join(f'value-{i},west\n' for i in range(1100))+'person@example.com,east\n')
    p=ingest_file(path,path.name,tmp_path/'data')
    assert p['columns'][0]['sensitive'] is True
