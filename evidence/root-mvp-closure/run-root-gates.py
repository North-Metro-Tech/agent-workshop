"""Final QA only. No product edits, no native writes, no service changes."""
from pathlib import Path
import subprocess,os,json,shutil
W=Path(__file__).resolve().parent
R=W/'root-mvp-closure'
E=R/'evidence/root-mvp-closure'; E.mkdir(parents=True,exist_ok=True)
PY='/home/aaron/hermes-agent/.venv/bin/python'
HEAD='5f7df84da20206a89d87a8ed692dff537edfefc4'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==HEAD
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=R,text=True)
def run(args,name,cwd=R,env=None,timeout=300):
 with (E/name).open('w') as f:
  f.write('COMMAND: '+repr(args)+'\n');f.flush()
  try:
   p=subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  except subprocess.TimeoutExpired:
   f.write('\nTIMEOUT; NOT A PASS\n'); raise
  f.write('\nEXIT_CODE: '+str(p.returncode)+'\n')
 print(name,p.returncode,flush=True)
 assert p.returncode==0,name
run(['git','status','--porcelain'],'initial-clean-checkout.txt')
run([PY,'scripts/check_python_lock.py','--output',str(E/'python-quarantine.json')],'python-quarantine.txt')
run([PY,'scripts/check_npm_quarantine.py'],'npm-quarantine.txt')
shutil.copy2(R/'evidence/phase3-npm-quarantine.json',E/'npm-quarantine.json')
run(['git','restore','evidence/phase3-npm-quarantine.json'],'restore-quarantine.txt')
run([PY,'scripts/dev.py','install'],'clean-install.txt')
run(['sfw','uv','pip','install','--python','.venv/bin/python','--require-hashes','--only-binary',':all:','--exclude-newer','2026-10-15T00:00:00Z','-r','requirements.lock'],'python-socket-install.txt')
run(['sfw','npm','ci','--include=dev','--ignore-scripts'],'npm-socket-install.txt',R/'frontend')
run(['sfw','npm','audit','--include=dev'],'npm-audit.txt',R/'frontend')
run(['npm','--prefix','frontend','run','typecheck'],'frontend-typecheck.txt')
run(['npm','--prefix','frontend','run','test','--','--run'],'frontend-tests.txt')
run(['npm','--prefix','frontend','run','build'],'frontend-build.txt')
env=dict(os.environ,PYTHONPATH=str(R/'.venv/lib/python3.11/site-packages')+':'+str(R/'backend')+':'+str(R/'collectors'),PYTHONDONTWRITEBYTECODE='1')
run([PY,'-m','pytest','-q','--junitxml='+str(E/'backend-junit.xml')],'backend-tests.txt',env=env)
run([str(R/'.venv/bin/python'),'scripts/dev.py','schema','--check'],'schema-check.txt')
for command,name in [('demo','demo'),('collector-demo','collector-demo'),('check','compile')]:
 run([PY,'scripts/dev.py',command],name+'.txt')
 if command!='check': run([PY,'scripts/dev.py',command],name+'-repeat.txt')
for name in ['demo','collector-demo']:
 assert (E/(name+'.txt')).read_bytes()==(E/(name+'-repeat.txt')).read_bytes(),name
run([str(R/'.venv/bin/python'),'-m','workshop.demo'],'installed-demo.txt',env=dict(os.environ,PYTHONPATH=''))
print('CLEAN EXACT-HEAD BACKEND/FRONTEND/DEMO GATES PASS',flush=True)
