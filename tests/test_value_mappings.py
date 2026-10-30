import json

import pandas as pd

from bi_pipeline.value_mappings import add_configured_value_labels


def test_configured_scalar_and_composite_codes_are_decoded(tmp_path):
    mapping = {
        'columns': {
            'Station_code': {'19': 'RUH'},
            'Product_code': {'3': 'GEN'},
            'Type': {'3': 'Transit Outbound'},
            'Station': {'19': 'Riyadh (RUH)'},
            'Product': {'3': 'General Cargo (GEN)'},
            'is_weekend': {'0': 'Weekday', '1': 'Weekend'},
        },
        'composites': [{
            'pattern': r'^\d+_\d+_\d+$',
            'separator': '_',
            'parts': ['Station', 'Product', 'Type'],
            'template': '{0} - {1} ({2})',
        }],
    }
    mapping_path = tmp_path / 'value_mappings.json'
    mapping_path.write_text(json.dumps(mapping), encoding='utf-8')
    df = pd.DataFrame({
        'Station': [19.0, 99.0],
        'cargo_route_id': ['19_3_3', '99_8_0'],
        'is_weekend': [0, 1],
    })

    enriched = add_configured_value_labels(df, mapping_path)

    assert enriched['Station_display_name'].tolist() == ['Riyadh (RUH)', 99.0]
    assert enriched['cargo_route_id_display_name'].tolist() == [
        'Riyadh (RUH) - General Cargo (GEN) (Transit Outbound)',
        '99 - 8 (0)',
    ]
    assert enriched['is_weekend_display_name'].tolist() == ['Weekday', 'Weekend']
    assert df['cargo_route_id'].tolist() == ['19_3_3', '99_8_0']


def test_value_mapping_column_matching_is_case_insensitive(tmp_path):
    mapping_path = tmp_path / 'value_mappings.json'
    mapping_path.write_text(json.dumps({
        'columns': {'product': {'3': 'General Cargo (GEN)'}},
        'composites': [],
    }), encoding='utf-8')

    enriched = add_configured_value_labels(
        pd.DataFrame({'PRODUCT': [3]}),
        mapping_path,
    )

    assert enriched['PRODUCT_display_name'].tolist() == ['General Cargo (GEN)']


def test_invalid_value_mapping_structure_is_reported(tmp_path):
    mapping_path = tmp_path / 'value_mappings.json'
    mapping_path.write_text('{"columns": [], "composites": []}', encoding='utf-8')

    try:
        add_configured_value_labels(pd.DataFrame({'Station': [1]}), mapping_path)
    except ValueError as exc:
        assert 'invalid structure' in str(exc)
    else:
        raise AssertionError('Invalid mapping configuration was silently accepted.')
