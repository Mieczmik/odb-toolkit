"""
compute.py -- Python 3 script.
Loads extracted field data, applies field_defs functions,
writes results JSON keyed by step|frame_idx|instance.

Usage (called by main.py):
    python src/compute.py <runtime.json>
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from field_defs import FIELD_DEFS


def compute_frame(frame_data: dict, mesh: dict | None = None) -> list[dict]:
    lookups = {}
    positions = {}
    for src, payload in frame_data.items():
        lookups[src] = dict(zip(payload['labels'], payload['data']))
        positions[src] = payload.get('position', 'element')

    # Build nodal-to-element averaging helper if mesh available
    nodal_to_element = {}
    if mesh:
        elements = mesh.get('elements', {})
        for el_label, el_info in elements.items():
            el_key = int(el_label)
            nodal_to_element[el_key] = [int(n) for n in el_info['connectivity']]

    results = []
    for fdef in FIELD_DEFS:
        if not all(s in lookups for s in fdef['sources']):
            continue

        # Determine output position
        auto_pos = 'element' if any(positions[s] == 'element' for s in fdef['sources']) else 'nodal'
        out_pos = fdef.get('position', auto_pos)
 
        if out_pos != auto_pos:
            print(f"[compute] WARNING: '{fdef['name']}' requested position='{out_pos}' "
                  f"but sources suggest '{auto_pos}'. Using '{auto_pos}'.")
            out_pos = auto_pos
 
        if out_pos == 'element':
            el_sources = [s for s in fdef['sources'] if positions[s] == 'element']
            if el_sources:
                key_sets = [set(lookups[s].keys()) for s in el_sources]
                base_labels = sorted(key_sets[0].intersection(*key_sets[1:]))
            else:
                continue
        else:
            nod_sources = [s for s in fdef['sources'] if positions[s] == 'nodal']
            if nod_sources:
                key_sets = [set(lookups[s].keys()) for s in nod_sources]
                base_labels = sorted(key_sets[0].intersection(*key_sets[1:]))
            else:
                continue

        if not base_labels:
            continue

        labels = []
        values = []
        for el in base_labels:
            fields_dict = {}
            skip = False
            for s in fdef['sources']:
                if positions[s] == out_pos or positions[s] == positions.get(fdef['sources'][0], 'element'):
                    # Same position -- direct lookup
                    if el in lookups[s]:
                        fields_dict[s] = lookups[s][el]
                    else:
                        skip = True
                        break
                elif positions[s] == 'nodal' and out_pos == 'element' and nodal_to_element:
                    # Average nodal field over element's nodes
                    conn = nodal_to_element.get(el, [])
                    node_vals = [lookups[s][n] for n in conn if n in lookups[s]]
                    if not node_vals:
                        skip = True
                        break
                    # Component-wise average
                    n_comp = len(node_vals[0])
                    avg = [sum(v[c] for v in node_vals) / len(node_vals) for c in range(n_comp)]
                    fields_dict[s] = avg
                else:
                    skip = True
                    break

            if skip:
                continue

            values.append(fdef['func'](fields_dict))
            labels.append(el)

        if not labels:
            continue

        results.append({
            'name': fdef['name'],
            'description': fdef['description'],
            'labels': labels,
            'values': values,
            'position': out_pos,
        })

    return results


def main():
    with open(sys.argv[1]) as f:
        cfg = json.load(f)

    with open(cfg['extracted_path']) as f:
        raw = json.load(f)

    # Load mesh if available
    mesh_path = Path(cfg['extracted_path']).parent / "mesh.json"
    mesh_data = {}
    if mesh_path.exists():
        with open(mesh_path) as f:
            mesh_data = json.load(f)

    all_results = {}
    for frame_key, frame_data in raw.items():
        # Parse instance name from key for mesh lookup
        inst_name = frame_key.split('|')[2]
        mesh = mesh_data.get(inst_name)

        computed = compute_frame(frame_data, mesh=mesh)
        if computed:
            all_results[frame_key] = computed
            names = [c['name'] for c in computed]
            print(f"[compute] {frame_key}: {names}")

    with open(cfg['results_path'], 'w') as f:
        json.dump(all_results, f)

    print(f"[compute] Done -> {cfg['results_path']} ({len(all_results)} frames)")


if __name__ == '__main__':
    main()