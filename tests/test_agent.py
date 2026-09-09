import importlib
from tests.test_ingest import make_csv


def test_agent_uses_metadata_and_repairs_invalid_sql(tmp_path):
    agent = importlib.import_module('backend.agent')
    p = importlib.import_module('backend.ingest').ingest_file(make_csv(tmp_path), 'users.csv', tmp_path / 'data')
    calls = []
    def provider(stage, payload):
        calls.append((stage, payload))
        if stage == 'plan':
            return {'columns': ['c1'], 'plan': 'Count records by lead status.', 'clarification': '', 'choices': []}
        if stage == 'generate':
            return {'sql': 'SELECT nope, COUNT(*) FROM dataset GROUP BY nope', 'title': 'Users by status', 'chartType': 'bar'}
        return {'sql': 'SELECT c1 AS status, COUNT(*) AS users FROM dataset GROUP BY c1 ORDER BY users DESC', 'title': 'Users by status', 'chartType': 'bar'}
    answer = agent.answer_question(p, 'How many users by lead status?', [], provider=provider)
    assert answer['result']['rows'] == [['hot', 2], ['cold', 1]]
    assert answer['attempts'] == 2
    assert len(calls) == 3
    assert all('a@example.com' not in str(payload) and 'SECRET' not in str(payload) for _,payload in calls)
    assert all('distribution' not in str(payload) for _,payload in calls)
    assert answer['messages'][0]['version'] == 'v0.9.1'
    assert answer['messages'][2]['updateDataModel']['value']['rows'][0]['users'] == 2


def test_clarification_never_executes_sql(tmp_path):
    agent = importlib.import_module('backend.agent')
    p = importlib.import_module('backend.ingest').ingest_file(make_csv(tmp_path), 'users.csv', tmp_path / 'data')
    def provider(stage, payload):
        assert stage == 'plan'
        return {'columns': [], 'plan': '', 'clarification': 'Which status field should I use?', 'choices': ['Lead status', 'Qualification status']}
    answer = agent.answer_question(p, 'Show conversion', [], provider=provider)
    assert answer['kind'] == 'clarification'
    assert answer['sql'] is None


def test_repairs_are_bounded(tmp_path):
    import pytest
    agent = importlib.import_module('backend.agent')
    p = importlib.import_module('backend.ingest').ingest_file(make_csv(tmp_path), 'users.csv', tmp_path / 'data')
    calls=[]
    def provider(stage, payload):
        calls.append(stage)
        return {'columns': ['c1'], 'plan': 'Count', 'clarification': '', 'choices': []} if stage=='plan' else {'sql': 'DROP TABLE dataset', 'title':'Oops', 'chartType':'table'}
    with pytest.raises(ValueError):
        agent.answer_question(p, 'Count users', [], provider=provider)
    assert calls == ['plan','generate','repair','repair']
