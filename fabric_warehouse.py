"""Direct Microsoft Fabric warehouse access. There is deliberately no local-data fallback."""
from __future__ import annotations
import re
import pandas as pd
from config import SOURCE_CONNECTION_STRING, FABRIC_CONNECT_TIMEOUT, FABRIC_MAX_ROWS

class WarehouseError(RuntimeError): pass
_CONN = None

def _connect():
    global _CONN
    if _CONN is None:
        if not SOURCE_CONNECTION_STRING:
            raise WarehouseError('SOURCE_CONNECTION_STRING is missing from .env')
        try:
            import mssql_python
            _CONN = mssql_python.connect(SOURCE_CONNECTION_STRING, timeout=FABRIC_CONNECT_TIMEOUT)
        except Exception as exc:
            raise WarehouseError(f'Fabric warehouse connection failed: {exc}') from exc
    return _CONN

def quote_table(table: str) -> str:
    parts = [p.strip() for p in str(table).split('.')]
    if not 1 <= len(parts) <= 3 or any(not re.fullmatch(r'[A-Za-z0-9_ -]+', p) for p in parts):
        raise WarehouseError(f'Invalid warehouse table identifier: {table!r}')
    return '.'.join(f'[{p}]' for p in parts)

def query(sql: str) -> pd.DataFrame:
    try:
        cur = _connect().cursor()
        cur.execute(sql)
        cols = [c[0] for c in cur.description] if cur.description else []
        rows = cur.fetchall()
        cur.close()
        return pd.DataFrame.from_records(rows, columns=cols)
    except Exception as exc:
        raise WarehouseError(f'Warehouse query failed: {exc}') from exc

def list_tables() -> list[str]:
    df = query("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE IN ('BASE TABLE','VIEW') ORDER BY TABLE_SCHEMA,TABLE_NAME")
    return [f'{r[0]}.{r[1]}' for r in df.itertuples(index=False, name=None)]

def load_table(table: str) -> pd.DataFrame:
    limit = FABRIC_MAX_ROWS
    df = query(f'SELECT TOP ({limit + 1}) * FROM {quote_table(table)}')
    if df.empty: raise WarehouseError(f'{table} returned no rows')
    if len(df) > limit: raise WarehouseError(f'{table} exceeds FABRIC_MAX_ROWS={limit}; increase the limit. Data was not truncated.')
    return df


def add_dimension_labels(df: pd.DataFrame, fact_table: str) -> pd.DataFrame:
    """Enrich encoded product/route keys from unambiguous warehouse dimensions."""
    metadata = query(
        'SELECT TABLE_SCHEMA, TABLE_NAME, COLUMN_NAME '
        'FROM INFORMATION_SCHEMA.COLUMNS '
        'ORDER BY TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION'
    )
    if metadata.empty:
        return df

    tables = {}
    for schema, table, column in metadata.itertuples(index=False, name=None):
        name = f'{schema}.{table}'
        tables.setdefault(name, {})[str(column).lower()] = str(column)

    fact_name = str(fact_table).lower()
    result = df.copy()
    for key_column in df.columns:
        key_name = str(key_column)
        key_lower = key_name.lower()
        has_key_suffix = key_lower.endswith(('_id', '_key', '_code'))
        if not has_key_suffix and key_lower not in {'product', 'route', 'cargo_route'}:
            continue
        base_name = re.sub(r'_(id|key|code)$', '', key_lower)
        entity = base_name.split('_')[-1]
        if entity not in {'product', 'route'}:
            continue

        candidates = []
        for dimension, columns in tables.items():
            if dimension.lower() == fact_name:
                continue
            dimension_name = dimension.rsplit('.', 1)[-1].lower()
            if entity not in dimension_name:
                continue
            dimension_keys = [
                column for column in columns.values()
                if str(column).lower() == key_lower
                or (
                    has_key_suffix
                    and re.sub(r'_(id|key|code)$', '', str(column).lower()).split('_')[-1] == entity
                    and str(column).lower().endswith(('_id', '_key', '_code'))
                )
                or (
                    not has_key_suffix
                    and str(column).lower() in {
                        f'{base_name}_id', f'{base_name}_key', f'{base_name}_code',
                    }
                )
            ]
            if len(dimension_keys) != 1:
                continue
            dimension_key = dimension_keys[0]
            label_columns = [
                column for column in columns.values()
                if str(column).lower() in {
                    f'{base_name}_name',
                    f'{base_name}_label',
                    f'{base_name}_tag',
                    f'{base_name}_description',
                    f'{base_name}_display_name',
                    f'{entity}_name',
                    f'{entity}_label',
                    f'{entity}_tag',
                    'name',
                    'label',
                    'tag',
                    'description',
                    'display_name',
                }
                and str(column).lower() != str(dimension_key).lower()
            ]
            for label_column in label_columns:
                score = (
                    2 if str(label_column).lower().startswith(f'{base_name}_') else 0
                ) + (
                    1 if str(label_column).lower().endswith('_name') else 0
                )
                candidates.append((score, dimension, dimension_key, label_column))

        if not candidates:
            continue
        best_score = max(candidate[0] for candidate in candidates)
        best = [candidate for candidate in candidates if candidate[0] == best_score]
        if len(best) != 1:
            continue

        _, dimension, dimension_key, label_column = best[0]
        sql = (
            f'SELECT DISTINCT TOP (100001) {quote_table(dimension_key)}, '
            f'{quote_table(label_column)} FROM {quote_table(dimension)} '
            f'WHERE {quote_table(dimension_key)} IS NOT NULL '
            f'AND {quote_table(label_column)} IS NOT NULL'
        )
        mapping = query(sql)
        if len(mapping) > 100000:
            raise WarehouseError(
                f'Label dimension {dimension} has more than 100000 rows; refusing an incomplete label mapping.'
            )
        mapping = mapping.drop_duplicates()
        mapping = mapping.rename(columns={dimension_key: key_name})
        if mapping.groupby(key_name, dropna=False)[label_column].nunique().gt(1).any():
            continue

        label_name = f'{base_name}_display_name'
        labels = mapping.set_index(key_name)[label_column]
        result[label_name] = result[key_column].map(labels)

    return result
