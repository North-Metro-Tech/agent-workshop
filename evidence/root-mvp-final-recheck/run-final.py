"""Final acceptance recheck; approved synthetic tests and bounded native reads only.
No package installation, live restart, native mutation, or risk self-approval.
"""
from pathlib import Path
import json, os, shutil, subprocess, hashlib, datetime
R=Path(__file__).resolve().parents[2]
E=Path(__file__).resolve().parent
P=R/'evidence/root-mvp-closure'
PY='/home/aaron/hermes-agent/.venv/bin/python'
BASE='5f7df84da20206a89d87a8ed692dff537edfefc4'
SC='df2ef871a6f45c1c82d65bb055ac500403fce80f'

def run(args,name,cwd=R,env=None,expected=0,raw=False,timeout=300):
    p=subprocess.run(args,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    (E/name).write_bytes(p.stdout if raw else ('COMMAND: '+repr(args)+'\n').encode()+p.stdout+('\nEXIT_CODE: '+str(p.returncode)+'\n').encode())
    print(name,p.returncode,flush=True)
    assert p.returncode==expected,(name,p.returncode)
    return p.stdout

assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()=='fb56ff612d7533b7882d1549f208a90e0df14392'
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=R)
run([PY,str(P/'verify.py')],'preserved-checkpoint-readback.txt')
run(['npm','--prefix','frontend','run','typecheck'],'frontend-typecheck.txt')
run(['npm','--prefix','frontend','run','test','--','--run'],'frontend-tests.txt')
run(['npm','--prefix','frontend','run','build'],'frontend-build.txt')
env=dict(os.environ,PYTHONPATH=str(R/'.venv/lib/python3.11/site-packages')+':'+str(R/'backend')+':'+str(R/'collectors'),PYTHONDONTWRITEBYTECODE='1')
run([PY,'-m','pytest','-q','--junitxml='+str(E/'backend-junit.xml')],'backend-tests.txt',env=env)
run([str(R/'.venv/bin/python'),'scripts/dev.py','schema','--check'],'schema-check.txt')
for cmd in ('demo','collector-demo','check'):
    a=run([PY,'scripts/dev.py',cmd],cmd+'.txt')
    if cmd!='check': assert a==run([PY,'scripts/dev.py',cmd],cmd+'-repeat.txt')
e2e=dict(os.environ,WORKSHOP_E2E_PYTHON=str(R/'.venv/bin/python'),WORKSHOP_E2E_CHROMIUM='/home/aaron/.local/bin/chromium',PLAYWRIGHT_JSON_OUTPUT_NAME=str(E/'browser.json'))
for k in ['WORKSHOP_LOGIN_TOKEN','WORKSHOP_E2E_TOKEN','WORKSHOP_E2E_URL']:e2e.pop(k,None)
scene=R/'evidence/phase3-remediation/browser-scene.png'
original=scene.read_bytes()
try:
    run(['npm','--prefix','frontend','run','test:e2e','--','--reporter=list,json'],'browser.txt',env=e2e)
    shutil.copy2(scene,E/'synthetic-browser-scene.png')
finally:
    scene.write_bytes(original)
stats=json.loads((E/'browser.json').read_text())['stats']
assert stats['expected']==4 and all(stats[k]==0 for k in ('skipped','unexpected','flaky'))
audit=run(['sfw','npm','audit','--include=dev','--json'],'npm-audit.json',cwd=R/'frontend',raw=True,expected=1)
prod=run(['sfw','npm','audit','--omit=dev','--json'],'npm-production-audit.json',cwd=R/'frontend',raw=True)
ad=json.loads(audit);pr=json.loads(prod)
assert ad['metadata']['vulnerabilities']['high']==1 and ad['metadata']['vulnerabilities']['total']==1
assert set(ad['vulnerabilities'])=={'happy-dom'} and pr['metadata']['vulnerabilities']['total']==0
assert 'GHSA-834v-8h66-3h79' in audit.decode()
# Same previously approved read-only source, isolated Workshop state in this clone.
for n in (1,2):
    d=json.loads(run([str(R/'.venv/bin/python'),'scripts/observe_workflow.py','--approved-local'],f'one-shot-workflow-{n}.json',raw=True))
    assert d['source_projection_agreement'] and d['native_fence']['unchanged'] and all(c['agrees'] for c in d['comparisons'])
    assert d['runtime_coverage']=='partial' and d['role_availability']=='unknown' and not d['native_write_enabled']
# Copy the already-reviewed corrected verifier without editing old evidence.
for name in ('live-browser.mjs','verify-installed.py'):shutil.copy2(P/name,E/name)
run([str(R/'.venv/bin/python'),str(E/'verify-installed.py'),'before'],'native-before.txt')
run(['node',str(E/'live-browser.mjs')],'live-browser.txt')
run([str(R/'.venv/bin/python'),str(E/'verify-installed.py')],'historian-readback.txt')
run([str(R/'.venv/bin/python'),str(E/'verify-installed.py'),'sample'],'live-resource-sample.txt')
run(['systemctl','--user','show','agent-workshop-release1.service','-p','ActiveState','-p','SubState','-p','Restart','-p','NRestarts','-p','UnitFileState','-p','ExecMainStartTimestamp'],'live-service.txt')
run(['tailscale','serve','status'],'serve-status.txt')
for label,url in [('loopback','http://127.0.0.1:8765/'),('tailnet','https://frankenfarm.taile4f46c.ts.net:10000/')]:
    assert run(['curl','--silent','--show-error','--max-time','20','-o','/dev/null','-w','%{http_code}',url],label+'-http.txt')==b'200'
# Verbatim copies, not new scenario execution. Each retains its original head/date/test names.
D=E/'accepted-scenarios';D.mkdir(exist_ok=True)
provenance={}
for a in [f'A{i:02d}' for i in range(1,11)]+['A23','A25']:
    raw=subprocess.check_output(['git','show',SC+':evidence/'+a+'.txt'],cwd=R.parent/'final-sweep-a87670b9')
    assert b'Candidate: d56e3ccf6f332fd4b578fa47cd2e2a7f24a726d4' in raw and b'Pinning tests:' in raw and b'Scenario result: PASS' in raw
    (D/(a+'.txt')).write_bytes(raw)
    provenance[a]={'source_commit':SC,'source_path':'evidence/'+a+'.txt','sha256':hashlib.sha256(raw).hexdigest(),'fresh_at_final_head':False}
(D/'PROVENANCE.json').write_text(json.dumps(provenance,indent=2)+'\n')
now=datetime.datetime.now(datetime.timezone.utc)
assert now.timestamp()<1793124353.295,'Core acceptance expiry requires re-evaluation'
(E/'verified-at.json').write_text(json.dumps({'at_utc':now.isoformat(),'product':BASE,'root_run':os.environ.get('HERMES_KANBAN_RUN_ID'),'accepted_dev_risk_card':'t_817d72ca','acceptance_still_before_patch_eligibility':True,'actual_dev_audit_exit':1,'actual_production_audit_exit':0},indent=2)+'\n')
print('FINAL TESTS/LIVE READBACK PASS; DEV AUDIT STILL FAILS, SEPARATELY CORE-ACCEPTED',flush=True)
