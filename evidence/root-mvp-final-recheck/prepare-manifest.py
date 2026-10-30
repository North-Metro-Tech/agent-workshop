"""Generate deterministic local evidence hashes; reject private login content."""
from pathlib import Path
import hashlib,json
p=Path(__file__).resolve().parent
secret=Path('/home/aaron/.local/share/agent-workshop/release1/state-schema2/approved-local/login-secret').read_text().strip().encode()
files=sorted(f for f in p.rglob('*') if f.is_file() and f.name not in ['manifest.json','verification-readback.txt'])
assert all(secret not in f.read_bytes() for f in files)
(p/'manifest.json').write_text(json.dumps({str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},indent=2)+'\n')
print('manifest files',len(files),'private-login exclusion PASS')
