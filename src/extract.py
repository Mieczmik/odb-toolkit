# -*- coding: utf-8 -*-
"""
extract.py -- Abaqus Python 2 script.
Reads field outputs from ODB (all steps, frames, instances).
Dumps to JSON keyed by "StepName|frameIdx|InstanceName".

Usage (called by main.py):
    abaqus python src/extract.py <runtime.json>
"""

import sys
import json
from odbAccess import openOdb
from abaqusConstants import NODAL


def main():
    with open(sys.argv[1], 'r') as f:
        cfg = json.load(f)

    requested = cfg.get('sources', None)  # None or "ALL" = all fields

    odb = openOdb(str(cfg['odb_path']), readOnly=True)
    try:
        instances = odb.rootAssembly.instances.keys()
        result = {}

        # Export mesh data (nodes + connectivity) per instance
        mesh = {}
        for inst_name in instances:
            inst = odb.rootAssembly.instances[inst_name]
            nodes = {}
            for n in inst.nodes:
                nodes[n.label] = [float(c) for c in n.coordinates]
            elements = {}
            for e in inst.elements:
                elements[e.label] = {
                    'connectivity': list(e.connectivity),
                    'type': str(e.type),
                }
            mesh[inst_name] = {'nodes': nodes, 'elements': elements}
            print("[extract] mesh %s: %d nodes, %d elements" % (
                inst_name, len(nodes), len(elements)))

        mesh_path = str(cfg['extracted_path']).replace('extracted.json', 'mesh.json')
        with open(mesh_path, 'w') as f:
            json.dump(mesh, f)

        for step_name in odb.steps.keys():
            step = odb.steps[step_name]
            for frame_idx, frame in enumerate(step.frames):

                available = frame.fieldOutputs.keys()
                if not available:
                    continue

                if requested is None or requested == "ALL":
                    sources = list(available)
                else:
                    sources = [str(s) for s in requested if s in available]
                if not sources:
                    continue

                for inst_name in instances:
                    key = "%s|%d|%s" % (step_name, frame_idx, inst_name)

                    frame_data = {}
                    for src in sources:
                        field = frame.fieldOutputs[src]

                        # Detect nodal vs element position
                        is_nodal = False
                        if field.locations:
                            is_nodal = (field.locations[0].position == NODAL)

                        labels = []
                        data = []
                        for v in field.values:
                            if v.instance is not None and v.instance.name != inst_name:
                                continue

                            lbl = v.nodeLabel if is_nodal else v.elementLabel
                            if lbl is None:
                                continue

                            labels.append(lbl)
                            try:
                                data.append([float(x) for x in v.data])
                            except TypeError:
                                data.append([float(v.data)])

                        # Average multiple integration points per element
                        if labels and not is_nodal:
                            from collections import defaultdict
                            accum = defaultdict(list)
                            for lbl, row in zip(labels, data):
                                accum[lbl].append(row)
                            labels = []
                            data = []
                            for lbl in sorted(accum.keys()):
                                rows = accum[lbl]
                                n_comp = len(rows[0])
                                avg = [sum(r[c] for r in rows) / len(rows)
                                       for c in range(n_comp)]
                                labels.append(lbl)
                                data.append(avg)

                        if labels:
                            frame_data[str(src)] = {
                                'labels': labels,
                                'data': data,
                                'position': 'nodal' if is_nodal else 'element',
                            }

                    if not frame_data:
                        continue

                    result[key] = frame_data
                    print("[extract] %s: %s" % (key, list(frame_data.keys())))

        with open(str(cfg['extracted_path']), 'w') as f:
            json.dump(result, f)

    finally:
        odb.close()

    print("[extract] Done -> %s (%d entries)" % (cfg['extracted_path'], len(result)))


if __name__ == '__main__':
    main()