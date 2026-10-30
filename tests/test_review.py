import pandas as pd
from bi_pipeline.review import merge_for_review, commit_review, retire_unsupported_saved
from bi_pipeline.specs import validate_spec

def test_review_combines_frozen_and_new_and_remembers_removal():
    df=pd.DataFrame({'Region':['N','S'],'Revenue':[5,9]})
    old=validate_spec({'title':'Saved','metric':'Revenue','aggregation':'sum','group_by':'Region','chart':'bar'},df)
    new=validate_spec({'title':'New','metric':'Revenue','aggregation':'mean','group_by':'Region','chart':'pie'},df)
    saved={'approved':[old],'rejected':[]}
    rows=merge_for_review(saved,[new],df)
    assert [r['status'] for r in rows]==['Previously approved','New suggestion']
    rows[0]['include']=False
    state,errors=commit_review(rows,df,saved)
    assert not errors
    assert state['approved']==[new]
    assert any(r['identity']==old['identity'] for r in state['rejected'])

def test_edited_analytics_are_saved():
    df=pd.DataFrame({'Region':['N','S'],'Revenue':[5,9]})
    original=validate_spec({'metric':'Revenue','aggregation':'sum','group_by':'Region'},df)
    edited=validate_spec({'title':'Average by region','metric':'Revenue','aggregation':'mean','group_by':'Region','chart':'barh'},df)
    state,errors=commit_review([{'include':True,'spec':edited,'status':'Previously approved','original_spec':original}],df,{'approved':[original],'rejected':[]})
    assert not errors
    assert state['approved'][0]['aggregation']=='mean'
    assert state['approved'][0]['chart']=='barh'
    assert state['edited'][0]['aggregation']=='mean'
    assert state['edited'][0]['aggregation']=='mean'

def test_editing_measure_suppresses_the_old_identity():
    df=pd.DataFrame({'Region':['N','S'],'Revenue':[5,9],'Cost':[2,4]})
    old=validate_spec({'metric':'Revenue','aggregation':'sum','group_by':'Region'},df)
    changed=validate_spec({'metric':'Cost','aggregation':'sum','group_by':'Region'},df)
    state,errors=commit_review([{'include':True,'spec':changed,'status':'Previously approved','original_spec':old}],df,{'approved':[old],'edited':[],'rejected':[]})
    assert not errors
    assert any(x['identity']==old['identity'] for x in state['rejected'])
    assert state['edited'][0]['metric']=='Cost'

def test_legacy_unsupported_analytics_are_retired_from_saved_approvals():
    df = pd.DataFrame({
        'ShipDate': pd.to_datetime(['2026-01-01', '2026-02-01']),
        'Region': ['N', 'S'],
        'Weight': [10, 20],
    })
    supported = validate_spec({
        'title': 'Weight by date',
        'metric': 'Weight',
        'aggregation': 'sum',
        'group_by': 'ShipDate',
        'chart': 'line',
    }, df)
    unsupported = {
        'title': 'Weight correlation by region',
        'business_question': 'Is there a correlation between weight and region?',
        'metric': 'Weight',
        'aggregation': 'mean',
        'group_by': 'Region',
        'chart': 'scatter',
        'filters': [],
    }

    updated, changed = retire_unsupported_saved({
        'approved': [supported, unsupported],
        'edited': [],
        'rejected': [],
    }, df)

    assert changed
    assert updated['approved'] == [supported]
    assert updated['rejected'][0]['spec'] == unsupported
    assert 'no longer supported' in updated['rejected'][0]['reason']


def test_legacy_weak_high_cardinality_nunique_is_retired_from_approvals():
    df = pd.DataFrame({
        'Weight_KG': [float(value) for value in range(1000)],
        'cargo_route_id': ['R1'] * 500 + ['R2'] * 500,
    })
    weak = {
        'title': 'Unique weight values by route',
        'metric': 'Weight_KG',
        'aggregation': 'nunique',
        'group_by': 'cargo_route_id',
        'chart': 'barh',
        'period': None,
        'filters': [],
    }

    updated, changed = retire_unsupported_saved({
        'approved': [weak],
        'edited': [],
        'rejected': [],
    }, df)

    assert changed
    assert updated['approved'] == []
    assert updated['rejected'][0]['spec'] == weak
