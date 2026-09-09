"""Fail-closed SQL validation and a killable, read-only DuckDB worker."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import duckdb
import sqlglot
from sqlglot import exp
from .ingest import json_value

ALLOWED_FUNCTIONS = {'COUNT','SUM','AVG','MIN','MAX','ROUND','ABS','CEIL','FLOOR','COALESCE','NULLIF','LOWER','UPPER','TRIM','LENGTH','CAST','TRY_CAST','DATE_TRUNC','TIMESTAMP_TRUNC','EXTRACT','YEAR','MONTH','DAY','STRFTIME','TIME_TO_STR','IF','CASE','PERCENTILE_CONT','APPROX_DISTINCT','STDDEV','STDDEV_SAMP','VARIANCE','POWER','SQRT','GREATEST','LEAST'}


def validate_sql(sql, columns):
    if len(sql) > 12000:
        raise ValueError('Query is too long.')
    try:
        statements = sqlglot.parse(sql, read='duckdb')
    except sqlglot.errors.ParseError:
        raise ValueError('SQL could not be parsed. Use the DuckDB dialect.') from None
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError('Only one SELECT query is allowed.')
    tree = statements[0]
    if tree.find(exp.Subquery):
        raise ValueError('Nested subqueries are disabled. Use a grouped aggregate or a CTE.')
    if any(tree.find_all(exp.Join, exp.Union, exp.Intersect, exp.Except, exp.Window)):
        raise ValueError('Joins, set operations and window functions are not enabled for this single-table MVP.')
    ctes = {c.alias for c in tree.find_all(exp.CTE)}
    if any(c.args.get('recursive') for c in tree.find_all(exp.With)):
        raise ValueError('Recursive queries are not allowed.')
    tables = list(tree.find_all(exp.Table))
    if not tables or not any(t.name == 'dataset' for t in tables):
        raise ValueError('Queries must use the selected dataset.')
    for table in tables:
        if not isinstance(table.this, exp.Identifier) or table.db or table.catalog or table.name not in {'dataset', *ctes}:
            raise ValueError('Only the selected dataset is accessible. File and external table access are blocked.')
    for node in tree.find_all(exp.Func):
        name = node.name.upper() if isinstance(node, exp.Anonymous) else node.sql_name().upper()
        if name not in ALLOWED_FUNCTIONS:
            raise ValueError(f'The function {name[:40]} is not allowed.')
    for select in tree.find_all(exp.Select):
        local_aggregates=[a for a in select.find_all(exp.AggFunc) if a.find_ancestor(exp.Select) is select]
        if not local_aggregates:
            raise ValueError('Each query scope must aggregate. Individual row extraction is disabled in chat.')
    protected = {c['key'] for c in columns if not c['queryable']}
    allowed = {c['key'] for c in columns if c['queryable']}
    aliases = {a.alias for a in tree.find_all(exp.Alias)}
    table_aliases = {t.alias_or_name for t in tables}
    for column in tree.find_all(exp.Column):
        if column.name in table_aliases:
            raise ValueError('Whole-row table references are disabled.')
        if column.name in protected:
            raise ValueError('This query references a protected or unstructured column. Use aggregate-safe fields.')
        if column.name not in allowed | aliases:
            raise ValueError(f'Unknown column {column.name[:40]}. Use only the supplied column keys.')
    for star in tree.find_all(exp.Star):
        if not isinstance(star.parent, exp.Count):
            raise ValueError('SELECT * is disabled. Select explicit aggregate columns.')
    # Cap after the whole query so aggregation semantics are unchanged.
    return tree.sql(dialect='duckdb')


def _worker(database_path, keys, sql, pipe):
    try:
        with duckdb.connect(':memory:', config={'autoload_known_extensions':'false','autoinstall_known_extensions':'false','memory_limit':'256MB','threads':'1','max_temp_directory_size':'0B'}) as con:
            # Physically omit protected values before any model-generated SQL runs.
            path=database_path.replace("'", "''")
            con.execute(f"ATTACH '{path}' AS source (READ_ONLY)")
            projection=', '.join(keys) if keys else '1 AS __record'
            con.execute(f'CREATE TABLE dataset AS SELECT {projection} FROM source.dataset')
            con.execute('DETACH source')
            con.execute('SET enable_external_access=false')
            con.execute('SET lock_configuration=true')
            cur = con.execute(f'SELECT * FROM ({sql}) AS answer LIMIT 201')
            names = [d[0] for d in cur.description]
            rows = [[json_value(v) for v in row] for row in cur.fetchall()]
            if any(v is not None and not isinstance(v,(str,int,float,bool)) for row in rows for v in row):
                raise ValueError('Only scalar aggregate results are supported.')
            if any(isinstance(v, str) and len(v)>500 for row in rows for v in row):
                raise ValueError('Result values exceed the display limit.')
            pipe.send({'columns': names, 'rows': rows[:200], 'truncated': len(rows)>200})
    except Exception as exc:
        # Avoid sending database snippets, paths or source values back to the AI.
        pipe.send({'error': type(exc).__name__, 'message': 'Query execution failed. Check types, grouping and column references.'})
    finally:
        pipe.close()


def execute_query(profile, sql, timeout=10):
    safe_sql = validate_sql(sql, profile['columns'])
    keys=[c['key'] for c in profile['columns'] if c['queryable']]
    # Start a dedicated module instead of importing the hosting platform's __main__
    # through multiprocessing. Pass dependencies, but no provider/storage credentials.
    environment={key:os.environ[key] for key in ('PATH','LD_LIBRARY_PATH','DYLD_LIBRARY_PATH','LANG','LC_ALL','SYSTEMROOT') if key in os.environ}
    environment['PYTHONPATH']=os.pathsep.join(sys.path)
    process=subprocess.Popen([sys.executable,'-m','backend.query_worker'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=Path(__file__).resolve().parents[1],env=environment)
    start = time.monotonic()
    try:
        try:
            output,_=process.communicate(json.dumps({'databasePath':profile['databasePath'],'keys':keys,'sql':safe_sql}).encode(),timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise ValueError('This query exceeded 10 seconds. Ask a narrower question.')
        try:
            result=json.loads(output)
        except (json.JSONDecodeError,UnicodeDecodeError):
            raise ValueError('The query worker stopped. Try a smaller aggregation.') from None
        if 'error' in result:
            raise ValueError(result['message'])
        result['elapsedMs'] = round((time.monotonic()-start)*1000)
        return result
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate()
