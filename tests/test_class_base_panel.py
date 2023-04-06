import pytest

from astrohack._classes.base_panel import _gauss_elimination_numpy, BasePanel, \
     panelkinds, imean, irigid, icorscp, icorlst, ixypara, icorrob, irotpara, ifulllst
from astrohack._utils._conversion import _convert_unit
import numpy as np


class TestBasePanel:
    tolerance = 1e-6

    def test_gauss_elimination_numpy(self):
        """
        Tests the gaussian elimination routine by using an identity matrix
        """
        size = 3
        identity = np.identity(size)
        vector = np.arange(size)
        for pos in range(size):
            assert _gauss_elimination_numpy(identity, vector)[pos] == vector[pos], 'Gaussian elimination failed'

    def test_init(self):
        screws = np.zeros([4, 2])
        label = 'TEST'
        lepanel = BasePanel(panelkinds[imean], screws, label)
        assert lepanel.label == label, "Internal panel label not what expected"
        assert lepanel.kind == panelkinds[imean], "Internal kind does not match input"
        assert lepanel.samples == [], 'List of samples should be empty'
        assert lepanel.margins == [], 'list of pixels in the margin should be empty'
        assert lepanel.corr is None, 'List of corrections should be None'
        assert not lepanel.solved, 'Panel cannot be solved at creation'
        with pytest.raises(Exception):
            lepanel = BasePanel('xxx', screws, label)

    def test_add_point(self):
        """
        Test the add point common function
        """
        screws = np.zeros([4, 2])
        ipanel = 0
        lepanel = BasePanel(panelkinds[imean], ipanel, screws)
        nsamp = 30
        point = [0, 0, 0, 0, 0]
        for i in range(nsamp):
            lepanel.add_sample(point)
            lepanel.add_margin(point)
        assert len(lepanel.samples) == nsamp, 'Internal number of samples do not match the expected number of samples'
        assert len(lepanel.margins) == nsamp, 'Internal list of points does not have the expected size'
        for i in range(nsamp):
            assert lepanel.samples[i] == point, '{0:d}-eth point does not match input point'.format(i)
        return

    def test_mean_kind(self):
        """
        Tests the whole usage of a panel of the mean kind
        """
        expectedmean = 3.5
        point = [0, 0, 0, 0, expectedmean]
        screws = np.zeros([4, 2])
        nsamp = 30
        meanpanel = BasePanel(panelkinds[imean], screws, 'test')
        assert meanpanel._solve_sub == meanpanel._solve_mean, 'Incorrect overloading of mean solving method'
        assert meanpanel.corr_point == meanpanel._corr_point_mean, 'Incorrect overloading of mean point correction ' \
                                                                   'method'
        for i in range(nsamp):
            meanpanel.add_sample(point)
        meanpanel.solve()
        assert abs(meanpanel.par[0] - expectedmean)/expectedmean < self.tolerance, 'Did not recover the expected mean'
        meanpanel.get_corrections()
        assert len(meanpanel.corr) == nsamp, 'Number of corrected points do not match number of samples'
        onecorr = meanpanel.corr_point(0, 0)
        assert abs(onecorr - expectedmean)/expectedmean < self.tolerance, 'Correction for a point did not match the ' \
                                                                          'expected value'
        mmscrews = meanpanel.export_screws_float(unit='mm')
        fac = _convert_unit('m', 'mm', 'length')
        for screw in mmscrews:
            assert abs(screw - fac*expectedmean) < self.tolerance, 'mm screw adjustments not within 0.1% tolerance '\
                                                                      'of the expected value'
        miscrews = meanpanel.export_screws_float(unit='mils')
        fac = _convert_unit('m', 'mils', 'length')
        for screw in miscrews:
            assert abs(screw - fac * expectedmean) < 1e-2, 'Miliinches screw adjustments not ' \
                                                                         'within 1% of the expected value'

    def test_rigid_kind(self):
        """
        Tests the whole usage of a panel of the rigid kind
        """
        expectedpar = [3.5, -2, 1]
        screws = np.zeros([4, 2])
        nside = 32
        rigidpanel = BasePanel(panelkinds[irigid], screws, 'test')
        assert rigidpanel._solve_sub == rigidpanel._solve_rigid, 'Incorrect overloading of rigid solving method'
        assert rigidpanel.corr_point == rigidpanel._corr_point_rigid, 'Incorrect overloading of rigid point ' \
                                                                      'correction method'
        for ix in range(nside):
            for iy in range(nside):
                value = ix*expectedpar[0] + iy*expectedpar[1] + expectedpar[2]
                rigidpanel.add_sample([ix, iy, ix, iy, value])
        rigidpanel.solve()
        for ipar in range(3):
            feedback = '{0:d}-eth parameter does not match its expected value'.format(ipar)
            assert abs(rigidpanel.par[ipar]-expectedpar[ipar])/abs(expectedpar[ipar]) < self.tolerance, feedback
        rigidpanel.get_corrections()
        assert len(rigidpanel.corr) == nside**2, 'Number of corrected points do not match number of samples'
        onecorr = rigidpanel.corr_point(0, 0)
        assert abs(onecorr - expectedpar[2])/expectedpar[2] < self.tolerance, 'Correction for a point did not match ' \
                                                                              'the expected value'
        mmscrews = rigidpanel.export_screws_float()
        fac = _convert_unit('m', 'mm', 'length')
        for screw in mmscrews:
            assert abs(screw - fac*expectedpar[2]) < self.tolerance, 'mm screw adjustments not within 0.1% ' \
                                                                        'tolerance of the expected value'

    def test_xyparaboloid_scipy_kind(self):
        """
        Tests the whole usage of a panel of the xyparaboloid kind
        """
        expectedpar = [150, 10, 2.5]
        screws = np.zeros([4, 2])
        nside = 32
        xyparapanel = BasePanel(panelkinds[ixypara], screws, 'test')
        assert xyparapanel._solve_sub == xyparapanel._solve_scipy, 'Incorrect overloading of scipy solving method'
        assert xyparapanel.corr_point == xyparapanel._corr_point_scipy, 'Incorrect overloading of rigid point ' \
                                                                        'correction method'
        assert xyparapanel._fitting_function == xyparapanel._xyaxes_paraboloid, 'Incorrect overloading of XY '\
                                                                                'paraboloid function'
        for ix in range(nside):
            for iy in range(nside):
                value = expectedpar[0]*ix**2 + expectedpar[1]*iy**2 + expectedpar[2]
                xyparapanel.add_sample([ix, iy, ix, iy, value])
        xyparapanel.solve()
        for ipar in range(3):
            feedback = '{0:d}-eth parameter does not match its expected value'.format(ipar)
            assert abs(xyparapanel.par[ipar] - expectedpar[ipar]) / abs(expectedpar[ipar]) < self.tolerance, feedback
        xyparapanel.get_corrections()
        assert len(xyparapanel.corr) == nside ** 2, 'Number of corrected points do not match number of samples'
        onecorr = xyparapanel.corr_point(0, 0)
        assert abs(onecorr - expectedpar[2]) / expectedpar[2] < self.tolerance, 'Correction for a point did not match '\
                                                                                'the expected value'
        mmscrews = xyparapanel.export_screws_float()
        fac = _convert_unit('m', 'mm', 'length')
        for screw in mmscrews:
            assert abs(screw - fac*expectedpar[2]) < self.tolerance, 'mm screw adjustments not within 0.1% ' \
                                                                        'tolerance of the expected value'

    def test_rotatedparaboloid_scipy_kind(self):
        """
        Tests the whole usage of a panel of the rotatedparaboloid kind
        """
        theta = 0
        expectedpar = [39, 10, 2.5, theta]
        screws = np.zeros([4, 2])
        nside = 32
        rotparapanel = BasePanel(panelkinds[irotpara], screws, 'test')
        assert rotparapanel._solve_sub == rotparapanel._solve_scipy, 'Incorrect overloading of scipy solving method'
        assert rotparapanel.corr_point == rotparapanel._corr_point_scipy, 'Incorrect overloading of rigid point ' \
                                                                          'correction method'
        assert rotparapanel._fitting_function == rotparapanel._rotated_paraboloid, 'Incorrect overloading of paraboloid' \
                                                                                   ' function'
        for ix in range(nside):
            for iy in range(nside):
                u = ix * np.cos(theta) - iy * np.sin(theta)
                v = ix * np.sin(theta) + iy * np.cos(theta)
                value = expectedpar[0] * u**2 + expectedpar[1] * v**2 + expectedpar[2]
                rotparapanel.add_sample([ix, iy, ix, iy, value])
        rotparapanel.solve()
        for ipar in range(3):
            feedback = '{0:d}-eth parameter does not match its expected value'.format(ipar)
            assert abs(rotparapanel.par[ipar] - expectedpar[ipar]) / abs(expectedpar[ipar]) < self.tolerance, feedback
        rotparapanel.get_corrections()
        assert len(rotparapanel.corr) == nside ** 2, 'Number of corrected points do not match number of samples'
        onecorr = rotparapanel.corr_point(0, 0)
        assert abs(onecorr - expectedpar[2]) / expectedpar[2] < self.tolerance, 'Correction for a point did not match '\
                                                                                'the expected value'
        mmscrews = rotparapanel.export_screws_float()
        fac = _convert_unit('m', 'mm', 'length')
        for screw in mmscrews:
            assert abs(screw - fac*expectedpar[2]) < 1e3*self.tolerance, 'mm screw adjustments not within 0.1% ' \
                                                                        'tolerance of the expected value'

    def test_corotatedparaboloid_scipy_kind(self):
        """
        Tests the whole usage of a panel of the corotatedparaboloid kind
        """
        expectedpar = [75, 5, -2.0]
        screws = np.zeros([4, 2])
        nside = 32
        corotparapanel = BasePanel(panelkinds[icorscp], screws, 'test')
        assert corotparapanel._solve_sub == corotparapanel._solve_scipy, 'Incorrect overloading of rigid solving method'
        assert corotparapanel.corr_point == corotparapanel._corr_point_scipy, 'Incorrect overloading of rigid point ' \
                                                                              'correction method'
        assert corotparapanel._fitting_function == corotparapanel._corotated_paraboloid, 'Incorrect overloading of ' \
                                                                                         'paraboloid function'
        for ix in range(nside):
            for iy in range(nside):
                value = expectedpar[0]*ix**2 + expectedpar[1]*iy**2 + expectedpar[2]
                corotparapanel.add_sample([ix, iy, ix, iy, value])
        corotparapanel.solve()
        for ipar in range(3):
            feedback = '{0:d}-eth parameter does not match its expected value'.format(ipar)
            assert abs(corotparapanel.par[ipar] - expectedpar[ipar]) / abs(expectedpar[ipar]) < self.tolerance, feedback
        corotparapanel.get_corrections()
        assert len(corotparapanel.corr) == nside ** 2, 'Number of corrected points do not match number of samples'
        onecorr = corotparapanel.corr_point(0, 0)
        assert abs(onecorr - expectedpar[2]) / expectedpar[2] < self.tolerance, 'Correction for a point did not match '\
                                                                                'the expected value'
        mmscrews = corotparapanel.export_screws_float()
        fac = _convert_unit('m', 'mm', 'length')
        for screw in mmscrews:
            assert abs(screw - fac*expectedpar[2]) < self.tolerance, 'mm screw adjustments not within 0.1% ' \
                                                                        'tolerance of the expected value'
