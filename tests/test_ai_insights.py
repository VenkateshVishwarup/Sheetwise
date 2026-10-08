import csv
import json

import pytest

from backend.ingest import ingest_file


def imported(tmp_path):
    path = tmp_path / 'leads.csv'
    statuses = ['hot'] * 6 + ['cold'] * 5 + ['warm'] * 2 + ['lost']
    with path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['email', 'customer_name', 'status', 'converted', 'amount', 'created_date'])
        for i, status in enumerate(statuses):
            writer.writerow([f'person{i}@example.com', f'Asha Rao {i}', status, ['true', 'false', ''][i % 3], str(10 * (i + 1)), f'2026-08-{3 + i:02}'])
    return ingest_file(path, 'leads.csv', tmp_path / 'data')


def test_summary_sends_only_unprotected_totals_with_small_groups_merged(tmp_path):
    from backend.ai_insights import ai_summary
    summary = ai_summary(imported(tmp_path))
    sent = json.dumps(summary)
    assert '@' not in sent and 'Asha' not in sent
    assert 'email' not in sent and 'customer_name' not in sent
    columns = {c['name']: c for c in summary['columns']}
    assert set(columns) == {'status', 'converted', 'amount', 'created_date'}
    assert columns['status']['values'] == [{'label': 'hot', 'count': 6}, {'label': 'cold', 'count': 5}, {'label': 'other (groups under 5 records)', 'count': 3}]
    assert (columns['converted']['trueCount'], columns['converted']['falseCount'], columns['converted']['unknownCount']) == (5, 5, 4)
    assert (columns['amount']['min'], columns['amount']['max'], columns['amount']['mean']) == (10, 140, 75)
    assert summary['rowCount'] == 14
    assert summary['timeSeries']['grain'] == 'day' and len(summary['timeSeries']['periods']) == 14


def test_generated_insights_keep_only_those_citing_sent_columns(tmp_path):
    from backend.ai_insights import ai_summary, generate_ai_insights
    profile = imported(tmp_path)
    keys = {c['name']: c['key'] for c in profile['columns']}
    calls = []

    def provider(stage, payload):
        calls.append((stage, payload))
        return {'insights': [
            {'title': 'Hot leads lead', 'text': 'Hot is 6 of 14 statuses; call 98765 43210.', 'columns': [keys['status']]},
            {'title': 'Uses email', 'text': 'Protected.', 'columns': [keys['email']]},
            {'title': 'Invented', 'text': 'Unknown column.', 'columns': ['c99']},
            {'title': 'Uncited', 'text': 'No source.', 'columns': []},
            {'title': 'Conversion by status', 'text': 'Converted is true for half of known records.', 'columns': [keys['converted'], keys['status'], keys['converted']]},
        ]}

    run = generate_ai_insights(profile, provider)
    assert calls == [('insights', {'dataset': ai_summary(profile)})]
    assert run['insights'] == [
        {'title': 'Hot leads lead', 'text': 'Hot is 6 of 14 statuses; call [number removed].', 'source': 'status'},
        {'title': 'Conversion by status', 'text': 'Converted is true for half of known records.', 'source': 'converted · status'},
    ]
    assert run['datasetId'] == profile['id'] and run['model'] and run['createdAt']


def test_no_usable_insights_is_reported_as_a_service_problem(tmp_path):
    from backend.ai_insights import generate_ai_insights
    with pytest.raises(RuntimeError, match='no usable insights'):
        generate_ai_insights(imported(tmp_path), lambda stage, payload: {'insights': [{'title': 'x', 'text': 'y', 'columns': ['c99']}]})


def test_insights_stage_uses_its_own_instructions_and_strict_schema_without_storage(monkeypatch):
    from backend import agent
    captured = {}

    class Responses:
        def create(self, **request):
            captured.update(request)
            return type('Response', (), {'output_text': '{"insights": []}'})()

    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    monkeypatch.setattr(agent, 'OpenAI', lambda **options: type('Client', (), {'responses': Responses()})())
    assert agent.provider_call('insights', {'dataset': {'rowCount': 1}}) == {'insights': []}
    assert captured['store'] is False
    assert captured['instructions'] == agent.INSIGHTS_SYSTEM
    assert captured['text']['format']['schema'] == agent.INSIGHTS_SCHEMA and captured['text']['format']['strict'] is True


def test_ai_insights_api_generates_lists_and_is_deleted_with_the_dataset(tmp_path, monkeypatch):
    import importlib
    from fastapi.testclient import TestClient
    main = importlib.import_module('backend.main')
    monkeypatch.delenv('WORKSPACE_PASSWORD', raising=False)
    monkeypatch.setattr('backend.ai_insights.provider_call', lambda stage, payload: {'insights': [{'title': 'Status mix', 'text': 'Hot is the largest status.', 'columns': [payload['dataset']['columns'][0]['key']]}]})
    app = main.create_app(tmp_path / 'data', local_mode=True)
    client = TestClient(app)
    dataset_id = client.post('/api/demo').json()['id']
    assert client.get(f'/api/datasets/{dataset_id}/ai-insights').json() == []
    created = client.post(f'/api/datasets/{dataset_id}/ai-insights')
    assert created.status_code == 201, created.text
    assert created.json()['insights'][0]['title'] == 'Status mix'
    reloaded = TestClient(main.create_app(tmp_path / 'data', local_mode=True))
    assert [r['id'] for r in reloaded.get(f'/api/datasets/{dataset_id}/ai-insights').json()] == [created.json()['id']]
    assert client.delete(f'/api/datasets/{dataset_id}').status_code == 200
    assert app.state.store.ai_insights(dataset_id) == []
