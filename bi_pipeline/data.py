from __future__ import annotations
import json
import pandas as pd

def profile_dataset(df: pd.DataFrame) -> dict:
    """Profile every row and every column; the LLM receives whole-dataset statistics."""
    columns = []
    for name in df.columns:
        s = df[name]
        item = {'name': str(name), 'dtype': str(s.dtype), 'non_null': int(s.notna().sum()), 'nulls': int(s.isna().sum()), 'unique': int(s.nunique(dropna=True))}
        if pd.api.types.is_numeric_dtype(s):
            d = pd.to_numeric(s, errors='coerce')
            item.update({'min': _scalar(d.min()), 'max': _scalar(d.max()), 'mean': _scalar(d.mean()), 'median': _scalar(d.median()), 'sum': _scalar(d.sum())})
        elif pd.api.types.is_datetime64_any_dtype(s):
            item.update({'min': _scalar(s.min()), 'max': _scalar(s.max())})
        else:
            item['top_values'] = {str(k): int(v) for k, v in s.astype('string').value_counts(dropna=True).head(10).items()}
        columns.append(item)
    return {'rows': int(len(df)), 'columns_count': int(len(df.columns)), 'columns': columns}

def _scalar(v):
    if pd.isna(v): return None
    if hasattr(v, 'isoformat'): return v.isoformat()
    try: return v.item()
    except Exception: return v

def profile_prompt(profile: dict) -> str:
    return json.dumps(profile, ensure_ascii=False, default=str)
