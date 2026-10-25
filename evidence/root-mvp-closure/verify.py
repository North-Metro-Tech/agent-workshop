"""Pure readback verification of root evidence; no native/Workshop writes."""
from pathlib import Path
import hashlib,json,subprocess,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[2];E=Path(__file__).resolve().parent
BASE='5f7df84da20206a89d87a8ed692dff537edfefc4'
OLD=R.parent/'final-sweep-a87670b9'
SCENARIO_COMMIT='df2ef871a6f45c1c82d65bb055ac500403fce80f'
def git(*args,cwd=R):return subprocess.check_output(['git',*args],cwd=cwd)
def jsonlog(name):return json.loads((E/name).read_text().split('\n',1)[1].rsplit('\nEXIT_CODE:',1)[0])
count=0
for path in git('ls-tree','-r','--name-only',BASE).decode().splitlines():
 if path.startswith('evidence/') or path=='RESUME.md': continue
 assert (R/path).read_bytes()==git('show',BASE+':'+path),path
 count+=1
prior=git('show',BASE+':RESUME.md').decode(); current=(R/'RESUME.md').read_text()
assert current.startswith('# RESUME — Agent Workshop\n\n') and current.endswith(prior.split('\n\n',1)[1])
print('PASS product byte equality (excluding additive RESUME):',count)
# Only this run's locally generated pytest JUnit is parsed; no remote/user XML.
x=ET.parse(E/'backend-junit.xml'); suites=list(x.getroot().iter('testsuite'))
assert sum(int(s.get('tests','0')) for s in suites)==568
assert all(int(s.get(k,'0'))==0 for s in suites for k in ['failures','errors','skipped'])
assert '57 passed (57)' in (E/'frontend-tests.txt').read_text()
stats=json.loads((E/'browser.json').read_text())['stats'];assert stats['expected']==4 and all(stats[k]==0 for k in ['skipped','unexpected','flaky'])
for name in ['frontend-typecheck.txt','frontend-tests.txt','frontend-build.txt','schema-check.txt','clean-install.txt','compile.txt','installed-demo.txt','python-quarantine.txt','npm-quarantine.txt','python-socket-install.txt','npm-socket-install.txt']:
 assert (E/name).read_text().endswith('EXIT_CODE: 0\n'),name
for name in ['demo','collector-demo']:assert (E/(name+'.txt')).read_bytes()==(E/(name+'-repeat.txt')).read_bytes()
print('PASS backend568/frontend57/browser4 zero skips + schema/clean demos/locks')
audit=jsonlog('npm-audit.json.txt');prod=jsonlog('npm-production-audit.json.txt')
assert audit['metadata']['vulnerabilities']['high']==1 and 'happy-dom' in audit['vulnerabilities']
assert prod['metadata']['vulnerabilities']['total']==0
assert (E/'npm-audit.txt').read_text().endswith('EXIT_CODE: 1\n')
q=json.loads((E/'quarantine-conflict.json').read_text());assert q['eligible_now'] is False and q['no_fix_or_override_installed'] is True
print('CONFIRMED BLOCKER: full dev audit high Happy DOM; production audit clean; patch quarantined')
for n in [1,2]:
 d=json.loads((E/f'one-shot-workflow-{n}.json').read_text());assert d['compared_attempts']==42==len(d['comparisons']) and all(c['agrees'] for c in d['comparisons'])
 assert d['source_projection_agreement'] and d['native_fence']['unchanged'] and not d['native_write_enabled']
 assert d['runtime_coverage']=='partial' and d['role_availability']=='unknown'
b=json.loads((E/'browser-report.json').read_text());assert b['result']=='PASS' and b['compared_executions']==42 and b['target_task']=='t_7e8a8223'
assert b['origin']=='https://frankenfarm.taile4f46c.ts.net:10000' and not b['native_write_enabled']
h=json.loads((E/'historian-readback.json').read_text());assert h['result']=='PASS' and len(h['exact_service_revision_checks'])==2 and all(r['all_items_equal_exact_durable_revision'] for r in h['exact_service_revision_checks'])
assert h['native_fence']['unchanged']
assert (E/'live-attempt1/live-browser.txt').read_text().endswith('EXIT_CODE: 1\n')
print('PASS installed HTTPS/native42+42/durable revision; preserved first QA assumption failure')
scenarios={}
for a in [f'A{i:02d}' for i in range(1,11)]+['A23','A25']:
 raw=git('show',SCENARIO_COMMIT+':evidence/'+a+'.txt',cwd=OLD)
 assert b'Candidate: d56e3ccf6f332fd4b578fa47cd2e2a7f24a726d4' in raw and b'Pinning tests:' in raw and b'Scenario result: PASS' in raw
 scenarios[a]=hashlib.sha256(raw).hexdigest()
print('PASS twelve prior signed committed scenario transcripts (historical d56e3ccf, NOT fresh5f7df84)')
if (E/'MANIFEST.json').exists():
 manifest=json.loads((E/'MANIFEST.json').read_text())
 for path,digest in manifest.items():assert hashlib.sha256((E/path).read_bytes()).hexdigest()==digest,path
 print('PASS manifest:',len(manifest))
print('ROOT NOT COMPLETE: Core audit-risk/remedy disposition required')
