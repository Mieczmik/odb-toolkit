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


FIELD_DEFS = [
    {
        'name': 'MY_VONMISES',
        'description': 'Custom von Mises stress',
        'sources': ['S'],
        'position': 'element', # DEFAULT: 'element' if any(pos == 'element' for pos in positions.values()) else 'nodal' in compute.py
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
]