from __future__ import print_function, division

from nose.tools import *

from sids import SuperCell

import math as m
import numpy as np


class TestSuperCell(object):

    def setUp(self):
        alat = 1.42
        sq3h  = 3.**.5 * 0.5
        self.sc = SuperCell(np.array([[1.5, sq3h,  0.],
                                      [1.5,-sq3h,  0.],
                                      [ 0.,   0., 10.]],np.float64) * alat, nsc=[3,3,1])


    def tearDown(self):
        del self.sc

    def test_nsc1(self):
        nsc = np.copy(self.sc.nsc)
        self.sc.set_nsc([5,5,0])
        assert_true( np.allclose([5,5,1],self.sc.nsc) )
        assert_true( len(self.sc.sc_off) == np.prod(self.sc.nsc) )

    def test_nsc2(self):
        nsc = np.copy(self.sc.nsc)
        self.sc.set_nsc([0,1,0])
        assert_true( np.allclose([1,1,1],self.sc.nsc) )
        assert_true( len(self.sc.sc_off) == np.prod(self.sc.nsc) )

    def test_rotation1(self):
        rot = self.sc.rotate(m.pi,[0,0,1])
        rot.cell[2,2] *= -1
        assert_true( np.allclose(-rot.cell,self.sc.cell) )

        rot = rot.rotate(m.pi,[0,0,1])
        rot.cell[2,2] *= -1
        assert_true( np.allclose(rot.cell,self.sc.cell) )

    def test_swapaxes1(self):
        sab = self.sc.swapaxes(0,1)
        assert_true( np.allclose(sab.cell[0,:],self.sc.cell[1,:]) )
        assert_true( np.allclose(sab.cell[1,:],self.sc.cell[0,:]) )

    def test_swapaxes2(self):
        sab = self.sc.swapaxes(0,2)
        assert_true( np.allclose(sab.cell[0,:],self.sc.cell[2,:]) )
        assert_true( np.allclose(sab.cell[2,:],self.sc.cell[0,:]) )

    def test_swapaxes3(self):
        sab = self.sc.swapaxes(1,2)
        assert_true( np.allclose(sab.cell[1,:],self.sc.cell[2,:]) )
        assert_true( np.allclose(sab.cell[2,:],self.sc.cell[1,:]) )

    def test_cut1(self):
        cut = self.sc.cut(2,0)
        assert_true( np.allclose(cut.cell[0,:]*2,self.sc.cell[0,:]) )
        assert_true( np.allclose(cut.cell[1,:],self.sc.cell[1,:]) )

    def test_creation(self):
        # full cell
        tmp1 = SuperCell([[1,0,0],[0,1,0],[0,0,1]])
        # diagonal cell
        tmp2 = SuperCell([1,1,1])
        # cell parameters
        tmp3 = SuperCell([1,1,1,90,90,90])
        tmp4 = SuperCell([1])
        assert_true( np.allclose(tmp1.cell,tmp2.cell) )
        assert_true( np.allclose(tmp1.cell,tmp3.cell) )
        assert_true( np.allclose(tmp1.cell,tmp4.cell) )



