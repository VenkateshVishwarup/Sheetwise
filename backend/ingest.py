"""Bounded CSV/XLSX ingestion, exact profiling and masked previews."""
import csv
import datetime as dt
import math
import tempfile
import uuid
import zipfile
from pathlib import Path

import duckdb
from .privacy import SECRET, field_privacy, mask_text

MAX_BYTES = 100 * 1024 * 1024
MAX_ROWS = 2_000_000
MAX_COLUMNS = 500


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def json_value(value):
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _xlsx_csv(path, target, sheet_name):
    import openpyxl
    with zipfile.ZipFile(path) as archive:
        if sum(i.file_size for i in archive.infolist()) > 512 * 1024 * 1024:
            raise ValueError('The expanded workbook is too large. Export the worksheet as CSV.')
    book = openpyxl.load_workbook(path, read_only=True, data_only=True, keep_links=False)
    try:
        if sheet_name and sheet_name not in book.sheetnames:
            raise ValueError('That worksheet was not found in the workbook.')
        sheet = book[sheet_name] if sheet_name else book.worksheets[0]
        if sheet.max_column and sheet.max_column > MAX_COLUMNS:
            raise ValueError('A worksheet may have at most 500 columns.')
        with target.open('w', newline='', encoding='utf-8') as out:
            writer = csv.writer(out)
            for index, row in enumerate(sheet.iter_rows(values_only=True)):
                if index > MAX_ROWS:
                    raise ValueError('A dataset may have at most 2 million rows.')
                writer.writerow([v.isoformat() if isinstance(v, (dt.date, dt.datetime)) else v for v in row])
                if out.tell() > 512 * 1024 * 1024:
                    raise ValueError('The expanded worksheet exceeds 512 MB.')
        return sheet.title
    finally:
        book.close()


