import math


def von_mises(f):
    """Von Mises from full stress tensor (3D, 6 components)."""
    d = f['S']
    s11, s22, s33, s12, s13, s23 = d[0], d[1], d[2], d[3], d[4], d[5]
    return math.sqrt(
        0.5 * ((s11 - s22)**2 + (s22 - s33)**2 + (s33 - s11)**2
               + 6.0 * (s12**2 + s13**2 + s23**2))
    )
    
def s11(f):
    """S11 component of stress tensor."""
    d = f['S']
    return d[0]


def u1(f):
    """U1 component of displacement vector."""
    d = f['U']
    return d[0]


def stress_disp_product(f):
    """Von Mises * displacement magnitude -- mixes element S and nodal U.
    U is automatically averaged over element nodes by compute.py."""
    d = f['S']
    u = f['U']
    s11, s22, s33, s12, s13, s23 = d[0], d[1], d[2], d[3], d[4], d[5]
    mises = math.sqrt(
        0.5 * ((s11 - s22)**2 + (s22 - s33)**2 + (s33 - s11)**2
               + 6.0 * (s12**2 + s13**2 + s23**2))
    )
    u_mag = math.sqrt(sum(ui**2 for ui in u))
    return mises * u_mag

def s11_normalized(f, lookups=None, mesh=None, label=None):
    """S11 normalized by mean S11 across elements at similar X coordinate.

    Groups elements into 1mm-wide bins by centroid X,
    computes mean S11 per bin, returns S11 / bin_mean.
    """
    if not mesh or not lookups or label is None:
        return f['S'][0]

    nodes = mesh.get('nodes', {})
    elements = mesh.get('elements', {})
    s_lookup = lookups.get('S', {})

    # Centroid X of current element
    conn = elements.get(str(label), {}).get('connectivity', [])
    my_x = sum(nodes[str(n)][0] for n in conn if str(n) in nodes) / max(len(conn), 1)
    bin_key = round(my_x, 0)

    # Mean S11 across elements in the same X bin
    total = 0.0
    count = 0
    for el_id, el_info in elements.items():
        el_int = int(el_id)
        if el_int not in s_lookup:
            continue
        c = el_info['connectivity']
        cx = sum(nodes[str(n)][0] for n in c if str(n) in nodes) / max(len(c), 1)
        if round(cx, 0) == bin_key:
            total += s_lookup[el_int][0]
            count += 1

    slice_mean = total / count if count > 0 else 1.0
    return f['S'][0] / slice_mean if slice_mean != 0 else 0.0

def s11_normalized_with_cache(bin_size=1.0, axis=0):
    cache = {}

    def func(f, lookups=None, mesh=None, label=None):
        if not mesh or not lookups or label is None:
            return f['S'][0]

        cache_key = id(lookups)
        if cache_key not in cache:
            from collections import defaultdict
            nodes = mesh['nodes']
            elements = mesh['elements']
            s_lookup = lookups['S']

            bins = defaultdict(list)
            el_to_bin = {}
            for el_id, el_info in elements.items():
                el_int = int(el_id)
                if el_int not in s_lookup:
                    continue
                conn = el_info['connectivity']
                cx = sum(nodes[str(n)][axis] for n in conn) / len(conn)
                bk = round(cx / bin_size) * bin_size
                bins[bk].append(s_lookup[el_int][0])
                el_to_bin[el_int] = bk

            means = {}
            for bk, vals in bins.items():
                means[bk] = sum(vals) / len(vals)

            cache[cache_key] = {el: means[bk] for el, bk in el_to_bin.items()}

        mean = cache[cache_key].get(label, 1.0)
        return f['S'][0] / mean if mean != 0 else 0.0

    return func


FIELD_DEFS = [
    {
        'name': 'MY_VONMISES',
        'description': 'Custom von Mises stress',
        'sources': ['S'],
        'position': 'element',
        'func': von_mises,
    },
    {
        'name': 'STRESS_X_DISP',
        'description': 'Von Mises * displacement magnitude (cross-position)',
        'sources': ['S', 'U'],
        'position': 'element',
        'func': stress_disp_product,
    },
    {
        'name': 'MY_S11',
        'description': 'S11 component of stress tensor',
        'sources': ['S'],
        'position': 'element',
        'func': s11,
    },
    {
        'name': 'MY_U1',
        'description': 'U1 component of displacement vector',
        'sources': ['U'],
        'position': 'nodal',
        'func': u1,
    },
    {
        'name': 'S11_NORMALIZED',
        'description': 'S11 / mean S11 in X-slice',
        'sources': ['S'],
        'position': 'element',
        'global': True,
        'func': s11_normalized_with_cache(bin_size=1.0),
    },
]