import pandas as pd
import pytest
from bi_pipeline.specs import validate_spec, identity
from bi_pipeline.executor import execute

def test_spec_validation_and_execution():
    df=pd.DataFrame({'Region':['A','A','B'],'Revenue':[10,20,5]})
    spec=validate_spec({'title':'Revenue by region','metric':'Revenue','aggregation':'sum','group_by':'Region','chart':'bar'},df)
    out=execute(df,spec)
    assert dict(zip(out.category,out.value))=={'A':30,'B':5}
    assert identity(spec)==spec['identity']

def test_invalid_metric_rejected():
    with pytest.raises(ValueError): validate_spec({'metric':'Missing','aggregation':'sum'},pd.DataFrame({'x':[1]}))

def test_missing_metric_has_actionable_validation_error():
    df = pd.DataFrame({'Weight_KG': [10]})
    for metric in (None, '', '   '):
        with pytest.raises(ValueError, match='Metric is required. Choose a dataset column.'):
            validate_spec({'metric': metric, 'aggregation': 'sum'}, df)

def test_chart_change_does_not_create_a_different_analytics_identity():
    df=pd.DataFrame({'Region':['N','S'],'Revenue':[5,9]})
    a=validate_spec({'metric':'Revenue','aggregation':'sum','group_by':'Region','chart':'bar'},df)
    b=validate_spec({'metric':'Revenue','aggregation':'sum','group_by':'Region','chart':'pie'},df)
    assert a['identity']==b['identity']

def test_monthly_period_grouping_uses_all_rows():
    df=pd.DataFrame({'ShipDate':pd.to_datetime(['2026-01-01','2026-01-20','2026-02-03']),'Tonnage':[2,3,7]})
    spec=validate_spec({'metric':'Tonnage','aggregation':'sum','group_by':'ShipDate','period':'month','chart':'bar'},df)
    out=execute(df,spec)
    assert list(out['category'])==['2026-02','2026-01']
    assert list(out['value'])==[7,5]

def test_line_chart_requires_a_time_group_and_sorts_chronologically():
    df = pd.DataFrame({
        'ShipDate': pd.to_datetime(['2026-03-01', '2026-01-01', '2026-02-01']),
        'Tonnage': [7, 5, 6],
    })
    spec = validate_spec({
        'metric': 'Tonnage',
        'aggregation': 'sum',
        'group_by': 'ShipDate',
        'chart': 'line',
    }, df)
    result = execute(df, spec)
    assert list(result['category']) == list(pd.to_datetime([
        '2026-01-01', '2026-02-01', '2026-03-01',
    ]))
    assert list(result['value']) == [5, 6, 7]

def test_line_chart_is_rejected_for_unordered_business_categories():
    with pytest.raises(ValueError, match='date/time grouping column'):
        validate_spec({
            'metric': 'Revenue',
            'aggregation': 'sum',
            'group_by': 'Region',
            'chart': 'line',
        }, pd.DataFrame({'Region': ['N', 'S'], 'Revenue': [1, 2]}))

def test_pie_chart_requires_a_small_grouping_column():
    df = pd.DataFrame({
        'Region': [f'Region {index}' for index in range(10)],
        'Revenue': list(range(10)),
    })
    with pytest.raises(ValueError, match='between 2 and 8 categories'):
        validate_spec({
            'metric': 'Revenue',
            'aggregation': 'sum',
            'group_by': 'Region',
            'chart': 'pie',
        }, df)

@pytest.mark.parametrize('question', [
    'Is there a correlation between weight and target?',
    'Forecast next quarter tonnage',
    'What is the cumulative cargo weight?',
])
def test_unsupported_analytics_are_not_accepted(question):
    with pytest.raises(ValueError, match='not supported'):
        validate_spec({
            'title': question,
            'business_question': question,
            'metric': 'Weight',
            'aggregation': 'mean',
            'chart': 'bar',
        }, pd.DataFrame({'Weight': [1, 2]}))

def test_histogram_counts_metric_values_into_bins():
    df = pd.DataFrame({'Weight_KG': [1, 2, 3, 10]})
    spec = validate_spec({
        'metric': 'Weight_KG',
        'aggregation': 'count',
        'chart': 'histogram',
    }, df)
    out = execute(df, spec)
    assert out['value'].sum() == len(df)
    assert out['category'].nunique() > 0