def ingest_file(path, filename, data_dir, sheet_name=None):
    path, data_dir = Path(path), Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Files must be 100 MB or smaller.')
    extension = Path(filename).suffix.lower()
    if extension not in ('.csv', '.xlsx'):
        raise ValueError('Choose a CSV or XLSX file.')
    dataset_id = str(uuid.uuid4())
    database_path = data_dir / f'{dataset_id}.duckdb'
    selected_sheet = None
    try:
        with tempfile.TemporaryDirectory(dir=data_dir) as temp:
            source = path
            if extension == '.xlsx':
                source = Path(temp) / 'sheet.csv'
                selected_sheet = _xlsx_csv(path, source, sheet_name)
            with source.open(encoding='utf-8-sig', newline='') as f:
                sample = f.read(65536)
                if not sample.strip():
                    raise ValueError('This file is empty.')
                try:
                    delimiter = csv.Sniffer().sniff(sample, delimiters=',;\t|').delimiter
                except csv.Error:
                    delimiter = ','
                f.seek(0)
                headers = next(csv.reader(f, delimiter=delimiter))
            if not headers or len(headers) > MAX_COLUMNS:
                raise ValueError('A dataset must have 1 to 500 columns.')
            if any(not h.strip() or len(h) > 160 for h in headers) or len({h.casefold().strip() for h in headers}) != len(headers):
                raise ValueError('Column headers must be nonempty, unique and no longer than 160 characters.')
            retained = [(i, h) for i, h in enumerate(headers) if not SECRET.search(h)]
            if not retained:
                raise ValueError('This file contains no usable columns after secret fields are excluded.')
            con = duckdb.connect(str(database_path), config={'memory_limit': '512MB', 'threads': '2'})
            try:
                projection = ', '.join(f'{quoted(h)} AS c{i}' for i, h in retained)
                con.execute(f'CREATE TABLE original AS SELECT {projection} FROM read_csv(?, header=true, all_varchar=true, delim=?, strict_mode=true, null_padding=false, max_line_size=4194304)', [str(source), delimiter])
                row_count = con.execute('SELECT COUNT(*) FROM original').fetchone()[0]
                if row_count == 0 or row_count > MAX_ROWS:
                    raise ValueError('Upload a table with 1 to 2 million data rows.')
                columns, expressions, warnings = [], [], []
                for i, name in retained:
                    key = f'c{i}'
                    clean = f"NULLIF(TRIM({key}), '')"
                    nonempty, distinct = con.execute(f'SELECT COUNT({clean}), COUNT(DISTINCT {clean}) FROM original').fetchone()
                    # Inspect all values for obvious content risks without exposing them externally.
                    samples = [r[0] for r in con.execute(f'SELECT DISTINCT {clean} FROM original WHERE {clean} IS NOT NULL LIMIT 1000').fetchall()]
                    sensitive, reason = field_privacy(name, samples)
                    # Risk classification scans the complete column; sampling only
                    # helps infer representation and never defines the privacy boundary.
                    if not sensitive:
                        found_personal, found_unstructured = con.execute(f"SELECT COUNT(*) FILTER (WHERE regexp_matches({clean}, '[^ ]+@[^ ]+[.][A-Za-z]+') OR ((regexp_full_match({clean}, '[+]?[0-9][0-9 ()-]{{8,}}[0-9]')) AND NOT regexp_full_match({clean}, '[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}')) OR starts_with({clean}, 'http://') OR starts_with({clean}, 'https://')), COUNT(*) FILTER (WHERE length({clean}) > 160 OR starts_with({clean}, '{{') OR starts_with({clean}, '[')) FROM original").fetchone()
                        if found_personal:
                            sensitive,reason=True,'personal'
                        elif found_unstructured:
                            sensitive,reason=True,'unstructured'
                    col = {'key': key, 'name': mask_text(name), 'type': 'category', 'missingCount': row_count-nonempty, 'distinctCount': distinct, 'coverage': round(nonempty / row_count * 100, 1), 'sensitive': sensitive, 'privacyReason': reason, 'queryable': not sensitive, 'distribution': []}
                    expression = clean
                    if reason == 'identifier':
                        col['type'] = 'identifier'
                    elif reason == 'unstructured':
                        col['type'] = 'text'
                    elif nonempty:
                        bool_count = con.execute(f"SELECT COUNT(*) FROM original WHERE LOWER({clean}) IN ('true','false')").fetchone()[0]
                        numeric_count = con.execute(f'SELECT COUNT(TRY_CAST({clean} AS DOUBLE)) FROM original').fetchone()[0]
                        date_formats = "['%Y-%m-%d','%Y-%m-%d %H:%M:%S','%Y-%m-%dT%H:%M:%S','%d/%m/%Y','%d/%m/%Y %I:%M %p','%d-%m-%Y %H:%M:%S']"
                        if bool_count == nonempty:
                            col['type'] = 'boolean'
                            expression = f'TRY_CAST({clean} AS BOOLEAN)'
                        elif numeric_count == nonempty and not sensitive:
                            max_magnitude,max_digits=con.execute(f"SELECT MAX(ABS(TRY_CAST({clean} AS DOUBLE))), MAX(LENGTH(regexp_replace(regexp_replace({clean}, '[eE].*$', ''), '[^0-9]', '', 'g'))) FROM original").fetchone()
                            if not math.isfinite(max_magnitude) or max_magnitude >= 2**53 or max_digits>15:
                                col['type']='text'
                                col['queryable']=False
                                warnings.append(f'{col["name"]}: kept as text to avoid loss of numerical precision.')
                            else:
                                col['type'] = 'number'
                                expression = f'TRY_CAST({clean} AS DOUBLE)'
                        elif ('date' in name.lower() or 'time' in name.lower()) and not sensitive:
                            date_expr = f'TRY_STRPTIME({clean}, {date_formats})'
                            date_count = con.execute(f'SELECT COUNT({date_expr}) FROM original').fetchone()[0]
                            if date_count == nonempty:
                                col['type'] = 'date'
                                expression = date_expr
                                if any('/' in v or '-' in v and not v.startswith(('19','20')) for v in samples):
                                    warnings.append(f'{col["name"]}: parsed day-first dates; verify this convention before comparing dates.')
                            else:
                                col['type'] = 'text'
                                col['queryable'] = False
                        if col['type'] == 'category':
                            if distinct > 60 or any(len(v) > 80 for v in samples):
                                col['type'] = 'text'
                                col['queryable'] = False
                            else:
                                expression = f'LOWER({clean})'
                    col['queryable'] = col['queryable'] and col['type'] not in ('identifier', 'text') and nonempty > 0
                    columns.append(col)
                    expressions.append(f'{expression} AS {key}')
                con.execute('CREATE TABLE dataset AS SELECT ' + ', '.join(expressions) + ' FROM original')
                for col in columns:
                    key = col['key']
                    if col['queryable'] and col['type'] in ('boolean', 'category'):
                        grouped = con.execute(f'SELECT {key}, COUNT(*) n FROM dataset GROUP BY {key} ORDER BY n DESC, {key} LIMIT 12').fetchall()
                        col['distribution'] = [{'label': 'Unknown' if v is None else str(v).lower(), 'count': n} for v,n in grouped]
                        if col['type'] == 'boolean':
                            col['trueCount'], col['falseCount'] = con.execute(f'SELECT COUNT(*) FILTER (WHERE {key}=true), COUNT(*) FILTER (WHERE {key}=false) FROM dataset').fetchone()
                    elif col['queryable'] and col['type'] == 'number':
                        low, high, average, total = con.execute(f'SELECT MIN({key}), MAX({key}), AVG({key}), SUM({key}) FROM dataset').fetchone()
                        col.update({'min': json_value(low), 'max': json_value(high), 'mean': json_value(average), 'sum': json_value(total)})
                sparse = sum(c['coverage'] < 10 for c in columns)
                if sparse:
                    warnings.insert(0, f'{sparse} columns are more than 90% empty. Missing values stay unknown.')
                excluded = len(headers)-len(retained)
                if excluded:
                    warnings.insert(0, f'{excluded} secret field(s) excluded from the analytical copy.')
                for a in columns:
                    if 'status' in a['name'].lower() and a['queryable'] and a['type'] == 'category':
                        for b in columns:
                            if a['key'] < b['key'] and 'status' in b['name'].lower() and b['queryable'] and b['type']=='category':
                                # Only flag fields whose value vocabulary overlaps.
                                av = {x['label'] for x in a['distribution'] if x['label'] != 'Unknown'}
                                bv = {x['label'] for x in b['distribution'] if x['label'] != 'Unknown'}
                                if len(av & bv) >= 2:
                                    mismatch = con.execute(f'SELECT COUNT(*) FROM dataset WHERE {a["key"]} IS NOT NULL AND {b["key"]} IS NOT NULL AND {a["key"]} != {b["key"]}').fetchone()[0]
                                    if mismatch:
                                        warnings.append(f'{a["name"]} and {b["name"]} differ for {mismatch:,} records. They remain separate definitions.')
                return {'id': dataset_id, 'name': mask_text(Path(filename).stem), 'filename': mask_text(Path(filename).name), 'rowCount': row_count, 'inputColumnCount': len(headers), 'columnCount': len(columns), 'excludedCount': excluded, 'sizeBytes': path.stat().st_size, 'createdAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'sheetName': selected_sheet, 'columns': columns, 'warnings': warnings[:12], 'databasePath': str(database_path.resolve())}
            finally:
                con.close()
    except Exception as exc:
        database_path.unlink(missing_ok=True)
        if isinstance(exc, ValueError):
            raise
        raise ValueError('Could not read this table. Check encoding, row lengths, and file format. CSV must use UTF-8; export XLSX values before uploading formulas.') from None


def preview_rows(profile, offset=0, limit=25):
    with duckdb.connect(profile['databasePath'], read_only=True) as con:
        records = con.execute('SELECT * FROM original LIMIT ? OFFSET ?', [limit, offset]).fetchall()
    columns = profile['columns']
    return {
        'columns': [{k: c[k] for k in ('key', 'name', 'type', 'sensitive')} for c in columns],
        'rows': [{c['key']: ('••••' if c['sensitive'] and v else (str(v)[:160] if v is not None else None)) for c, v in zip(columns, row)} for row in records],
        'total': profile['rowCount'], 'offset': offset,
    }
