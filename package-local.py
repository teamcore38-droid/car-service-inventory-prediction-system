"""Create a portable source/model package without local data or credentials."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root=Path(__file__).resolve().parent
destination=root.parent/'Smart-Vehicle-Integrated.zip'
excluded={'node_modules','.venv','.runtime','.local-data','.git','__pycache__','dist','.expo'}
with ZipFile(destination,'w',ZIP_DEFLATED) as archive:
    for path in sorted(root.rglob('*')):
        relative=path.relative_to(root)
        if not path.is_file() or excluded.intersection(relative.parts):continue
        if path.name.startswith('.env') and path.name not in ('.env.example','.env.sample'):continue
        if path.suffix in ('.zip','.pyc') or path.name in ('.DS_Store','Thumbs.db'):continue
        archive.write(path,Path(root.name)/relative)
with ZipFile(destination) as archive:
    assert archive.testzip() is None
    assert not any(excluded.intersection(Path(name).parts) for name in archive.namelist())
    for required in ('RUN_LOCAL.md','Start-System.cmd','setup.ps1','inventory-ml/artifacts/daily_model.joblib','inventory-ml/Inventory_Daily_Training.ipynb','backend/package-lock.json','admin-web/package-lock.json'):
        assert f'{root.name}/{required}' in archive.namelist(),required
    print(f'Validated {len(archive.namelist())} files: {destination} ({destination.stat().st_size/1048576:.2f} MB)')
