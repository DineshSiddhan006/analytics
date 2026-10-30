from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_warehouse_connector_has_no_local_file_fallback():
    source=(ROOT/'fabric_warehouse.py').read_text(encoding='utf-8').lower()
    assert 'read_csv' not in source
    assert 'read_parquet' not in source
    assert 'fallback' in source  # explicit no-fallback contract is documented
    assert 'load_table' in source

def test_ask_ai_feature_uses_current_dataset_context():
    text='\n'.join(p.read_text(encoding='utf-8') for p in [ROOT/'app.py', *list((ROOT/'ui').glob('*.py'))]).lower()
    assistant=(ROOT/'bi_pipeline'/'assistant.py').read_text(encoding='utf-8').lower()
    assert 'ask ai cargo intelligence' in text
    assert 'answer_dataset_question' in assistant
    assert 'dataset_profile' in assistant
