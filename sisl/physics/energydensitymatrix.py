from __future__ import print_function, division

from .sparse import SparseOrbitalBZSpin

__all__ = ['EnergyDensityMatrix']


class EnergyDensityMatrix(SparseOrbitalBZSpin):
    """ Sparse energy density matrix object

    Assigning or changing elements is as easy as with standard `numpy` assignments:

    >>> EDM = EnergyDensityMatrix(...) # doctest: +SKIP
    >>> EDM.E[1,2] = 0.1 # doctest: +SKIP

    which assigns 0.1 as the density element between orbital 2 and 3.
    (remember that Python is 0-based elements).

    Parameters
    ----------
    geometry : Geometry
      parent geometry to create a energy density matrix from. The energy density matrix will
      have size equivalent to the number of orbitals in the geometry
    dim : int or Spin, optional
      number of components per element, may be a `Spin` object
    dtype : np.dtype, optional
      data type contained in the energy density matrix. See details of `Spin` for default values.
    nnzpr : int, optional
      number of initially allocated memory per orbital in the energy density matrix.
      For increased performance this should be larger than the actual number of entries
      per orbital.
    spin : Spin, optional
      equivalent to `dim` argument. This keyword-only argument has precedence over `dim`.
    orthogonal : bool, optional
      whether the energy density matrix corresponds to a non-orthogonal basis. In this case
      the dimensionality of the energy density matrix is one more than `dim`.
      This is a keyword-only argument.
    """

    def __init__(self, geometry, dim=1, dtype=None, nnzpr=None, **kwargs):
        super(EnergyDensityMatrix, self).__init__(geometry, dim, dtype, nnzpr, **kwargs)

        self.Ek = self.Pk

    def Ek(self, k=(0, 0, 0), dtype=None, gauge='R', format='csr', *args, **kwargs):
        r""" Setup the energy density matrix for a given k-point

        Creation and return of the density matrix for a given k-point (default to Gamma).

        Notes
        -----

        Currently the implemented gauge for the k-point is the cell vector gauge:

        .. math::
          E(k) = E_{\nu\mu} e^{i k R}

        where :math:`R` is an integer times the cell vector and :math:`\nu`, :math:`\mu` are orbital indices.

        Another possible gauge is the orbital distance which can be written as

        .. math::
          E(k) = E_{\nu\mu} e^{i k r}

        where :math:`r` is the distance between the orbitals :math:`\nu` and :math:`\mu`.
        Currently the second gauge is not implemented (yet).

        Parameters
        ----------
        k : array_like
           the k-point to setup the energy density matrix at
        dtype : numpy.dtype , optional
           the data type of the returned matrix. Do NOT request non-complex
           data-type for non-Gamma k.
           The default data-type is `numpy.complex128`
        gauge : {'R', 'r'}
           the chosen gauge, `R` for cell vector gauge, and `r` for orbital distance
           gauge.
        format : {'csr', 'array', 'dense', 'coo', ...}
           the returned format of the matrix, defaulting to the ``scipy.sparse.csr_matrix``,
           however if one always requires operations on dense matrices, one can always
           return in `numpy.ndarray` (`'array'`) or `numpy.matrix` (`'dense'`).
        spin : int, optional
           if the energy density matrix is a spin polarized one can extract the specific spin direction
           matrix by passing an integer (0 or 1). If the energy density matrix is not `Spin.POLARIZED`
           this keyword is ignored.
        """
        pass

    def _get_E(self):
        self._def_dim = self.UP
        return self

    def _set_E(self, key, value):
        if len(key) == 2:
            self._def_dim = self.UP
        self[key] = value

    E = property(_get_E, _set_E)

    @staticmethod
    def read(sile, *args, **kwargs):
        """ Reads density matrix from `Sile` using `read_energy_density_matrix`.

        Parameters
        ----------
        sile : `Sile`, str
            a `Sile` object which will be used to read the density matrix
            and the overlap matrix (if any)
            if it is a string it will create a new sile using `get_sile`.
        * : args passed directly to ``read_energy_density_matrix(,**)``
        """
        # This only works because, they *must*
        # have been imported previously
        from sisl.io import get_sile, BaseSile
        if isinstance(sile, BaseSile):
            return sile.read_energy_density_matrix(*args, **kwargs)
        else:
            with get_sile(sile) as fh:
                return fh.read_energy_density_matrix(*args, **kwargs)

    def write(self, sile, *args, **kwargs):
        """ Writes a density matrix to the `Sile` as implemented in the :code:`Sile.write_energy_density_matrix` method """
        # This only works because, they *must*
        # have been imported previously
        from sisl.io import get_sile, BaseSile
        if isinstance(sile, BaseSile):
            sile.write_energy_density_matrix(self, *args, **kwargs)
        else:
            with get_sile(sile, 'w') as fh:
                fh.write_energy_density_matrix(self, *args, **kwargs)
