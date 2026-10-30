from __future__ import annotations

import json
import os
from pathlib import Path
import re

import pandas as pd

_DEFAULT_MAPPING_PATH = Path(__file__).resolve().parents[1] / 'data' / 'value_mappings.json'


def _normalize_key(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)) and float(value).is_integer():
        return str(int(value))
    text = str(value).strip()
    try:
        numeric = float(text)
    except ValueError:
        return text
    return str(int(numeric)) if numeric.is_integer() else text


def _add_display_column(df, source_column, decoded):
    display_column = f'{source_column}_display_name'
    if display_column in df.columns:
        df[display_column] = df[display_column].where(df[display_column].notna(), decoded)
    else:
        df[display_column] = decoded


def add_configured_value_labels(df: pd.DataFrame, mapping_path=None) -> pd.DataFrame:
    """Decode configured scalar and composite warehouse values into display columns."""
    path = Path(mapping_path or os.environ.get('VALUE_MAPPINGS_PATH') or _DEFAULT_MAPPING_PATH)
    with path.open(encoding='utf-8') as mapping_file:
        config = json.load(mapping_file)

    column_mappings = config.get('columns')
    composites = config.get('composites', [])
    if not isinstance(column_mappings, dict) or not isinstance(composites, list):
        raise ValueError(f'Value mapping file has an invalid structure: {path}')
    if any(not isinstance(mapping, dict) for mapping in column_mappings.values()):
        raise ValueError(f'Each entry in "columns" must be a value-to-label object: {path}')

    result = df.copy()
    columns_by_name = {str(column).casefold(): column for column in result.columns}
    normalized_mappings = {
        str(column).casefold(): {
            _normalize_key(key): str(label)
            for key, label in mapping.items()
        }
        for column, mapping in column_mappings.items()
    }

    for configured_column, mapping in normalized_mappings.items():
        source_column = columns_by_name.get(configured_column)
        if source_column is None:
            continue
        decoded = result[source_column].map(
            lambda value: mapping.get(_normalize_key(value), value)
        )
        _add_display_column(result, source_column, decoded)

    for composite in composites:
        if not isinstance(composite, dict):
            raise ValueError(f'Composite value mappings must be objects: {path}')
        pattern = re.compile(composite['pattern'])
        separator = composite['separator']
        parts = composite['parts']
        template = composite['template']
        if not isinstance(parts, list) or not parts or not isinstance(separator, str):
            raise ValueError(f'Composite mapping has invalid parts or separator: {path}')

        part_mappings = [
            normalized_mappings.get(str(part).casefold(), {})
            for part in parts
        ]
        for source_column in result.columns:
            if source_column.endswith('_display_name'):
                continue
            values = result[source_column].astype('string')
            if not values.str.fullmatch(pattern, na=False).any():
                continue

            def decode_composite(value):
                if pd.isna(value):
                    return value
                encoded_parts = str(value).split(separator)
                if len(encoded_parts) != len(parts):
                    return value
                labels = [
                    mapping.get(_normalize_key(part), part)
                    for part, mapping in zip(encoded_parts, part_mappings)
                ]
                return template.format(*labels)

            decoded = result[source_column].map(decode_composite)
            _add_display_column(result, source_column, decoded)

    return result
