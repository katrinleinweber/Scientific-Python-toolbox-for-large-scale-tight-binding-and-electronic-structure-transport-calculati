from __future__ import print_function, division

from numbers import Integral
from scipy.sparse import csr_matrix, triu, tril
from scipy.sparse import hstack as ss_hstack
import numpy as np
from numpy import dot, unique

from sisl.geometry import Geometry
from sisl.supercell import SuperCell
import sisl._array as _a
from sisl._indices import indices_le, indices_fabs_le
from sisl._math_small import xyz_to_spherical_cos_phi
from sisl.messages import warn, tqdm_eta
from sisl._help import _zip as zip, _range as range
from sisl.utils.ranges import array_arange
from .spin import Spin
from sisl.sparse import SparseCSR
from sisl.sparse_geometry import SparseOrbital
from .sparse import SparseOrbitalBZSpin

__all__ = ['DensityMatrix']


class DensityMatrix(SparseOrbitalBZSpin):
    """ Sparse density matrix object

    Assigning or changing elements is as easy as with standard `numpy` assignments:

    >>> DM = DensityMatrix(...) # doctest: +SKIP
    >>> DM.D[1,2] = 0.1 # doctest: +SKIP

    which assigns 0.1 as the density element between orbital 2 and 3.
    (remember that Python is 0-based elements).

    Parameters
    ----------
    geometry : Geometry
      parent geometry to create a density matrix from. The density matrix will
      have size equivalent to the number of orbitals in the geometry
    dim : int or Spin, optional
      number of components per element, may be a `Spin` object
    dtype : np.dtype, optional
      data type contained in the density matrix. See details of `Spin` for default values.
    nnzpr : int, optional
      number of initially allocated memory per orbital in the density matrix.
      For increased performance this should be larger than the actual number of entries
      per orbital.
    spin : Spin, optional
      equivalent to `dim` argument. This keyword-only argument has precedence over `dim`.
    orthogonal : bool, optional
      whether the density matrix corresponds to a non-orthogonal basis. In this case
      the dimensionality of the density matrix is one more than `dim`.
      This is a keyword-only argument.
    """

    def __init__(self, geometry, dim=1, dtype=None, nnzpr=None, **kwargs):
        """ Initialize density matrix """
        super(DensityMatrix, self).__init__(geometry, dim, dtype, nnzpr, **kwargs)

        self.Dk = self.Pk

    def Dk(self, k=(0, 0, 0), dtype=None, gauge='R', format='csr', *args, **kwargs):
        r""" Setup the density matrix for a given k-point

        Creation and return of the density matrix for a given k-point (default to Gamma).

        Notes
        -----

        Currently the implemented gauge for the k-point is the cell vector gauge:

        .. math::
          D(k) = D_{\nu\mu} e^{i k R}

        where :math:`R` is an integer times the cell vector and :math:`\nu`, :math:`\mu` are orbital indices.

        Another possible gauge is the orbital distance which can be written as

        .. math::
          D(k) = D_{\nu\mu} e^{i k r}

        where :math:`r` is the distance between the orbitals :math:`\nu` and :math:`\mu`.
        Currently the second gauge is not implemented (yet).

        Parameters
        ----------
        k : array_like
           the k-point to setup the density matrix at
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
           if the density matrix is a spin polarized one can extract the specific spin direction
           matrix by passing an integer (0 or 1). If the density matrix is not `Spin.POLARIZED`
           this keyword is ignored.
        """
        pass

    def _get_D(self):
        self._def_dim = self.UP
        return self

    def _set_D(self, key, value):
        if len(key) == 2:
            self._def_dim = self.UP
        self[key] = value

    D = property(_get_D, _set_D)

    def density(self, grid, spinor=None, tol=1e-7, eta=False):
        r""" Expand the density matrix to the charge density on a grid

        This routine calculates the real-space density components on a specified grid.

        This is an *in-place* operation that *adds* to the current values in the grid.

        Note: To calculate :math:`\rho(\mathbf r)` in a unit-cell different from the
        originating geometry, simply pass a grid with a unit-cell different than the originating
        supercell.

        The real-space density is calculated as:

        .. math::
            \rho(\mathbf r) = \sum_{\nu\mu}\phi_\nu(\mathbf r)\phi_\mu(\mathbf r) D_{\nu\mu}

        While for non-collinear/spin-orbit calculations the density is determined from the
        spinor component (`spinor`) by

        .. math::
           \rho_{\boldsymbol\sigma}(\mathbf r) = \sum_{\nu\mu}\phi_\nu(\mathbf r)\phi_\mu(\mathbf r) \sum_\alpha [\boldsymbol\sigma \mathbf \rho_{\nu\mu}]_{\alpha\alpha}

        Here :math:`\boldsymbol\sigma` corresponds to a spinor operator to extract relevant quantities. By passing the identity matrix the total charge is added. By using the Pauli matrix :math:`\boldsymbol\sigma_x`
        only the :math:`x` component of the density is added to the grid (see `Spin.X`).

        Parameters
        ----------
        grid : Grid
           the grid on which to add the density (the density is in ``e/Ang^3``)
        spinor : (2,) or (2, 2), optional
           the spinor matrix to obtain the diagonal components of the density. For un-polarized density matrices
           this keyword has no influence. For spin-polarized it *has* to be either 1 integer or a vector of
           length 2 (defaults to total density).
           For non-collinear/spin-orbit density matrices it has to be a 2x2 matrix (defaults to total density).
        tol : float, optional
           DM tolerance for accepted values. For all density matrix elements with absolute values below
           the tolerance, they will be treated as strictly zeros.
        eta: bool, optional
           show a progressbar on stdout
        """
        try:
            # Once unique has the axis keyword, we know we can safely
            # use it in this routine
            # Otherwise we raise an ImportError
            unique([[0, 1], [2, 3]], axis=0)
        except:
            raise NotImplementedError(self.__class__.__name__ + '.density requires numpy >= 1.13, either update '
                                      'numpy or do not use this function!')

        geometry = self.geometry
        # Check that the atomic coordinates, really are all within the intrinsic supercell.
        # If not, it may mean that the DM does not conform to the primary unit-cell paradigm
        # of matrix elements. It complicates things.
        fxyz = geometry.fxyz
        f_min = fxyz.min()
        f_max = fxyz.max()
        if f_min < 0 or 1. < f_max:
            warn(self.__class__.__name__ + '.density has been passed a geometry where some coordinates are '
                 'outside the primary unit-cell. This may potentially lead to problems! '
                 'Double check the charge density!')
        del fxyz, f_min, f_max

        # Extract sub variables used throughout the loop
        shape = _a.asarrayi(grid.shape)
        dcell = grid.dcell

        # Sparse matrix data
        csr = self._csr

        # In the following we don't care about division
        # So 1) save error state, 2) turn off divide by 0, 3) calculate, 4) turn on old error state
        old_err = np.seterr(divide='ignore', invalid='ignore')

        # Placeholder for the resulting coefficients
        DM = None
        if self.spin.kind > Spin.POLARIZED:
            if spinor is None:
                # Default to the total density
                spinor = np.identity(2, dtype=np.complex128)
            else:
                spinor = _a.arrayz(spinor)
            if spinor.size != 4 or spinor.ndim != 2:
                raise ValueError(self.__class__.__name__ + '.density with NC/SO spin, requires a 2x2 matrix.')

            DM = _a.emptyz([self.nnz, 2, 2])
            idx = array_arange(csr.ptr[:-1], n=csr.ncol)
            if self.spin.kind == Spin.NONCOLINEAR:
                # non-collinear
                DM[:, 0, 0] = csr._D[idx, 0]
                DM[:, 1, 1] = csr._D[idx, 1]
                DM[:, 1, 0] = csr._D[idx, 2] - 1j * csr._D[idx, 3] #TODO check sign here!
                DM[:, 0, 1] = np.conj(DM[:, 1, 0])
            else:
                # spin-orbit
                DM[:, 0, 0] = csr._D[idx, 0] + 1j * csr._D[idx, 4]
                DM[:, 1, 1] = csr._D[idx, 1] + 1j * csr._D[idx, 5]
                DM[:, 1, 0] = csr._D[idx, 2] - 1j * csr._D[idx, 3] #TODO check sign here!
                DM[:, 0, 1] = csr._D[idx, 6] + 1j * csr._D[idx, 7]

            # Perform dot-product with spinor, and take out the diagonal real part
            DM = dot(DM, spinor.T)[:, [0, 1], [0, 1]].sum(1).real

        elif self.spin.kind == Spin.POLARIZED:
            if spinor is None:
                spinor = _a.onesd(2)

            elif isinstance(spinor, Integral):
                # extract the provided spin-polarization
                s = _a.zerosd(2)
                s[spinor] = 1.
                spinor = s
            else:
                spinor = _a.arrayd(spinor)

            if spinor.size != 2 or spinor.ndim != 1:
                raise ValueError(self.__class__.__name__ + '.density with polarized spin, requires spinor '
                                 'argument as an integer, or a vector of length 2')

            idx = array_arange(csr.ptr[:-1], n=csr.ncol)
            DM = csr._D[idx, 0] * spinor[0] + csr._D[idx, 1] * spinor[1]

        else:
            idx = array_arange(csr.ptr[:-1], n=csr.ncol)
            DM = csr._D[idx, 0]

        # Create the DM csr matrix.
        csrDM = csr_matrix((DM, csr.col[idx], np.insert(np.cumsum(csr.ncol), 0, 0)),
                           shape=(self.shape[:2]), dtype=DM.dtype)

        # Clean-up
        del idx, DM

        # To heavily speed up the construction of the density we can recreate
        # the sparse csrDM matrix by summing the lower and upper triangular part.
        # This means we only traverse the sparse UPPER part of the DM matrix
        # I.e.:
        #    psi_i * DM_{ij} * psi_j + psi_j * DM_{ji} * psi_i
        # is equal to:
        #    psi_i * (DM_{ij} + DM_{ji}) * psi_j
        # Secondly, to ease the loops we extract the main diagonal (on-site terms)
        # and store this for separate usage
        csr_sum = [None] * geometry.n_s
        no = geometry.no
        primary_i_s = geometry.sc_index([0, 0, 0])
        for i_s in range(geometry.n_s):
            # Extract the csr matrix
            o_start, o_end = i_s * no, (i_s + 1) * no
            csr = csrDM[:, o_start:o_end]
            if i_s == primary_i_s:
                csr_sum[i_s] = triu(csr) + tril(csr, -1).transpose()
            else:
                csr_sum[i_s] = csr

        # Recreate the column-stacked csr matrix
        csrDM = ss_hstack(csr_sum, format='csr')
        del csr, csr_sum

        # Remove all zero elements (note we use the tolerance here!)
        csrDM.data = np.where(np.fabs(csrDM.data) > tol, csrDM.data, 0.)

        # Eliminate zeros and sort indices etc.
        csrDM.eliminate_zeros()
        csrDM.sort_indices()
        csrDM.prune()

        # 1. Ensure the grid has a geometry associated with it
        sc = grid.sc.copy()
        if grid.geometry is None:
            # Create the actual geometry that encompass the grid
            ia, xyz, _ = geometry.within_inf(sc)
            if len(ia) > 0:
                grid.set_geometry(Geometry(xyz, geometry.atom[ia], sc=sc))

        # Instead of looping all atoms in the supercell we find the exact atoms
        # and their supercell indices.
        add_R = _a.zerosd(3) + geometry.maxR()
        # Calculate the required additional vectors required to increase the fictitious
        # supercell by add_R in each direction.
        # For extremely skewed lattices this will be way too much, hence we make
        # them square.
        o = sc.toCuboid(True)
        sc = SuperCell(o._v, origo=o.origo) + np.diag(2 * add_R)
        sc.origo -= add_R

        # Retrieve all atoms within the grid supercell
        # (and the neighbours that connect into the cell)
        IA, XYZ, ISC = geometry.within_inf(sc)

        # Retrieve progressbar
        eta = tqdm_eta(len(IA), self.__class__.__name__ + '.density', 'atom', eta)

        cell = geometry.cell
        atom = geometry.atom
        axyz = geometry.axyz
        a2o = geometry.a2o

        def xyz2spherical(xyz, offset):
            """ Calculate the spherical coordinates from indices """
            rx = xyz[:, 0] - offset[0]
            ry = xyz[:, 1] - offset[1]
            rz = xyz[:, 2] - offset[2]

            # Calculate radius ** 2
            xyz_to_spherical_cos_phi(rx, ry, rz)
            return rx, ry, rz

        def xyz2sphericalR(xyz, offset, R):
            """ Calculate the spherical coordinates from indices """
            rx = xyz[:, 0] - offset[0]
            idx = indices_fabs_le(rx, R)
            ry = xyz[idx, 1] - offset[1]
            ix = indices_fabs_le(ry, R)
            ry = ry[ix]
            idx = idx[ix]
            rz = xyz[idx, 2] - offset[2]
            ix = indices_fabs_le(rz, R)
            ry = ry[ix]
            rz = rz[ix]
            idx = idx[ix]
            if len(idx) == 0:
                return [], [], [], []
            rx = rx[idx]

            # Calculate radius ** 2
            ix = indices_le(rx ** 2 + ry ** 2 + rz ** 2, R ** 2)
            idx = idx[ix]
            if len(idx) == 0:
                return [], [], [], []
            rx = rx[ix]
            ry = ry[ix]
            rz = rz[ix]
            xyz_to_spherical_cos_phi(rx, ry, rz)
            return idx, rx, ry, rz

        # Looping atoms in the sparse pattern is better since we can pre-calculate
        # the radial parts and then add them.
        # First create a SparseOrbital matrix, then convert to SparseAtom
        spO = SparseOrbital(geometry, dtype=np.int16)
        spO._csr = SparseCSR(csrDM)
        spA = spO.toSparseAtom(dtype=np.int16)
        del spO
        na = geometry.na
        # Remove the diagonal part of the sparse atom matrix
        off = na * primary_i_s
        for ia in range(na):
            del spA[ia, off + ia]

        # Get pointers and delete the atomic sparse pattern
        # The below complexity is because we are not finalizing spA
        csr = spA._csr
        a_ptr = np.insert(_a.cumsumi(csr.ncol), 0, 0)
        a_col = csr.col[array_arange(csr.ptr, n=csr.ncol)]
        del spA, csr

        # Get offset in supercell in orbitals
        off = geometry.no * primary_i_s
        origo = grid.origo
        # TODO sum the non-origo atoms to the csrDM matrix
        #      this would further decrease the loops required.

        # Loop over all atoms in the grid-cell
        for ia, ia_xyz, isc in zip(IA, XYZ - origo.reshape(1, 3), ISC):
            # Get current atom
            ia_atom = atom[ia]
            IO = a2o(ia)
            IO_range = range(ia_atom.no)
            cell_offset = (cell * isc.reshape(3, 1)).sum(0) - origo

            # Extract maximum R
            R = ia_atom.maxR()
            if R <= 0.:
                warn("Atom '{}' does not have a wave-function, skipping atom.".format(ia_atom))
                eta.update()
                continue

            # Retrieve indices of the grid for the atomic shape
            idx = grid.index(ia_atom.toSphere(ia_xyz))

            # Now we have the indices for the largest orbital on the atom

            # Subsequently we have to loop the orbitals and the
            # connecting orbitals
            # Then we find the indices that overlap with these indices
            # First reduce indices to inside the grid-cell
            idx[idx[:, 0] < 0, 0] = 0
            idx[shape[0] <= idx[:, 0], 0] = shape[0] - 1
            idx[idx[:, 1] < 0, 1] = 0
            idx[shape[1] <= idx[:, 1], 1] = shape[1] - 1
            idx[idx[:, 2] < 0, 2] = 0
            idx[shape[2] <= idx[:, 2], 2] = shape[2] - 1

            # Remove duplicates, requires numpy >= 1.13
            idx = unique(idx, axis=0)
            if len(idx) == 0:
                eta.update()
                continue

            # Get real-space coordinates for the current atom
            # as well as the radial parts
            grid_xyz = dot(idx, dcell)

            # Perform loop on connection atoms
            # Allocate the DM_pj arrays
            # This will have a size equal to number of elements times number of
            # orbitals on this atom
            # In this way we do not have to calculate the psi_j multiple times
            DM_io = csrDM[IO:IO+ia_atom.no, :].tolil()
            DM_pj = _a.zerosd([ia_atom.no, grid_xyz.shape[0]])

            # Now we perform the loop on the connections for this atom
            # Remark that we have removed the diagonal atom (it-self)
            # As that will be calculated in the end
            for ja in a_col[a_ptr[ia]:a_ptr[ia+1]]:
                # Retrieve atom (which contains the orbitals)
                ja_atom = atom[ja % na]
                JO = a2o(ja)
                jR = ja_atom.maxR()
                # Get actual coordinate of the atom
                ja_xyz = axyz(ja) + cell_offset

                # Reduce the ia'th grid points to those that connects to the ja'th atom
                ja_idx, ja_r, ja_theta, ja_cos_phi = xyz2sphericalR(grid_xyz, ja_xyz, jR)

                if len(ja_idx) == 0:
                    # Quick step
                    continue

                # Loop on orbitals on this atom
                for jo in range(ja_atom.no):
                    o = ja_atom.orbital[jo]
                    oR = o.R

                    # Downsize to the correct indices
                    if jR - oR < 1e-6:
                        ja_idx1 = ja_idx.view()
                        ja_r1 = ja_r.view()
                        ja_theta1 = ja_theta.view()
                        ja_cos_phi1 = ja_cos_phi.view()
                    else:
                        ja_idx1 = indices_le(ja_r, oR)
                        if len(ja_idx1) == 0:
                            # Quick step
                            continue

                        # Reduce arrays
                        ja_r1 = ja_r[ja_idx1]
                        ja_theta1 = ja_theta[ja_idx1]
                        ja_cos_phi1 = ja_cos_phi[ja_idx1]
                        ja_idx1 = ja_idx[ja_idx1]

                    # Calculate the psi_j component
                    psi = o.psi_spher(ja_r1, ja_theta1, ja_cos_phi1, cos_phi=True)

                    # Now add this orbital to all components
                    for io in IO_range:
                        DM_pj[io, ja_idx1] += DM_io[io, JO+jo] * psi

                # Temporary clean up
                del ja_idx, ja_r, ja_theta, ja_cos_phi
                del ja_idx1, ja_r1, ja_theta1, ja_cos_phi1, psi

            # Now we have all components for all orbitals connection to all orbitals on atom
            # ia. We simply need to add the diagonal components

            # Loop on the orbitals on this atom
            ia_r, ia_theta, ia_cos_phi = xyz2spherical(grid_xyz, ia_xyz)
            del grid_xyz
            for io in IO_range:
                # Only loop halve the range.
                # This is because: triu + tril(-1).transpose()
                # removes the lower half of the on-site matrix.
                for jo in range(io+1, ia_atom.no):
                    DM = DM_io[io, off+IO+jo]

                    oj = ia_atom.orbital[jo]
                    ojR = oj.R

                    # Downsize to the correct indices
                    if R - ojR < 1e-6:
                        ja_idx1 = slice(None)
                        ja_r1 = ia_r.view()
                        ja_theta1 = ia_theta.view()
                        ja_cos_phi1 = ia_cos_phi.view()
                    else:
                        ja_idx1 = indices_le(ia_r, ojR)
                        if len(ja_idx1) == 0:
                            # Quick step
                            continue

                        # Reduce arrays
                        ja_r1 = ia_r[ja_idx1]
                        ja_theta1 = ia_theta[ja_idx1]
                        ja_cos_phi1 = ia_cos_phi[ja_idx1]

                    # Calculate the psi_j component
                    DM_pj[io, ja_idx1] += DM * oj.psi_spher(ja_r1, ja_theta1, ja_cos_phi1, cos_phi=True)

                # Calculate the psi_i component
                # Note that this one *also* zeroes points outside the shell
                # I.e. this step is important because it "nullifies" all but points where
                # orbital io is defined.
                psi = ia_atom.orbital[io].psi_spher(ia_r, ia_theta, ia_cos_phi, cos_phi=True)
                DM_pj[io, :] += DM_io[io, off+IO+io] * psi
                DM_pj[io, :] *= psi

            # Temporary clean up
            ja_idx1 = ja_r1 = ja_theta1 = ja_cos_phi1 = None
            del ia_r, ia_theta, ia_cos_phi, psi, DM_io

            # Now add the density
            grid.grid[idx[:, 0], idx[:, 1], idx[:, 2]] += DM_pj.sum(0)

            # Clean-up
            del DM_pj, idx

            eta.update()
        eta.close()

        # Reset the error code for division
        np.seterr(**old_err)

    @staticmethod
    def read(sile, *args, **kwargs):
        """ Reads density matrix from `Sile` using `read_density_matrix`.

        Parameters
        ----------
        sile : `Sile`, str
            a `Sile` object which will be used to read the density matrix
            and the overlap matrix (if any)
            if it is a string it will create a new sile using `get_sile`.
        * : args passed directly to ``read_density_matrix(,**)``
        """
        # This only works because, they *must*
        # have been imported previously
        from sisl.io import get_sile, BaseSile
        if isinstance(sile, BaseSile):
            return sile.read_density_matrix(*args, **kwargs)
        else:
            with get_sile(sile) as fh:
                return fh.read_density_matrix(*args, **kwargs)

    def write(self, sile, *args, **kwargs):
        """ Writes a density matrix to the `Sile` as implemented in the :code:`Sile.write_density_matrix` method """
        # This only works because, they *must*
        # have been imported previously
        from sisl.io import get_sile, BaseSile
        if isinstance(sile, BaseSile):
            sile.write_density_matrix(self, *args, **kwargs)
        else:
            with get_sile(sile, 'w') as fh:
                fh.write_density_matrix(self, *args, **kwargs)
