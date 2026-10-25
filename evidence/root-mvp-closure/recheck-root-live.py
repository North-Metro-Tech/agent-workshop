"""Retain the overstrict first QA assumption; match the canonical unknown after restart."""
from pathlib import Path
import shutil,subprocess
W=Path(__file__).resolve().parent;R=W/'root-mvp-closure';E=R/'evidence/root-mvp-closure'
A=E/'live-attempt1';A.mkdir()
for name in ['live-browser.txt','live-browser.mjs','browser-snapshot-initial.json','native-fence-before.json']:
 shutil.copy2(E/name,A/name)
p=E/'live-browser.mjs'; s=p.read_text();old="assert.ok(Number.isFinite(Number(ageText))&&Number(ageText)>=0);"
new="""const acquired=selected.facts.find(f=>f.name==='acquired_at')?.value;
 if(acquired==='unknown'){
  // Restart invalidation/reconcile_required is conservative: a fresh transport
  // never certifies execution freshness. Check the EXACT canonical unknown.
  assert.equal(selected.facts.find(f=>f.name==='acquisition_age')?.value,'unknown');
  assert.equal(selected.facts.find(f=>f.name==='lifecycle_quality')?.value,'unknown');
  assert.equal(ageText,'unknown');
 }else assert.ok(Number.isFinite(Number(ageText))&&Number(ageText)>=0);"""
assert s.count(old)==1;p.write_text(s.replace(old,new))
def run(args,name):
 p=subprocess.run(args,cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
 (E/name).write_text('COMMAND: '+repr(args)+'\n'+p.stdout+'\nEXIT_CODE: '+str(p.returncode)+'\n')
 print(name,p.returncode,flush=True);assert p.returncode==0
PY=str(R/'.venv/bin/python')
run([PY,str(E/'verify-installed.py'),'before'],'native-before.txt')
run(['node',str(E/'live-browser.mjs')],'live-browser.txt')
run([PY,str(E/'verify-installed.py')],'historian-readback.txt')
run([PY,str(E/'verify-installed.py'),'sample'],'live-resource-sample.txt')
run(['systemctl','--user','show','agent-workshop-release1.service','-p','ActiveState','-p','SubState','-p','Restart','-p','NRestarts','-p','UnitFileState','-p','ExecMainStartTimestamp'],'live-service.txt')
run(['tailscale','serve','status'],'serve-status.txt')
for label,url in [('loopback','http://127.0.0.1:8765/'),('tailnet','https://frankenfarm.taile4f46c.ts.net:10000/')]:
 run(['curl','--silent','--show-error','--max-time','20','-o','/dev/null','-w','%{http_code}',url],label+'-http.txt')
