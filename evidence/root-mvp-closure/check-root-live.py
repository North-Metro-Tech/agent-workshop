"""Bounded approved-source verification only; do not change or restart the service."""
from pathlib import Path
import subprocess,os,json
W=Path(__file__).resolve().parent;R=W/'root-mvp-closure';E=R/'evidence/root-mvp-closure'; OLD=W/'final-sweep-a87670b9/evidence/final-mvp-sweep'
PY=str(R/'.venv/bin/python')
def run(args,name,timeout=120,raw=False):
 p=subprocess.run(args,cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
 (E/name).write_text(p.stdout if raw else 'COMMAND: '+repr(args)+'\n'+p.stdout+'\nEXIT_CODE: '+str(p.returncode)+'\n')
 print(name,p.returncode,flush=True);assert p.returncode==0,name
 return p.stdout
for n in (1,2):
 d=json.loads(run([PY,'scripts/observe_workflow.py','--approved-local'],f'one-shot-workflow-{n}.json',raw=True))
 assert d['source_projection_agreement'] and d['native_fence']['unchanged'] and all(c['agrees'] for c in d['comparisons'])
 assert d['runtime_coverage']=='partial' and d['role_availability']=='unknown' and not d['native_write_enabled']
s=(OLD/'live-browser.mjs').read_text().replace(str(W/'final-sweep-a87670b9'),str(R)).replace('t_a87670b9','t_7e8a8223').replace("const origin='http://127.0.0.1:8765';","const origin='https://frankenfarm.taile4f46c.ts.net:10000';")
(E/'live-browser.mjs').write_text(s)
(E/'verify-installed.py').write_text((OLD/'verify-installed.py').read_text())
run([PY,str(E/'verify-installed.py'),'before'],'native-before.txt')
run(['node',str(E/'live-browser.mjs')],'live-browser.txt')
run([PY,str(E/'verify-installed.py')],'historian-readback.txt')
run([PY,str(E/'verify-installed.py'),'sample'],'live-resource-sample.txt')
run(['systemctl','--user','show','agent-workshop-release1.service','-p','ActiveState','-p','SubState','-p','Restart','-p','NRestarts','-p','UnitFileState','-p','ExecMainStartTimestamp'],'live-service.txt')
run(['tailscale','serve','status'],'serve-status.txt')
for label,url in [('loopback','http://127.0.0.1:8765/'),('tailnet','https://frankenfarm.taile4f46c.ts.net:10000/')]:
 out=run(['curl','--silent','--show-error','--max-time','20','-o','/dev/null','-w','%{http_code}',url],label+'-http.txt');assert out=='200'
print('LIVE TAILNET/FLEET/EXACT DURABLE READBACK PASS; NO MVP OR AUDIT WAIVER')
