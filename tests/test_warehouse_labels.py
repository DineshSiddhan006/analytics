import pandas as pd

import fabric_warehouse


def test_dimension_name_labels_are_joined_to_encoded_ids(monkeypatch):
    fact = pd.DataFrame({
        'cargo_route_id': ['14_1_1', '19_3_3'],
        'Weight_KG': [12, 22],
    })
    calls = []

    def fake_query(sql):
        calls.append(sql)
        if 'INFORMATION_SCHEMA.COLUMNS' in sql:
            return pd.DataFrame([
                ('dbo', 'cargo_features', 'cargo_route_id'),
                ('dbo', 'cargo_features', 'Weight_KG'),
                ('dbo', 'dim_route', 'route_id'),
                ('dbo', 'dim_route', 'route_name'),
            ], columns=['TABLE_SCHEMA', 'TABLE_NAME', 'COLUMN_NAME'])
        return pd.DataFrame({
            'route_id': ['14_1_1', '19_3_3'],
            'route_name': ['North Coast', 'Central Express'],
        })

    monkeypatch.setattr(fabric_warehouse, 'query', fake_query)

    enriched = fabric_warehouse.add_dimension_labels(fact, 'dbo.cargo_features')

    assert enriched['cargo_route_display_name'].tolist() == ['North Coast', 'Central Express']
    assert len(calls) == 2
    assert '[dbo].[dim_route]' in calls[1]
