import json
from bi_pipeline.store import JsonPlanStore

def test_json_roundtrip(tmp_path):
    store=JsonPlanStore(tmp_path)
    state={'approved':[{'identity':'a','title':'Revenue by region'}],'rejected':[{'identity':'b','title':'Count by type'}]}
    store.save('sales.orders',state)
    assert store.load('sales.orders')['approved']==state['approved']
    assert store.load('sales.orders')['rejected']==state['rejected']
    assert json.loads(next(tmp_path.glob('*.json')).read_text())['table']=='sales.orders'

def test_edited_list_roundtrip(tmp_path):
    store=JsonPlanStore(tmp_path)
    store.save('sales.orders', {'approved':[{'identity':'a'}], 'edited':[{'identity':'a','aggregation':'mean'}], 'rejected':[{'identity':'b'}]})
    loaded=store.load('sales.orders')
    assert loaded['edited'][0]['aggregation']=='mean'
