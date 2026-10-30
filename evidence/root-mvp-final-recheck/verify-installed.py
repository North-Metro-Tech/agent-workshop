"""Read-only installed historian and exact HTTP snapshot evidence. No Storage writer."""
import hashlib,json,os,sqlite3,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/home/aaron/.local/share/agent-workshop/release1/checkout-schema2')
HERE=Path(__file__).resolve().parent
STATE=ROOT.parent/'state-schema2/approved-local'
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'collectors'),str(ROOT/'scripts')]
from workshop.storage import _unpack,_restore
from workshop.delta import apply_difference
from workshop.api import LocalAPI
from workshop.web_projection import project
from workshop_collectors.hermes_work import approved_scope
from observe_work import fence

def connection(name='historian.db'):
    db=sqlite3.connect((STATE/name).as_uri()+'?mode=ro',uri=True,isolation_level=None)
    db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
    return db

def sections(db):
    data=None
    for seq,raw in db.execute('SELECT revision,state FROM revisions ORDER BY revision'):
        checkpoint=_unpack(raw)
        if checkpoint['format']=='anchor-v2': data=checkpoint['value']
        elif checkpoint['format']=='delta-v2' and data is not None: data=apply_difference(data,checkpoint['value'])
        else: raise AssertionError('Missing anchor')
        yield seq,data

def sample():
    unit=dict(x.split('=',1) for x in subprocess.check_output(['systemctl','--user','show','agent-workshop-release1.service','-p','MemoryCurrent','-p','MainPID','-p','ActiveState','-p','SubState','-p','Restart','-p','NRestarts','-p','UnitFileState'],text=True).splitlines())
    assert unit['ActiveState']=='active' and unit['SubState']=='running' and unit['Restart']=='no' and unit['NRestarts']=='0'
    proc=Path('/proc',unit['MainPID'])
    status=dict(x.split(':',1) for x in (proc/'status').read_text().splitlines() if ':' in x)
    db=connection()
    try:
        assert db.execute('PRAGMA user_version').fetchone()[0]==2
        revision=_unpack(db.execute("SELECT payload FROM metadata WHERE id='revision'").fetchone()[0])
        revs=db.execute('SELECT COUNT(*),SUM(length(state)+length(event)),MIN(revision),MAX(revision) FROM revisions').fetchone()
        e=[_unpack(r[0]) for r in db.execute('SELECT payload FROM executions')]
        ing=[_unpack(r[0])['state'] for r in db.execute('SELECT payload FROM ingests')]
        state_bytes=sum(db.execute('SELECT coalesce(sum(length(payload)),0) FROM '+t).fetchone()[0] for t in ('roles','feeds','executions','correlations','ambiguities','alarm_rules','alarm_controls','alarm_occurrences','alarm_audit','ingests','metadata'))
        anchors=[seq for seq,raw in db.execute('SELECT revision,state FROM revisions ORDER BY revision') if _unpack(raw)['format']=='anchor-v2']
        allocated=sum(p.stat().st_size for p in STATE.glob('historian.db*') if p.is_file())
        expected=sorted({revs[2]}|{seq for seq in range(revs[2],revs[3]+1) if (seq-1)%32==0})
        assert anchors==expected
        result={'at':datetime.now(timezone.utc).isoformat(),'monotonic':time.monotonic(),'unit':unit,'rss_kb':int(status['VmRSS'].split()[0]),'revision':revision,'retained_revisions':revs[0],'oldest':revs[2],'revision_event_bytes':revs[1],'state_bytes':state_bytes,'allocated_db_wal_shm_bytes':allocated,'anchors':anchors,'executions':len(e),'observation_counts':{str(x.key):len(x.observations) for x in e},'record_counts':[len(x['records']) for x in ing],'seen_counts':[len(x['_seen']) for x in ing]}
    finally: db.execute('COMMIT');db.close()
    q=connection('service-outbox.db')
    try:
        result['outbox_pending']=q.execute('SELECT COUNT(*) FROM pending').fetchone()[0]
        result['outbox_allocated_bytes']=sum(p.stat().st_size for p in STATE.glob('service-outbox.db*'))
    finally:q.execute('COMMIT');q.close()
    return result

