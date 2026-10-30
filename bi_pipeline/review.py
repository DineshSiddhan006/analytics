from __future__ import annotations
from .specs import identity, validate_spec


def retire_unsupported_saved(saved, df):
    """Move legacy saved analytics unsupported by the current engine to rejected history."""
    approved, rejected = [], list(saved.get('rejected', []))
    rejected_ids = {item.get('identity') for item in rejected}
    retired = False
    for spec in saved.get('approved', []):
        try:
            validate_spec(spec, df)
            approved.append(spec)
        except ValueError as exc:
            reason = str(exc)
            if (
                'not supported by the current analytics engine' not in reason
                and 'Unsupported chart:' not in reason
                and 'charts require a grouping column' not in reason
                and 'charts require between 2 and 8 categories' not in reason
                and 'charts require a date/time grouping column' not in reason
                and 'Time period grouping requires a date/time column' not in reason
                and 'fewer than two distinct values' not in reason
                and 'nunique is not meaningful for high-cardinality numeric metric' not in reason
            ):
                approved.append(spec)
                continue
            key = spec.get('identity') or identity(spec)
            if key not in rejected_ids:
                rejected.append({
                    'identity': key,
                    'title': spec.get('title'),
                    'spec': spec,
                    'reason': f'Retired because this analysis is no longer supported: {reason}',
                })
                rejected_ids.add(key)
            retired = True

    if not retired:
        return saved, False

    valid_ids = {item.get('identity') for item in approved}
    updated = dict(saved)
    updated['approved'] = approved
    updated['edited'] = [
        item for item in saved.get('edited', [])
        if item.get('identity') in valid_ids
    ]
    updated['rejected'] = rejected
    return updated, True


def merge_for_review(saved, fresh, df):
    approved = saved.get('approved',[]); rejected = {x.get('identity') for x in saved.get('rejected',[])}
    result=[]; seen=set()
    for item in approved:
        try: spec=validate_spec(item,df); key=identity(spec)
        except Exception as exc:
            result.append({'status':'Previously approved - invalid for current data','include':False,'spec':item,'error':str(exc)}); continue
        if key not in seen: result.append({'status':'Previously approved','include':True,'spec':spec,'error':''}); seen.add(key)
    for item in fresh:
        key=item['identity']
        if key not in seen and key not in rejected:
            result.append({'status':'New suggestion','include':True,'spec':item,'error':''}); seen.add(key)
    return result

def commit_review(rows, df, previous):
    approved=[]; edited_by_key={x.get('identity'): x for x in previous.get('edited',[]) if x.get('identity')}; rejected=list(previous.get('rejected',[])); errors=[]; seen=set()
    for row in rows:
        spec=row.get('spec',{})
        if not row.get('include'):
            if row.get('status') != 'Previously approved - invalid for current data':
                key=spec.get('identity')
                if key and key not in {x.get('identity') for x in rejected}: rejected.append({'identity':key,'title':spec.get('title'),'spec':spec})
            continue
        try:
            clean=validate_spec(spec,df); key=clean['identity']
            if key not in seen:
                approved.append(clean); seen.add(key)
                original = row.get('original_spec')
                if original and any(original.get(k) != clean.get(k) for k in ('title','business_question','metric','aggregation','group_by','chart','period','filters','rationale')):
                    edited_by_key[key] = clean
                    old_key = original.get('identity')
                    if old_key and old_key != key and old_key not in {x.get('identity') for x in rejected}:
                        rejected.append({'identity':old_key,'title':original.get('title'),'spec':original,'reason':'superseded by user edit'})
        except Exception as exc: errors.append(f"{spec.get('title','Analytics')}: {exc}")
    approved_keys = {x.get('identity') for x in approved}
    edited = [value for key, value in edited_by_key.items() if key in approved_keys]
    return {'approved':approved,'edited':edited,'rejected':rejected}, errors
