from __future__ import print_function, division

import pytest

from sisl.io.siesta.xv import *

import numpy as np

pytestmark = [pytest.mark.io, pytest.mark.siesta]
_dir = 'sisl/io/siesta'


def test_xv1(sisl_tmp, sisl_system):
    f = sisl_tmp('gr.XV', _dir)
    sisl_system.g.write(xvSileSiesta(f, 'w'))
    g = xvSileSiesta(f).read_geometry()

    # Assert they are the same
    assert np.allclose(g.cell, sisl_system.g.cell)
    assert np.allclose(g.xyz, sisl_system.g.xyz)
    assert sisl_system.g.atom.equal(g.atom, R=False)
