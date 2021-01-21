# Licensed under a 3-clause BSD style license - see LICENSE.rst
import pytest
import numpy as np
from numpy.testing import assert_allclose   
from astropy import units as u
from astropy.io import fits
from astropy.coordinates import Angle
from astropy.utils.data import get_pkg_data_filename
from gammapy.irf import EnergyDependentMultiGaussPSF, PSFKing
from gammapy.utils.testing import mpl_plot_check, requires_data, requires_dependency


@requires_data()
class TestEnergyDependentMultiGaussPSF:
    @pytest.fixture(scope="session")
    def psf(self):
        filename = "$GAMMAPY_DATA/tests/unbundled/irfs/psf.fits"
        return EnergyDependentMultiGaussPSF.read(filename, hdu="POINT SPREAD FUNCTION")

    def test_info(self, psf):
        info_str = open(get_pkg_data_filename("data/psf_info.txt")).read()

        print(psf.info())
        assert psf.info() == info_str

    def test_write(self, tmp_path, psf):
        psf.write(tmp_path / "tmp.fits")

        with fits.open(tmp_path / "tmp.fits", memmap=False) as hdu_list:
            assert len(hdu_list) == 2

    def test_to_table_psf(self, psf):
        energy = 1 * u.TeV
        theta = 0 * u.deg

        rad = np.linspace(0, 2, 300) * u.deg
        table_psf = psf.to_energy_dependent_table_psf(theta, rad=rad)

        containment = [0.68, 0.8, 0.9]
        desired = psf.containment_radius(
            energy_true=energy, offset=theta, fraction=containment
        )

        table_psf_at_energy = table_psf.table_psf_at_energy(energy)
        actual = table_psf_at_energy.containment_radius(containment)

        assert_allclose(desired, actual, rtol=1e-2)

    def test_to_psf3d(self, psf):
        rads = np.linspace(0.0, 1.0, 101) * u.deg
        psf_3d = psf.to_psf3d(rads)

        rad_axis = psf_3d.axes["rad"]
        assert rad_axis.nbin == 100
        assert rad_axis.unit == "deg"

        theta = 0.5 * u.deg
        energy = 0.5 * u.TeV

        containment = [0.68, 0.8, 0.9]
        desired = psf.containment_radius(
            energy_true=energy, offset=theta, fraction=containment
        )
        actual = psf_3d.containment_radius(
            energy_true=energy, offset=theta, fraction=containment
        )
        assert_allclose(np.squeeze(desired), actual, atol=0.005)

    @requires_dependency("matplotlib")
    def test_peek(self, psf):
        with mpl_plot_check():
            psf.peek()


@requires_data()
def test_psf_cta_1dc():
    filename = (
        "$GAMMAPY_DATA/cta-1dc/caldb/data/cta/1dc/bcf/South_z20_50h/irf_file.fits"
    )
    psf_irf = EnergyDependentMultiGaussPSF.read(filename, hdu="POINT SPREAD FUNCTION")

    # Check that PSF is filled with 0 for energy / offset where no PSF info is given.
    # This is needed so that stacked PSF computation doesn't error out,
    # trying to interpolate for observations / energies where this occurs.
    psf = psf_irf.to_energy_dependent_table_psf("4.5 deg")
    psf = psf.table_psf_at_energy("0.05 TeV")
    assert_allclose(psf.evaluate(rad="0.03 deg").value, 0)

    # Check that evaluation works for an energy / offset where an energy is available
    psf = psf_irf.to_energy_dependent_table_psf("2 deg")
    psf = psf.table_psf_at_energy("1 TeV")
    assert_allclose(psf.containment_radius(0.68), 0.052841 * u.deg, atol=1e-4)


@pytest.fixture(scope="session")
def psf_king():
    return PSFKing.read("$GAMMAPY_DATA/tests/hess_psf_king_023523.fits.gz")


@requires_data()
def test_psf_king_evaluate(psf_king):
    param_off1 = psf_king.evaluate_parameters(energy_true=1 * u.TeV, offset=0 * u.deg)
    param_off2 = psf_king.evaluate_parameters(energy_true=1 * u.TeV, offset=1 * u.deg)

    assert_allclose(param_off1["gamma"].value, 1.733179, rtol=1e-5)
    assert_allclose(param_off2["gamma"].value, 1.812795, rtol=1e-5)
    assert_allclose(param_off1["sigma"], 0.040576 * u.deg, rtol=1e-5)
    assert_allclose(param_off2["sigma"], 0.040765 * u.deg, rtol=1e-5)


@requires_data()
def test_psf_king_containment_radius(psf_king):
    radius = psf_king.containment_radius(
        fraction=0.68, energy_true=1 * u.TeV, offset=0.* u.deg
    )

    assert_allclose(radius, 0.65975 * u.deg, rtol=1e-5)


@requires_data()
def test_psf_king_to_table(psf_king):
    theta1 = Angle(0, "deg")
    theta2 = Angle(1, "deg")
    psf_king_table_off1 = psf_king.to_energy_dependent_table_psf(offset=theta1)
    rad = Angle(1, "deg")
    # energy = Quantity(1, "TeV") match with bin number 8
    # offset equal 1 degre match with the bin 200 in the psf_table
    value_off1 = psf_king.evaluate(
        rad=rad, energy_true=1 * u.TeV, offset=theta1
    )
    value_off2 = psf_king.evaluate(
        rad=rad, energy_true=1 * u.TeV, offset=theta2
    )
    # Test that the value at 1 degree in the histogram for the energy 1 Tev and theta=0 or 1 degree is equal to the one
    # obtained from the self.evaluate_direct() method at 1 degree
    assert_allclose(0.005234 * u.Unit("deg-2"), value_off1, rtol=1e-4)
    assert_allclose(0.004015 * u.Unit("deg-2"), value_off2, rtol=1e-4)

    # Test that the integral value is close to one
    integral = psf_king_table_off1.containment(rad=1 *u.deg, energy_true=1 * u.TeV)
    assert_allclose(integral, 1, atol=3e-2)


@requires_data()
def test_psf_king_write(psf_king, tmp_path):
    psf_king.write(tmp_path / "tmp.fits")
    psf_king2 = PSFKing.read(tmp_path / "tmp.fits")

    assert_allclose(
        psf_king2.axes["energy_true"].edges, psf_king.axes["energy_true"].edges
    )
    assert_allclose(psf_king2.axes["offset"].center, psf_king.axes["offset"].center)
    assert_allclose(psf_king2.data["gamma"], psf_king.data["gamma"])
    assert_allclose(psf_king2.data["sigma"], psf_king.data["sigma"])
