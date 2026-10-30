"""Build computed dashboard results from approved analytics definitions."""
from .executor import execute

def build_results(df, approved_specs):
    results=[]
    for spec in approved_specs:
        table=execute(df,spec)
        results.append({'spec':spec,'data':table})
    return results
