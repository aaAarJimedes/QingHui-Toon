"""Build only distributable original add-on files; no scene or third-party data."""
import argparse, ast, hashlib, json, zipfile
from pathlib import Path
root = Path(__file__).resolve().parents[1]
package = root / 'qinghui_toon'
tree = ast.parse((package / '__init__.py').read_text(encoding='utf8'))
info = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'bl_info' for t in n.targets))
version = '.'.join(map(str, info['version']))
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=root / 'dist')
out = parser.parse_args().output.resolve(); out.mkdir(parents=True, exist_ok=True)
files = sorted(p for p in package.iterdir() if p.is_file() and (p.suffix in {'.py', '.md'} or p.name == 'LICENSE.txt'))
assert len([p for p in files if p.suffix == '.py']) == 6
hashes = {}
archive = out / f'qinghui_toon-{version}.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for p in files:
        body = p.read_bytes(); name = 'qinghui_toon/' + p.name
        entry = zipfile.ZipInfo(name, (2026, 10, 9, 0, 0, 0)); entry.compress_type = zipfile.ZIP_DEFLATED; entry.external_attr = 0o100644 << 16
        z.writestr(entry, body); hashes[name] = hashlib.sha256(body).hexdigest()
with zipfile.ZipFile(archive) as z: assert z.testzip() is None
record = {'version': version, 'archive': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'files': hashes}
manifest = out / f'build-manifest-{version}.json'
manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
checksum = out / f'SHA256SUMS-{version}.txt'
checksum.write_text('\n'.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}' for p in (archive, manifest)) + '\n', encoding='utf8')
print(json.dumps({'version': version, 'files': len(files), 'sha256': record['sha256']}))
