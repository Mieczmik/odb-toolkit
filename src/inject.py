# -*- coding: utf-8 -*-
"""
inject.py -- Abaqus Python 2 script.
Reads computed results JSON and creates FieldOutput entries in ODB.

Usage (called by main.py):
    abaqus python src/inject.py <runtime.json>
"""

import sys
import json
from odbAccess import openOdb
from abaqusConstants import INTEGRATION_POINT, NODAL, SCALAR


def main():
    with open(sys.argv[1], 'r') as f:
        cfg = json.load(f)

    with open(str(cfg['results_path']), 'r') as f:
        all_results = json.load(f)

    if not all_results:
        print("[inject] Nothing to inject.")
        return

    odb = openOdb(str(cfg['odb_path']), readOnly=False)
    try:
        count = 0
        for frame_key, entries in all_results.items():
            parts = frame_key.split('|')
            step_name = str(parts[0])
            frame_idx = int(parts[1])
            inst_name = str(parts[2])

            frame = odb.steps[step_name].frames[frame_idx]
            instance = odb.rootAssembly.instances[inst_name]

            for entry in entries:
                name = str(entry['name'])
                pos = NODAL if entry.get('position') == 'nodal' else INTEGRATION_POINT

                # Reuse existing FieldOutput if created for another instance
                if name in frame.fieldOutputs:
                    fo = frame.fieldOutputs[name]
                else:
                    fo = frame.FieldOutput(
                        name=name,
                        description=str(entry['description']),
                        type=SCALAR,
                    )
                fo.addData(
                    position=pos,
                    instance=instance,
                    labels=entry['labels'],
                    data=[[v] for v in entry['values']],
                )
                count += 1

            print("[inject] %s: %d fields" % (frame_key, len(entries)))

        odb.save()
    finally:
        odb.close()

    print("[inject] ODB updated: %s (%d writes)" % (cfg['odb_path'], count))


if __name__ == '__main__':
    main()