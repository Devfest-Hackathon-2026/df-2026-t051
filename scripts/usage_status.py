"""Read-only operational view of the persistent daily analysis reservations."""
import json
from datetime import datetime,timezone,timedelta
from cloud_api import client,PROJECT

day=datetime.now(timezone(timedelta(hours=9))).date().isoformat()
url=f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents/chartbridge_usage/analysis-global-{day}'
with client() as api:
    response=api.get(url)
    if response.status_code==404:count=0
    else:
        response.raise_for_status();count=int(response.json()['fields']['count']['integerValue'])
print(json.dumps({'day_jst':day,'analysis_reserved_attempts':count,'configured_default_daily_limit':30,'remaining_at_default_limit':max(0,30-count),'warning':'Attempts include errors; this is not billed token usage or a Cloud Run spending cap.'}))