def test_histogram_does_not_expand_nonnegative_bins_below_zero():
    df = pd.DataFrame({'Weight_KG': [0.0, 0.0, 10.0, 20.0]})
    result = execute(df, {
        'metric': 'Weight_KG',
        'aggregation': 'count',
        'chart': 'histogram',
        'filters': [],
    })

    assert result['value'].sum() == len(df)
    assert min(float(category.split(' - ')[0]) for category in result['category']) == 0


def test_histogram_with_only_zero_values_has_no_negative_bin():
    df = pd.DataFrame({'Weight_KG': [0.0, 0.0, 0.0]})
    result = execute(df, {
        'metric': 'Weight_KG',
        'aggregation': 'count',
        'chart': 'histogram',
        'filters': [],
    })

    assert result['value'].tolist() == [3]
    assert result.iloc[0]['category'].startswith('0 - ')


def test_nunique_is_rejected_for_high_cardinality_numeric_measure():
    df = pd.DataFrame({
        'Weight_KG': [float(value) for value in range(1000)],
        'cargo_route_id': ['R1'] * 500 + ['R2'] * 500,
    })

    with pytest.raises(ValueError, match='nunique is not meaningful'):
        validate_spec({
            'metric': 'Weight_KG',
            'aggregation': 'nunique',
            'group_by': 'cargo_route_id',
            'chart': 'bar',
        }, df)


def test_grouping_with_only_one_distinct_value_is_rejected():
    df = pd.DataFrame({'Quarter': [1, 1, 1], 'Weight_KG': [10, 20, 30]})

    with pytest.raises(ValueError, match='fewer than two distinct values'):
        validate_spec({
            'metric': 'Weight_KG',
            'aggregation': 'mean',
            'group_by': 'Quarter',
            'chart': 'bar',
        }, df)

def test_ungrouped_aggregation_returns_the_dataset_total():
    df = pd.DataFrame({'Weight': [2, 5, 8]})
    result = execute(df, {
        'metric': 'Weight',
        'aggregation': 'sum',
        'group_by': None,
        'filters': [],
    })
    assert result.iloc[0]['value'] == 15

def test_neq_filter_accepts_empty_list_without_dataframe_shape_error():
    df = pd.DataFrame({'Region': ['North', 'South'], 'Revenue': [10, 20]})
    spec = validate_spec({
        'metric': 'Revenue',
        'aggregation': 'sum',
        'group_by': 'Region',
        'filters': [{'column': 'Region', 'operator': 'neq', 'value': []}],
    }, df)

    out = execute(df, spec)

    assert dict(zip(out['category'], out['value'])) == {'North': 10, 'South': 20}

def test_neq_filter_list_excludes_each_listed_value():
    df = pd.DataFrame({'Region': ['North', 'South', 'West'], 'Revenue': [10, 20, 30]})
    spec = validate_spec({
        'metric': 'Revenue',
        'aggregation': 'sum',
        'group_by': 'Region',
        'filters': [{'column': 'Region', 'operator': 'neq', 'value': ['South', 'West']}],
    }, df)

    out = execute(df, spec)

    assert dict(zip(out['category'], out['value'])) == {'North': 10}

def test_encoded_route_keys_use_source_name_or_tag_columns():
    df = pd.DataFrame({
        'cargo_route_id': ['14_1_1', '14_1_1', '19_3_3'],
        'cargo_route_display_name': ['North Coast', 'North Coast', 'Central Express'],
        'Tonnage': [10, 5, 20],
    })
    spec = validate_spec({
        'metric': 'Tonnage',
        'aggregation': 'sum',
        'group_by': 'cargo_route_id',
        'chart': 'barh',
    }, df)

    result = execute(df, spec)

    assert dict(zip(result['category'], result['value'])) == {
        'North Coast': 15,
        'Central Express': 20,
    }

def test_month_number_categories_render_as_month_names():
    from bi_pipeline.charts import _format_category

    assert _format_category(1, 'month') == 'Jan'
    assert _format_category(12, 'month') == 'Dec'
    assert _format_category(2, 'quarter') == 'Q2'

def test_in_filter_requires_list_value():
    df = pd.DataFrame({'Region': ['North'], 'Revenue': [10]})
    with pytest.raises(ValueError, match='requires a list'):
        validate_spec({
            'metric': 'Revenue',
            'aggregation': 'sum',
            'filters': [{'column': 'Region', 'operator': 'in', 'value': 'North'}],
        }, df)
