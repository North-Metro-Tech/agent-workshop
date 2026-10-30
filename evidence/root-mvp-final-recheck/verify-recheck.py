"""Readback verifier: this checkpoint proves a blocker, NOT MVP acceptance.
Use an existing approved Python interpreter; standard library only. No live writes.
"""
from pathlib import Path
import json, hashlib, subprocess, xml.etree.ElementTree as ET
E=Path(__file__).resolve().parent
R=E.parents[1]
BASE='5f7df84da20206a89d87a8ed692dff537edfefc4'
manifest=json.loads((E/'manifest.json').read_text())
for name,digest in manifest.items():assert hashlib.sha256((E/name).read_bytes()).hexdigest()==digest,name
old=R/'evidence/root-mvp-closure'
for name,digest in json.loads((old/'MANIFEST.json').read_text()).items():assert hashlib.sha256((old/name).read_bytes()).hexdigest()==digest,name
# Only our locally emitted, checksum-pinned pytest JUnit is parsed; no untrusted XML/DTD input.
junit=ET.parse(E/'backend-junit.xml').getroot()
suites=list(junit.iter('testsuite'))
assert sum(int(s.attrib['tests']) for s in suites)==568
assert all(int(s.attrib.get(k,'0'))==0 for s in suites for k in ['failures','errors','skipped'])
assert '57 passed' in (E/'frontend-tests.txt').read_text()
for name in ['frontend-typecheck.txt','frontend-tests.txt','frontend-build.txt','backend-tests.txt','schema-check.txt','demo.txt','demo-repeat.txt','collector-demo.txt','collector-demo-repeat.txt','check.txt','browser.txt']:
 assert (E/name).read_text().endswith('EXIT_CODE: 0\n'),name
stats=json.loads((E/'browser.json').read_text())['stats'];assert stats['expected']==4
assert all(stats[k]==0 for k in ['skipped','unexpected','flaky'])
audit=json.loads((E/'npm-audit.json').read_text());prod=json.loads((E/'npm-production-audit.json').read_text())
assert audit['metadata']['vulnerabilities']['high']==1 and audit['metadata']['vulnerabilities']['total']==1
assert set(audit['vulnerabilities'])=={'happy-dom'} and prod['metadata']['vulnerabilities']['total']==0
assert 'Source/projection disagreement for attempt 42' in (E/'one-shot-workflow-1.json').read_text()
diag=json.loads((E/'agreement-diagnostic.json').read_text())
for label in ['isolated','installed']:
 assert diag[label]['reconcile_required']
 for r in diag[label]['rows']:
  if r['id'] in ['42','44'] and label=='installed' or r['id']=='42' and label=='isolated':
   assert r['current_source']['lifecycle']=='unknown' and r['saved_lifecycle']['mapped']=='active'
   assert r['retained_records'][-1]['attributes']['workshop.lifecycle']=='unknown'
live=json.loads((E/'live-diagnostic-report.json').read_text());assert live['result']=='MISMATCH_REPRODUCED_NOT_MVP_PASS'
assert [r['id'] for r in live['rows'] if not r['agrees']]==['42','44']
assert all(r['quality']=='unknown' for r in live['rows'])
assert not live['native_write_enabled']
durable=json.loads((E/'historian-readback.json').read_text());assert durable['native_fence']['unchanged']
assert all(r['all_items_equal_exact_durable_revision'] and r['original_record_identities_verified'] for r in durable['exact_service_revision_checks'])
assert [r['cursor'] for r in durable['exact_service_revision_checks']]==[live['initial_cursor'],live['final_cursor']]
service=dict(line.split('=',1) for line in (E/'live-service.txt').read_text().splitlines())
assert service['ActiveState']=='active' and service['SubState']=='running' and service['Restart']=='no' and service['NRestarts']=='0' and service['UnitFileState']=='disabled'
old_resume=subprocess.check_output(['git','show','fb56ff612d7533b7882d1549f208a90e0df14392:RESUME.md'],cwd=R)
assert (R/'RESUME.md').read_bytes().endswith(old_resume.split(b'\n',1)[1])
product=[]
for name in subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=R,text=True).splitlines():
 if name.startswith('evidence/') or name=='RESUME.md':continue
 assert (R/name).read_bytes()==subprocess.check_output(['git','show',BASE+':'+name],cwd=R),name
 product.append(name)
print(json.dumps({'status':'BLOCKER_PRESERVED_NOT_MVP_PASS','manifest_files':len(manifest),'unchanged_product_files':len(product),'backend':568,'frontend':57,'browser':stats,'retained_source_mismatches':['42','44'],'durable_http_revisions':[r['cursor'] for r in durable['exact_service_revision_checks']],'original_resume_preserved':True},indent=2))
