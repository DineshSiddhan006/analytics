from __future__ import annotations
import uuid
from fabric_warehouse import add_dimension_labels, load_table
from .data import profile_dataset
from .llm import propose_analytics
from .review import merge_for_review, commit_review, retire_unsupported_saved
from .results import build_results
from .store import JsonPlanStore
from .value_mappings import add_configured_value_labels
from config import PLAN_STORE_DIR

class AnalyticsService:
    def __init__(self, store=None): self.store=store or JsonPlanStore(PLAN_STORE_DIR)
    def plan_run(self, table, progress=None):
        def report(message):
            if progress:
                progress(message)

        report('Loading the selected warehouse table...')
        df=add_configured_value_labels(add_dimension_labels(load_table(table),table))
        report('Profiling the loaded dataset...')
        profile=profile_dataset(df)
        report('Loading saved analytics and checking prior plans...')
        saved=self.store.load(table)
        saved, changed=retire_unsupported_saved(saved,df)
        if changed:
            self.store.save(table,saved)
        report('Generating and validating analytics proposals...')
        context,fresh,errors=propose_analytics(df,profile,table,saved.get('approved',[]),saved.get('rejected',[]))
        review=merge_for_review(saved,fresh,df)
        report(f'Prepared {len(review)} analytics for review.')
        return {'run_id':uuid.uuid4().hex,'table':table,'df':df,'profile':profile,'context':context,'review':review,'proposal_errors':errors}
    def proceed(self, run, rows):
        table=run['table']; previous=self.store.load(table)
        state,errors=commit_review(rows,run['df'],previous)
        if errors: raise ValueError('\n'.join(errors))
        self.store.save(table,state)
        outputs=build_results(run['df'],state['approved'])
        return {'run_id':run['run_id'],'table':table,'df':run['df'],'profile':run['profile'],'context':run['context'],'outputs':outputs}
