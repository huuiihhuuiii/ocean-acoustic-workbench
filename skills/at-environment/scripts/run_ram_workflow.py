"""Run the staged RAM input and preserve TL without inventing pressure phase."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import numpy as np

folder = Path(__file__).resolve().parent
workflow = json.loads((folder / 'workflow.json').read_text(encoding='utf-8'))
for name in ['tl.grid', 'tl.line']:
    (folder / name).unlink(missing_ok=True)
result = subprocess.run([workflow['ram_executable']], cwd=folder,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
result.check_returncode()
spec = importlib.util.spec_from_file_location('ram_reader', folder / 'read_ram_grid.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
summary = reader.export(folder / 'tl.grid', folder)
data = reader.read_grid(folder / 'tl.grid')
r, z = np.meshgrid(data['ranges_m'], data['depths_m'])
np.savetxt(folder / 'field_slice.csv', np.column_stack([r.ravel(), z.ravel(), data['tl_db'].ravel()]),
           delimiter=',', header='range_m,receiver_depth_m,tl_db', comments='')
summary.update(model='RAM', source_axis='range_depth', phase_available=False,
               scope='Execution and TL structure checked; no convergence or physical accuracy certificate')
(folder / 'model_metrics.json').write_text(json.dumps(summary, indent=2, allow_nan=False), encoding='utf-8')
print('MODEL_WORKFLOW_OUTPUT_CHECKED', flush=True)
