"""Bounded readback of the failed private QA historian, without opening a writer."""
import sys,json,sqlite3,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path[:0]=[str(R/'backend'),str(R/'collectors')]
from workshop.storage import _restore,_unpack
from workshop.delta import apply_difference
from workshop_collectors.hermes_work import HermesWork,approved_scope,linux_process_probe
from workshop_collectors.hermes_runtime import HermesRuntime,runtime_binding
from workshop.contracts import ExecutionKey
scope=approved_scope();obs=HermesRuntime(HermesWork(scope,process_probe=linux_process_probe),runtime_binding(scope))
snapshot=obs.observe(board=scope.board,acquired_at=time.monotonic());current={x['execution_id']:x for x in snapshot.observations()}
result={}
for label,p in [('isolated',R/'.workshop-state/workflow-historian.db'),('installed',Path('/home/aaron/.local/share/agent-workshop/release1/state-schema2/approved-local/historian.db'))]:
 db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True,isolation_level=None);db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
 data=None
 for rev,raw in db.execute('SELECT revision,state FROM revisions ORDER BY revision'):
  c=_unpack(raw)
  data=c['value'] if c['format']=='anchor-v2' else apply_difference(data,c['value'])
 state=_restore(data);ing=state.ingests['runtime'];records=ing.records
 rows=[]
 for identity in ['42','43','44','45']:
  fact=state.reducer.executions.get(ExecutionKey(obs.binding.runtime,identity))
  rows.append({'id':identity,'current_source':current.get(identity),'saved_lifecycle':None if fact is None else vars(fact.lifecycle),'saved_task':None if fact is None else vars(fact.task),'saved_discrepancies':None if fact is None else len(fact.discrepancies),'retained_records':[x for x in records if x['attributes'].get('workshop.execution.id')==identity]})
 result[label]={'revision':rev,'reconcile_required':ing.reconcile_required,'rows':rows}
 db.execute('COMMIT');db.close()
print(json.dumps(result,indent=2,default=str))
