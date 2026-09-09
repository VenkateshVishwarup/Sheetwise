import importlib
import pytest
from tests.test_ingest import make_csv


def profile(tmp_path):
    return importlib.import_module('backend.ingest').ingest_file(make_csv(tmp_path), 'users.csv', tmp_path / 'data')


def test_real_aggregate_results(tmp_path):
    query = importlib.import_module('backend.query')
    p = profile(tmp_path)
    result = query.execute_query(p, 'SELECT c1 AS status, COUNT(*) AS users FROM dataset GROUP BY c1 ORDER BY users DESC')
    assert result['rows'] == [['hot', 2], ['cold', 1]]
    result = query.execute_query(p, 'SELECT SUM(c5) AS spend FROM dataset')
    assert result['rows'] == [[30.0]]


@pytest.mark.parametrize('sql', [
    'DROP TABLE dataset',
    'SELECT COUNT(*) FROM dataset; SELECT 1',
    "SELECT * FROM read_csv('/etc/passwd')",
    'SELECT * FROM information_schema.tables',
    'SELECT c4, COUNT(*) FROM dataset GROUP BY c4',
    'SELECT c0 FROM dataset',
    "SELECT COUNT(*), read_blob('/etc/passwd') FROM dataset",
    'SELECT COUNT(*) FROM range(1000000000)',
    'SELECT COUNT(*) FROM other_dataset',
    'COPY dataset TO \'/tmp/export.csv\'',
    'SELECT c1 FROM dataset',
    'SELECT LIST(c1) FROM dataset',
    'SELECT MIN(d) AS d FROM dataset d',
    'SELECT c1 FROM dataset WHERE (SELECT COUNT(*) FROM dataset)>0',
    'WITH unused AS (SELECT COUNT(*) AS n FROM dataset) SELECT c1 FROM dataset',
])
def test_unsafe_queries_are_blocked(tmp_path, sql):
    query = importlib.import_module('backend.query')
    p = profile(tmp_path)
    with pytest.raises(ValueError):
        query.validate_sql(sql, p['columns'])


def test_valid_cte_and_unknown_column(tmp_path):
    query = importlib.import_module('backend.query')
    p = profile(tmp_path)
    query.validate_sql('WITH x AS (SELECT c1, COUNT(*) AS n FROM dataset GROUP BY c1) SELECT c1, SUM(n) FROM x GROUP BY c1', p['columns'])
    with pytest.raises(ValueError):
        query.validate_sql('SELECT unknown, COUNT(*) FROM dataset GROUP BY unknown', p['columns'])