def verify_snapshots():
    scope=approved_scope(); db=connection()
    try:
        identity=_unpack(db.execute("SELECT payload FROM metadata WHERE id='identity'").fetchone()[0])
        captures={name:json.loads((HERE/name).read_text()) for name in ('browser-snapshot-initial.json','browser-snapshot-final.json')}
        results=[]
        for seq,data in sections(db):
            for name,actual in captures.items():
                if actual['cursor']!=f'{identity}:{seq}': continue
                state=_restore(data)
                expected=project({'cursor':actual['cursor'],'projection':LocalAPI(state.reducer).snapshot(now=actual['generated_at'])},now=actual['generated_at'],source_mode='approved-local')
                assert json.loads(expected.model_dump_json())==actual
                ingest=state.ingests['runtime']
                assert state.source_identities['runtime']==(scope.path.stat().st_dev,scope.path.stat().st_ino)
                assert ingest.records and actual['native_write_enabled'] is False
                for r in ingest.records:
                    rid=json.loads(r['attributes']['workshop.record.id'])
                    assert rid[0]=='outbox-v1' and rid[1]==ingest._epoch
                results.append({'file':name,'cursor':actual['cursor'],'items':len(actual['items']),'source_cursor':state.source_cursors['runtime'],'outbox_epoch':ingest._epoch,'all_items_equal_exact_durable_revision':True,'native_identity_matches':True,'original_record_identities_verified':True})
        assert len(results)==len(captures),'Capture expired: rerun browser explicitly'
    finally:db.execute('COMMIT');db.close()
    q=connection('service-outbox.db')
    try:
        meta=json.loads(q.execute('SELECT value FROM meta WHERE id=1').fetchone()[0]); pending=q.execute('SELECT COUNT(*) FROM pending').fetchone()[0]
        assert meta['epoch']==results[-1]['outbox_epoch'] and meta['next_cursor']>results[-1]['source_cursor']
    finally:q.execute('COMMIT');q.close()
    before=json.loads((HERE/'native-fence-before.json').read_text()); after=fence(scope.path)
    assert before['schema_sha256']==after['schema_sha256']
    report={'result':'PASS','exact_service_revision_checks':results,'live_outbox':{'epoch':meta['epoch'],'next_cursor':meta['next_cursor'],'pending_at_readback':pending},'native_fence':{'before':before,'after':after,'unchanged':before==after,'limits':'Main/schema measured interval only; concurrent native writers live; excludes WAL/SHM; no causal write-attribution or kernel read-only boundary claim'}}
    (HERE/'historian-readback.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':
    if sys.argv[1:] == ['before']:
        scope=approved_scope();(HERE/'native-fence-before.json').write_text(json.dumps(fence(scope.path),indent=2)+'\n')
        unit=sample()['unit']; pid=unit['MainPID']
        mount=Path('/proc',pid,'mountinfo').read_text();(HERE/'service-mountinfo.txt').write_text(mount)
        native=scope.path.resolve(); applicable=[line for line in mount.splitlines() if Path(line.split()[4]) in (native,*native.parents)]
        nearest=max(applicable,key=lambda line:len(line.split()[4]))
        (HERE/'mount-observation.json').write_text(json.dumps({'pid':pid,'native_mount':nearest,'effective_readonly_observed':'ro' in nearest.split()[5].split(','),'limit':'Observation only; systemd requested properties do not establish effective restrictions'},indent=2)+'\n')
        print('Captured native fence and actual mountinfo; no effective hardening inference')
    elif sys.argv[1:] == ['sample']: print(json.dumps(sample(),indent=2))
    else: verify_snapshots()
