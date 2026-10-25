"""Record corruption, byte order and depth-origin tests independent of solver output."""
import importlib.util,struct,tempfile
from pathlib import Path
import numpy as np
spec=importlib.util.spec_from_file_location('ram',Path(__file__).resolve().parents[1]/'skills/at-environment/scripts/read_ram_grid.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with tempfile.TemporaryDirectory() as tmp:
    for endian in ('<','>'):
        payload=struct.pack(endian+'5fi2fi2f2ifi',25.,100.,1.,3.,1.,1,1000.,1.,2,4.,1500.,1,1,6.,2)
        def record(raw):return struct.pack(endian+'i',len(raw))+raw+struct.pack(endian+'i',len(raw))
        raw=record(payload)+b''.join(record(struct.pack(endian+'2f',10.+i,20.+i)) for i in range(3));p=Path(tmp)/'tl.grid';p.write_bytes(raw);d=m.read_grid(p)
        assert np.array_equal(d['depths_m'],[1.,3.]) and np.array_equal(d['ranges_m'],[1.,2.,3.])
        assert np.array_equal(d['tl_db'],[[10,11,12],[20,21,22]])
        for corrupted in [raw[:-1],raw[:68]+struct.pack(endian+'i',999)+raw[72:]]:
            p.write_bytes(corrupted)
            try:m.read_grid(p);raise AssertionError('Corrupt RAM record accepted')
            except ValueError:pass
print('PASS: RAM little/big endian, correct sample ordering/depth origin, truncated and corrupt records rejected')
