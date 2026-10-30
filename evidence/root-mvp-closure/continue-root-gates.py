"""Preserve non-audit verification without suppressing the failed audit gate."""
from pathlib import Path
import subprocess,os,json,datetime,shutil
W=Path(__file__).resolve().parent; R=W/'root-mvp-closure'; E=R/'evidence/root-mvp-closure'
PY='/home/aaron/hermes-agent/.venv/bin/python'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()=='5f7df84da20206a89d87a8ed692dff537edfefc4'
def run(args,name,cwd=R,env=None,timeout=300,required=True):
 with (E/name).open('w') as f:
  f.write('COMMAND: '+repr(args)+'\n');f.flush()
  p=subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  f.write('\nEXIT_CODE: '+str(p.returncode)+'\n')
 print(name,p.returncode,flush=True)
 if required: assert p.returncode==0,name
 return p.returncode
# Read-only metadata/advisory evidence; never npm audit fix or an age override.
run(['npm','view','happy-dom','time','--json'],'happy-dom-publication-times.txt')
run(['sfw','npm','audit','--include=dev','--json'],'npm-audit.json.txt',R/'frontend',required=False)
run(['sfw','npm','audit','--omit=dev','--json'],'npm-production-audit.json.txt',R/'frontend')
run(['npm','--prefix','frontend','run','typecheck'],'frontend-typecheck.txt')
run(['npm','--prefix','frontend','run','test','--','--run'],'frontend-tests.txt')
run(['npm','--prefix','frontend','run','build'],'frontend-build.txt')
env=dict(os.environ,PYTHONPATH=str(R/'.venv/lib/python3.11/site-packages')+':'+str(R/'backend')+':'+str(R/'collectors'),PYTHONDONTWRITEBYTECODE='1')
run([PY,'-m','pytest','-q','--junitxml='+str(E/'backend-junit.xml')],'backend-tests.txt',env=env)
run([str(R/'.venv/bin/python'),'scripts/dev.py','schema','--check'],'schema-check.txt')
for cmd,name in [('demo','demo'),('collector-demo','collector-demo'),('check','compile')]:
 run([PY,'scripts/dev.py',cmd],name+'.txt')
 if cmd!='check':
  run([PY,'scripts/dev.py',cmd],name+'-repeat.txt')
  assert (E/(name+'.txt')).read_bytes()==(E/(name+'-repeat.txt')).read_bytes()
run([str(R/'.venv/bin/python'),'-m','workshop.demo'],'installed-demo.txt',env=dict(os.environ,PYTHONPATH=''))
e2e=dict(os.environ,WORKSHOP_E2E_PYTHON=str(R/'.venv/bin/python'),WORKSHOP_E2E_CHROMIUM='/home/aaron/.local/bin/chromium',PLAYWRIGHT_JSON_OUTPUT_NAME=str(E/'browser.json'))
for k in ['WORKSHOP_LOGIN_TOKEN','WORKSHOP_E2E_TOKEN','WORKSHOP_E2E_URL']:e2e.pop(k,None)
run(['npm','--prefix','frontend','run','test:e2e','--','--reporter=list,json'],'browser.txt',env=e2e)
stats=json.loads((E/'browser.json').read_text())['stats']; assert stats['expected']==4 and all(stats[k]==0 for k in ('skipped','unexpected','flaky'))
shutil.copy2(R/'evidence/phase3-remediation/browser-scene.png',E/'synthetic-browser-scene.png')
run(['git','restore','--','evidence/phase3-remediation/browser-scene.png'],'restore-generated-browser.txt')
times=json.loads((E/'happy-dom-publication-times.txt').read_text().split('\n',1)[1].rsplit('\nEXIT_CODE:',1)[0])
release=datetime.datetime.fromisoformat(times['21.0.4'].replace('Z','+00:00')); now=datetime.datetime.now(datetime.timezone.utc); eligible=release+datetime.timedelta(days=7)
(E/'quarantine-conflict.json').write_text(json.dumps({'checked_at_utc':now.isoformat(),'installed':'happy-dom@21.0.1','patched':'happy-dom@21.0.4','patched_published_utc':release.isoformat(),'patched_age_days':(now-release).total_seconds()/86400,'quarantine_eligible_utc':eligible.isoformat(),'quarantine_eligible_aedt':eligible.astimezone(datetime.timezone(datetime.timedelta(hours=11))).isoformat(),'eligible_now':now>=eligible,'advisory':'GHSA-834v-8h66-3h79','no_fix_or_override_installed':True},indent=2)+'\n')
print('NON-AUDIT GATES PASS; DEVELOPMENT AUDIT FAIL REMAINS UNRESOLVED',stats,flush=True)
