from __future__ import annotations
import hashlib, json
import re
import pandas as pd
AGGS = {'sum','mean','median','min','max','count','nunique'}
CHARTS = {'bar','barh','pie','donut','line','area','histogram'}
PERIODS = {None, 'day', 'week', 'month', 'quarter', 'year'}
UNSUPPORTED_ANALYSIS = re.compile(
    r'\b(correlat\w*|lag|rolling|forecast\w*|predict\w*|cumulative|percentages?|ratios?)\b',
    re.IGNORECASE,
)


def _is_time_column(column, series) -> bool:
    name = str(column).lower()
    return (
        pd.api.types.is_datetime64_any_dtype(series)
        or any(part in name for part in ('date', 'time', 'timestamp'))
        or name in {'month', 'quarter', 'year'}
    )


def _is_identifier_column(column) -> bool:
    return bool(re.search(r'_(id|key|code)$', str(column), re.IGNORECASE))


def _is_high_cardinality_numeric(df: pd.DataFrame, column) -> bool:
    if not pd.api.types.is_numeric_dtype(df[column]) or _is_identifier_column(column):
        return False
    unique_count = int(df[column].nunique(dropna=True))
    threshold = max(50, min(500, int(len(df) * 0.01)))
    return unique_count > threshold


def identity(spec: dict) -> str:
    core = {k: spec.get(k) for k in ('metric','aggregation','group_by','period','filters')}
    raw = json.dumps(core, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:20]

def validate_spec(raw: dict, df: pd.DataFrame) -> dict:
    if not isinstance(raw, dict): raise ValueError('Analytics proposal must be an object')
    metric = raw.get('metric')
    if not isinstance(metric, str) or not metric.strip():
        raise ValueError('Metric is required. Choose a dataset column.')
    metric = metric.strip()
    group = raw.get('group_by')
    if metric not in df.columns: raise ValueError(f'Unknown metric column: {metric}. Choose a column from the dataset.')
    if group is not None and (
        not isinstance(group, str) or not group.strip() or group not in df.columns
    ):
        raise ValueError(f'Unknown grouping column: {group}')
    if group and int(df[group].nunique(dropna=True)) < 2:
        raise ValueError(
            f'Grouping column {group} has fewer than two distinct values; it cannot support a comparison.'
        )
    agg = str(raw.get('aggregation','sum')).lower()
    chart = str(raw.get('chart','bar')).lower()
    if agg not in AGGS: raise ValueError(f'Unsupported aggregation: {agg}')
    if chart not in CHARTS: raise ValueError(f'Unsupported chart: {chart}')
    if agg == 'nunique' and _is_high_cardinality_numeric(df, metric):
        raise ValueError(
            f'nunique is not meaningful for high-cardinality numeric metric {metric}; use a supported measure aggregation.'
        )
    if agg in {'sum','mean','median','min','max'} and not pd.api.types.is_numeric_dtype(df[metric]):
        raise ValueError(f'{agg} requires a numeric metric: {metric}')
    if chart == 'histogram' and not pd.api.types.is_numeric_dtype(df[metric]):
        raise ValueError(f'histogram requires a numeric metric: {metric}')
    if chart in {'pie', 'donut'}:
        if not group:
            raise ValueError(f'{chart} charts require a grouping column.')
        category_count = int(df[group].nunique(dropna=True))
        if not 2 <= category_count <= 8:
            raise ValueError(f'{chart} charts require between 2 and 8 categories. Use a bar chart instead.')
    period = raw.get('period') or None
    if period not in PERIODS: raise ValueError(f'Unsupported time period: {period}')
    if period and (
        not group or group not in df.columns or not _is_time_column(group, df[group])
    ):
        raise ValueError(f'Time period grouping requires a date/time column: {group}')
    if chart in {'line', 'area'} and (
        not group or not _is_time_column(group, df[group])
    ):
        raise ValueError(f'{chart} charts require a date/time grouping column.')
    description = ' '.join(
        str(raw.get(key, '')) for key in ('title', 'business_question', 'rationale')
    )
    unsupported = UNSUPPORTED_ANALYSIS.search(description)
    if unsupported:
        raise ValueError(
            f"'{unsupported.group(0)}' analysis is not supported by the current analytics engine."
        )
    filters = raw.get('filters') or []
    if not isinstance(filters, list): raise ValueError('Filters must be a list')
    for item in filters:
        if not isinstance(item, dict) or item.get('column') not in df.columns: raise ValueError(f'Invalid filter column: {item.get("column") if isinstance(item,dict) else item}')
        operator = item.get('operator')
        value = item.get('value')
        if operator not in {'eq','neq','in','gte','lte'}: raise ValueError(f'Unsupported filter operator: {operator}')
        if operator == 'in' and not isinstance(value, (list, tuple, set)):
            raise ValueError('The in filter operator requires a list of values.')
        if operator in {'eq', 'gte', 'lte'} and isinstance(value, (list, tuple, set)):
            raise ValueError(f'The {operator} filter operator requires a single value.')
    spec = {'title': str(raw.get('title') or f'{agg.title()} of {metric} by {group or "dataset"}'), 'business_question': str(raw.get('business_question','')), 'metric': metric, 'aggregation': agg, 'group_by': group, 'chart': chart, 'period': period, 'filters': filters, 'rationale': str(raw.get('rationale',''))}
    spec['identity'] = identity(spec)
    return spec
