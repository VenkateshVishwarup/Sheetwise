import pytest
from backend.privacy import field_privacy


def test_iso_date_is_not_a_phone_number():
    assert field_privacy('created_date',['2026-08-01'])[0] is False


def test_contact_values_beyond_sample_window_are_protected(tmp_path):
    from backend.ingest import ingest_file
    path=tmp_path/'data.csv'
    path.write_text('detail,region\n'+''.join(f'value-{i},west\n' for i in range(1100))+'person@example.com,east\n')
    p=ingest_file(path,path.name,tmp_path/'data')
    assert p['columns'][0]['sensitive'] is True


def test_contact_events_are_not_contact_details_but_birth_dates_are_personal():
    assert field_privacy('last_contacted_at',[]) == (False,'')
    assert field_privacy('contact',[])[0] is True
    assert field_privacy('date_of_birth',[])[0] is True
    assert field_privacy('user_dob',[])[0] is True


@pytest.mark.parametrize('name', ['customer_name', 'Customer Name', 'customerName', 'first_name', 'last_name', 'surname', 'name', 'display_name', 'agent_name', 'lead_name'])
def test_person_name_columns_are_personal(name):
    assert field_privacy(name, []) == (True, 'personal')


@pytest.mark.parametrize('name', ['template_name', 'campaign_name', 'ad_name', 'adset_name', 'file_name', 'company_name', 'product_name', 'business_type'])
def test_business_label_names_are_not_personal(name):
    assert field_privacy(name, []) == (False, '')
