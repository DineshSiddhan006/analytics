from __future__ import annotations
import math
import re
import numpy as np
import pandas as pd


_LABEL_SUFFIXES = ('name', 'label', 'tag', 'description', 'display_name')


def _category_label_column(df: pd.DataFrame, group: str) -> str | None:
    """Find a source-provided human-readable label that maps uniquely to a group key."""
    normalized = re.sub(r'_(id|key|code)$', '', str(group), flags=re.IGNORECASE).lower()
    choices = []
    for column in df.columns:
        candidate = str(column).lower()
        if candidate == group.lower():
            continue
        # Direct match: column named exactly <group>_display_name (created by add_configured_value_labels)
        if candidate == f'{group.lower()}_display_name':
            choices.append(column)
            continue
        if candidate in {f'{normalized}_{suffix}' for suffix in _LABEL_SUFFIXES}:
            choices.append(column)
        elif normalized and candidate.endswith(tuple(f'_{suffix}' for suffix in _LABEL_SUFFIXES)):
            prefix = re.sub(r'_(name|label|tag|description|display_name)$', '', candidate)
            if prefix == normalized:
                choices.append(column)
    if not choices:
        return None

    priority = {'display_name': 0, 'name': 1, 'label': 2, 'tag': 3, 'description': 4}
    choices.sort(key=lambda col: next(
        (priority[suffix] for suffix in _LABEL_SUFFIXES if str(col).lower().endswith(f'_{suffix}')),
        len(priority),
    ))
    for label_column in choices:
        paired = df[[group, label_column]].dropna().drop_duplicates()
        if paired.groupby(group, dropna=False)[label_column].nunique().le(1).all():
            return label_column
    return None


def _period_label_column(df: pd.DataFrame, group: str) -> str | None:
    name = str(group).lower()
    if name in {'month', 'quarter', 'day_of_week', 'weekday'}:
        return _category_label_column(df, group)
    return None


def execute(df: pd.DataFrame, spec: dict) -> pd.DataFrame:
    data = df.copy()
    for f in spec.get('filters', []):
        col, op, val = f.get('column'), f.get('operator'), f.get('value')
        if col not in data.columns: raise ValueError(f'Filter column not found: {col}')
        if op == 'eq': data = data[data[col] == val]
        elif op == 'neq':
            if isinstance(val, (list, tuple, set)):
                data = data[~data[col].isin(val)]
            else:
                data = data[data[col] != val]
        elif op == 'in': data = data[data[col].isin(val if isinstance(val,list) else [val])]
        elif op == 'gte': data = data[data[col] >= val]
        elif op == 'lte': data = data[data[col] <= val]
        else: raise ValueError(f'Unsupported filter operator: {op}')
    metric, agg, group = spec['metric'], spec['aggregation'], spec.get('group_by')
    if spec.get('chart') == 'histogram':
        values = pd.to_numeric(data[metric], errors='coerce').dropna()
        if values.empty:
            return pd.DataFrame(columns=['category', 'value'])
        bin_count = max(1, min(20, math.ceil(math.sqrt(len(values)))))
        minimum, maximum = float(values.min()), float(values.max())
        if minimum == maximum:
            if minimum >= 0:
                edges = np.linspace(minimum, minimum + max(abs(minimum) * 0.02, 1.0), 2)
            else:
                half_width = max(abs(minimum) * 0.01, 0.5)
                edges = np.linspace(minimum - half_width, minimum + half_width, 2)
        else:
            edges = np.linspace(minimum, maximum, bin_count + 1)
        counts, edges = np.histogram(values.to_numpy(), bins=edges)
        categories = [
            f'{left:g} - {right:g}'
            for left, right in zip(edges[:-1], edges[1:])
        ]
        return pd.DataFrame({'category': categories, 'value': counts})
    label_column = None
    if group:
        label_column = _category_label_column(data, group) or _period_label_column(data, group)
        if spec.get('period'):
            dates = pd.to_datetime(data[group], errors='coerce')
            if dates.notna().sum() == 0: raise ValueError(f"Period grouping requires a date column: {group}")
            grain = spec['period']
            if grain == 'day': data[group] = dates.dt.strftime('%Y-%m-%d')
            elif grain == 'week': data[group] = dates.dt.to_period('W').astype(str)
            elif grain == 'month': data[group] = dates.dt.to_period('M').astype(str)
            elif grain == 'quarter': data[group] = dates.dt.to_period('Q').astype(str)
            elif grain == 'year': data[group] = dates.dt.to_period('Y').astype(str)
        group_column = label_column or group
        grouped = data.groupby(group_column, dropna=False)[metric]
    else:
        data = data.assign(_all='All records')
        group = '_all'
        group_column = group
        grouped = data.groupby(group, dropna=False)[metric]
    fn = {'sum':'sum','mean':'mean','median':'median','min':'min','max':'max','count':'count','nunique':'nunique'}[agg]
    result = grouped.agg(fn).reset_index(name='value').rename(columns={group_column if group else group:'category'})
    if spec.get('chart') in {'line', 'area'}:
        if str(spec.get('group_by')).lower() in {'month', 'quarter', 'year'}:
            result['_sort'] = pd.to_numeric(result['category'], errors='coerce')
            return result.sort_values('_sort', kind='stable').drop(columns='_sort').reset_index(drop=True)
        return result.sort_values('category', kind='stable').reset_index(drop=True)
    return result.sort_values('value', ascending=False, kind='stable').reset_index(drop=True)
