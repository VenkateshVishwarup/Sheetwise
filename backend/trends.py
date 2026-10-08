"""Counts per time period for the overview trends, computed once at import."""
import datetime as dt

MIN_DATE_COVERAGE = 10
MIN_PERIODS = 3
MIN_KNOWN = 20  # fewest known true/false values for a period's rate to be shown
STEADY_FIT = 0.5  # R² at or above which a straight line describes the periods well
LEVEL_CHANGE = 0.1  # a fitted change under 10% of the average reads as level
MAX_PERIODS = 200
MAX_RATES = 12
# The widest range each grain covers before the next coarser one is used.
GRAINS = (('day', 31), ('week', 366), ('month', 3660), ('year', None))


def _next(start, grain):
    if grain == 'day':
        return start + dt.timedelta(days=1)
    if grain == 'week':
        return start + dt.timedelta(days=7)
    if grain == 'month':
        return dt.date(start.year + start.month // 12, start.month % 12 + 1, 1)
    return dt.date(start.year + 1, 1, 1)


def _truncate(day, grain):
    if grain == 'day':
        return day
    if grain == 'week':
        return day - dt.timedelta(days=day.weekday())
    if grain == 'month':
        return day.replace(day=1)
    return day.replace(month=1, day=1)


def time_series(con, columns, row_count):
    """Records and true/false answers per period of the best-populated date column; None when no trend is possible."""
    dates = [c for c in columns if c['queryable'] and c['type'] == 'date' and c['coverage'] >= MIN_DATE_COVERAGE]
    if not dates:
        return None
    axis = max(dates, key=lambda c: c['coverage'])
    key = axis['key']
    first, last = (v.date() for v in con.execute(f'SELECT MIN({key}), MAX({key}) FROM dataset').fetchone())
    span = (last - first).days
    grain = next(g for g, widest in GRAINS if widest is None or span <= widest)
    starts = [_truncate(first, grain)]
    while starts[-1] < _truncate(last, grain) and len(starts) <= MAX_PERIODS:
        starts.append(_next(starts[-1], grain))
    if not MIN_PERIODS <= len(starts) <= MAX_PERIODS:
        return None
    flags = sorted((c for c in columns if c['queryable'] and c['type'] == 'boolean'), key=lambda c: -c['coverage'])[:MAX_RATES]
    counts = ''.join(f', COUNT({c["key"]}), COUNT(*) FILTER (WHERE {c["key"]} = true)' for c in flags)
    grouped = {r[0]: r[1:] for r in con.execute(f"SELECT date_trunc('{grain}', {key})::DATE AS period, COUNT(*){counts} FROM dataset WHERE {key} IS NOT NULL GROUP BY period").fetchall()}
    empty = (0,) * (1 + 2 * len(flags))
    rows = [grouped.get(s, empty) for s in starts]
    buckets = [{'start': s.isoformat(), 'records': r[0], 'partial': False} for s, r in zip(starts, rows)]
    # A period is partial when the data starts after its first day or ends before its last day.
    buckets[0]['partial'] = first > starts[0]
    buckets[-1]['partial'] = buckets[-1]['partial'] or last < _next(starts[-1], grain) - dt.timedelta(days=1)
    rates = [{'key': c['key'], 'name': c['name'], 'coverage': c['coverage'], 'known': [r[1 + 2 * i] for r in rows], 'true': [r[2 + 2 * i] for r in rows]} for i, c in enumerate(flags)]
    return {'dateKey': key, 'dateName': axis['name'], 'coverage': axis['coverage'], 'grain': grain, 'first': first.isoformat(), 'last': last.isoformat(), 'buckets': buckets, 'rates': rates}


def percents(rate):
    """Percent true per period among known values; periods with too few known values stay blank."""
    return [round(100 * t / k, 1) if k >= MIN_KNOWN else None for k, t in zip(rate['known'], rate['true'])]


def linear_fit(values, buckets):
    """Least-squares line through complete periods with values, or None when fewer than three exist."""
    points = [(i, v) for i, (v, b) in enumerate(zip(values, buckets)) if v is not None and not b['partial']]
    if len(points) < MIN_PERIODS:
        return None
    n = len(points)
    mx, my = sum(x for x, _ in points) / n, sum(y for _, y in points) / n
    slope = sum((x - mx) * (y - my) for x, y in points) / sum((x - mx) ** 2 for x, _ in points)
    intercept = my - slope * mx
    total = sum((y - my) ** 2 for _, y in points)
    r2 = 1 - sum((y - intercept - slope * x) ** 2 for x, y in points) / total if total else 1.0
    low, high = points[0][0], points[-1][0]
    line = [round(intercept + slope * i, 2) if low <= i <= high else None for i in range(len(values))]
    return {'line': line, 'slope': slope, 'r2': r2, 'points': points}


def shape(fit):
    """steady, level or uneven, judged on the fitted change across complete periods; also returns their mean."""
    xs = [x for x, _ in fit['points']]
    mean = sum(v for _, v in fit['points']) / len(xs)
    change = fit['slope'] * (xs[-1] - xs[0]) / mean if mean else 0
    if abs(change) < LEVEL_CHANGE:
        return 'level', mean
    return ('steady' if fit['r2'] >= STEADY_FIT else 'uneven'), mean


def chosen_rates(series, limit=2):
    """Conversion-like fields first, then the best populated, keeping only rates that can be trended."""
    ranked = sorted(series['rates'], key=lambda r: (0 if 'convert' in r['name'].lower() else 1, -r['coverage']))
    return [r for r in ranked if linear_fit(percents(r), series['buckets'])][:limit]
