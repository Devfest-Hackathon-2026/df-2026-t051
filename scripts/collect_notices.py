"""Collect installed distribution license notices without importing application secrets."""
import importlib.metadata as metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sections = []
for dist in sorted(metadata.distributions(), key=lambda d: d.metadata['Name'].lower()):
    if dist.metadata['Name'] == 'pip':
        continue
    for file in dist.files or []:
        if any(term in file.name.lower() for term in ('license', 'notice', 'copying')) and file.suffix.lower() not in {'.py', '.pyc'}:
            path = Path(dist.locate_file(file))
            if path.is_file():
                sections.append(f"\n=== {dist.metadata['Name']} {dist.version} / {file.name} ===\n" + path.read_text(encoding='utf-8', errors='replace'))

for package in sorted((ROOT / 'frontend/node_modules/.pnpm').glob('*/node_modules/*')):
    candidates = list(package.iterdir()) if package.name.startswith('@') and package.is_dir() else [package]
    for candidate in candidates:
        if not candidate.is_dir() or candidate.is_symlink():
            continue
        for file in sorted(candidate.iterdir()):
            if file.is_file() and any(file.name.lower().startswith(term) for term in ('license', 'notice', 'copying')):
                sections.append(f"\n=== {candidate.name} / {file.name} ===\n" + file.read_text(encoding='utf-8', errors='replace'))

(ROOT / 'docs/third-party-notices.txt').write_text('\n'.join(sections), encoding='utf-8')
print(f'Collected {len(sections)} notices')
