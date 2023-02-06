import numpy as np
from matplotlib import pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
from astrohack._classes.linear_axis import LinearAxis
from astrohack._classes.base_panel import panelkinds, irotpara, ixypara
from astrohack._classes.ring_panel import RingPanel
from astrohack._classes.telescope import Telescope
from astrohack._utils._fits_io import _read_fits
from astrohack._utils._fits_io import _write_fits
from astrohack._utils._globals import *

lnbr = "\n"


class AntennaSurface:
    def __init__(self, amp, dev, telescope, cutoff=0.21, pkind=None, deviationisphase=False):
        """
        Antenna Surface description capable of computing RMS, Gains, and fitting the surface to obtain screw adjustments
        Args:
            amp: Amplitude aperture image (AIPS FITS file)
            dev: Physical deviation aperture image (AIPS FITS file)
            telescope: currently supported: ["VLA","VLBA"]
            cutoff: fractional cutoff on the amplitude image to exclude regions with weak amplitude from the panel
            surface fitting
            pkind: Kind of panel surface fitting, if is None defaults to telescope default
        """
        # Initializes antenna surface parameters
        self.ampfile = amp
        self.devfile = dev

        self.ingains = np.nan
        self.ougains = np.nan
        self.inrms = np.nan
        self.ourms = np.nan

        self._read_images()
        self.cut = cutoff * np.max(self.amp)

        self.telescope = Telescope(telescope)

        if pkind is None:
            if self.telescope.ringed:
                self.panelkind = panelkinds[irotpara]
            else:
                self.panelkind = panelkinds[ixypara]
        else:
            self.panelkind = pkind

        self._get_aips_headpars()
        self.reso = self.telescope.diam / self.npoint

        self.residuals = None
        self.corrections = None
        self.phase_corrections = None
        self.phase_residuals = None
        self.solved = False
        if self.telescope.ringed:
            self._build_polar()
            self._build_ring_panels()
            self._build_ring_mask()
            self.fetch_panel = self._fetch_panel_ringed
            self.compile_panel_points = self._compile_panel_points_ringed

        if deviationisphase:
            self.phase = self.deviation
            self.deviation = self._phase_to_deviation(self.phase)
        else:
            self.phase = self._deviation_to_phase(self.deviation)

    def _get_aips_headpars(self):
        """
        Fetches AIPS specific metadata from FITS headers
        """
        for line in self.devhead["HISTORY"]:
            wrds = line.split()
            if wrds[1] == "Visibilities":
                self.npoint = np.sqrt(int(wrds[-1]))
            elif wrds[1] == "Observing":
                self.wavel = float(wrds[-2])
            elif wrds[1] == "Antenna" and wrds[2] == "surface":
                self.inlim = abs(float(wrds[-3]))
                self.oulim = abs(float(wrds[-2]))

    def _read_images(self):
        """
        Reads amplitude and deviation images and initializes the X and Y axes
        """
        self.amphead, self.amp = _read_fits(self.ampfile)
        self.devhead, self.deviation = _read_fits(self.devfile)
        #
        if self.devhead["NAXIS1"] != self.amphead["NAXIS1"]:
            raise Exception("Amplitude and deviation images have different sizes")
        self.npix = int(self.devhead["NAXIS1"])
        self.xaxis = LinearAxis(
            self.npix,
            self.amphead["CRPIX1"],
            self.amphead["CRVAL1"],
            self.amphead["CDELT1"],
        )
        self.yaxis = LinearAxis(
            self.npix,
            self.amphead["CRPIX2"],
            self.amphead["CRVAL2"],
            self.amphead["CDELT2"],
        )
        return

    def _phase_to_deviation(self, phase):
        """
        Transforms a phase map to a physical deviation map
        Args:
            phase: Input phase map

        Returns:
            Physical deviation map
        """
        acoeff = (self.wavel / twopi) / (4.0 * self.telescope.focus)
        bcoeff = 4 * self.telescope.focus ** 2
        return acoeff * phase * np.sqrt(self.rad ** 2 + bcoeff)

    def _deviation_to_phase(self, deviation):
        """
        Transforms a physical deviation map to a phase map
        Args:
            deviation: Input physical deviation map

        Returns:
            Phase map
        """
        acoeff = (self.wavel / twopi) / (4.0 * self.telescope.focus)
        bcoeff = 4 * self.telescope.focus ** 2
        return deviation / (acoeff * np.sqrt(self.rad ** 2 + bcoeff))

    def _build_ring_mask(self):
        """
        Builds the mask on regions to be included in panel surface masks, specific to circular antennas as there is an
        outer and inner limit to the mask based on the antenna's inner receiver hole and outer edge
        """
        self.mask = np.where(self.amp < self.cut, False, True)
        self.mask = np.where(self.rad > self.inlim, self.mask, False)
        self.mask = np.where(self.rad < self.oulim, self.mask, False)
        self.mask = np.where(np.isnan(self.deviation), False, self.mask)

    def _build_polar(self):
        """
        Build polar coordinate grid, specific for circular antennas with panels arranged in rings
        """
        self.rad = np.zeros([self.npix, self.npix])
        self.phi = np.zeros([self.npix, self.npix])
        for iy in range(self.npix):
            ycoor = self.yaxis.idx_to_coor(iy + 0.5)
            for ix in range(self.npix):
                xcoor = self.xaxis.idx_to_coor(ix + 0.5)
                self.rad[ix, iy] = np.sqrt(xcoor ** 2 + ycoor ** 2)
                self.phi[ix, iy] = np.arctan2(ycoor, xcoor)
                if self.phi[ix, iy] < 0:
                    self.phi[ix, iy] += 2 * np.pi

    def _build_ring_panels(self):
        """
        Build list of panels, specific for circular antennas with panels arranged in rings
        """
        self.panels = []
        for iring in range(self.telescope.nrings):
            angle = 2.0 * np.pi / self.telescope.npanel[iring]
            for ipanel in range(self.telescope.npanel[iring]):
                panel = RingPanel(
                    self.panelkind,
                    angle,
                    iring,
                    ipanel,
                    self.telescope.inrad[iring],
                    self.telescope.ourad[iring],
                )
                self.panels.append(panel)
        return

    def _compile_panel_points_ringed(self):
        """
        Loops through the points in the antenna surface and checks to which panels it belongs,
        specific for circular antennas with panels arranged in rings
        """
        for iy in range(self.npix):
            yc = self.yaxis.idx_to_coor(iy + 0.5)
            for ix in range(self.npix):
                if self.mask[ix, iy]:
                    xc = self.xaxis.idx_to_coor(ix + 0.5)
                    # How to do the coordinate choice here without
                    # adding an if?
                    for panel in self.panels:
                        if panel.is_inside(self.rad[ix, iy], self.phi[ix, iy]):
                            panel.add_point([xc, yc, ix, iy, self.deviation[ix, iy]])

    def _fetch_panel_ringed(self, ring, panel):
        """
        Fetch a panel object from the panel list using its ring and panel numbers,
        specific for circular antennas with panels arranged in rings
        Args:
            ring: Ring number
            panel: Panel number

        Returns:
        Panel object
        """
        if ring == 1:
            ipanel = panel - 1
        else:
            ipanel = np.sum(self.telescope.npanel[: ring - 1]) + panel - 1
        return self.panels[ipanel]

    def gains(self):
        """
        Computes antenna gains in decibels before and after panel surface fitting
        Returns:
        Gains before panel fitting OR Gains before and after panel fitting
        """
        self.ingains = self._gains_array(self.phase)
        if self.residuals is None:
            return self.ingains
        else:
            self.ougains = self._gains_array(self.phase_residuals)
            return self.ingains, self.ougains

    def _gains_array(self, arr):
        """
        Worker for gains method, works with the actual arrays to compute the gains
        This numpy version is significantly faster than the previous version
        Args:
            arr: Deviation image over which to compute the gains

        Returns:
        Actual and theoretical gains
        """
        thgain = fourpi * (1000.0 * self.reso / self.wavel) ** 2
        gain = thgain * np.sqrt(np.sum(np.cos(arr[self.mask]))**2 + np.sum(np.sin(arr[self.mask]))**2)/np.sum(self.mask)
        return convert_to_db(gain), convert_to_db(thgain)

    def get_rms(self, phase=False):
        """
        Computes antenna surface RMS before and after panel surface fitting
        Returns:
        RMS before panel fitting OR RMS before and after panel fitting
        """
        self.inrms = m2mm * self._compute_rms_array(self.deviation)
        if self.residuals is None:
            return self.inrms
        else:
            self.ourms = m2mm * self._compute_rms_array(self.residuals)
        return self.inrms, self.ourms

    def _compute_rms_array(self, array):
        """
        Factorized the computation of the RMS of an array
        Args:
            array: Input data array

        Returns:
            RMS of the input array
        """
        return np.sqrt(np.mean(array[self.mask] ** 2))

    def fit_surface(self):
        """
        Loops over the panels to fit the panel surfaces
        """
        for panel in self.panels:
            panel.solve()
        self.solved = True

    def correct_surface(self):
        """
        Apply corrections determined by the panel surface fitting methods to the antenna surface
        """
        if not self.solved:
            raise Exception("Panels must be fitted before atempting a correction")
        self.corrections = np.where(self.mask, 0, np.nan)
        self.residuals = np.copy(self.deviation)
        for panel in self.panels:
            panel.get_corrections()
            for ipnt in range(len(panel.corr)):
                val = panel.values[ipnt]
                ix, iy = int(val[2]), int(val[3])
                self.residuals[ix, iy] -= panel.corr[ipnt]
                self.corrections[ix, iy] = -panel.corr[ipnt]
        self.phase_corrections = self._deviation_to_phase(self.corrections)
        self.phase_residuals = self._deviation_to_phase(self.residuals)

    def print_misc(self):
        """
        Print miscelaneous information on the panels in the antenna surface
        """
        for panel in self.panels:
            panel.print_misc()

    def plot_surface(self, filename=None, mask=False, screws=False, dpi=300, plotphase=False):
        """
        Do plots of the antenna surface
        Args:
            filename: Save plot to a file rather than displaying it with matplotlib widgets
            mask: Display mask and amplitudes rather than deviation/phase images
            plotphase: plot phase images rather than deviation images 
            screws: Display the screws on the panels
            dpi: Plot resolution in DPI
        """
            
        if mask:
            fig, ax = plt.subplots(1, 2, figsize=[10, 5])
            title = "Mask"
            self._plot_surface(
                self.mask, title, fig, ax[0], 0, 1, screws=screws, mask=mask
            )
            vmin, vmax = np.nanmin(self.amp), np.nanmax(self.amp)
            title = "Amplitude min={0:.5f}, max ={1:.5f} V".format(vmin, vmax)
            self._plot_surface(
                self.amp, title, fig, ax[1], vmin, vmax, screws=screws,
                unit=self.amphead["BUNIT"].strip(),
            )
        else:
            if plotphase:
                self._plot_three_surfaces(self.phase, self.phase_corrections, self.phase_residuals, 'degress',
                                          rad2deg, screws, 'Antenna surface phase')
            else:
                self._plot_three_surfaces(self.deviation, self.corrections, self.residuals, 'mm', m2mm, screws,
                                          'Antenna surface')
        if filename is None:
            plt.show()
        else:
            plt.savefig(filename, dpi=dpi)

    def _plot_three_surfaces(self, original, corrections, residuals, unit, conversion, screws, suptitle):
        """
        Factorizes the plot of the combination of 3 maps
        Args:
            original: Original dataset
            corrections: Corrections applied to the dataset
            residuals: Residuals after correction
            unit: Unit of the output data
            conversion: Conversion factor between internal units and unit
            screws: show screws (Bool)
            suptitle: Superior title to be displayed on top of the figure

        Returns:

        """
        vmin, vmax = np.nanmin(conversion * original), np.nanmax(conversion * original)
        inrms = conversion * self._compute_rms_array(original)
        if self.residuals is None:
            fig, ax = plt.subplots()
            title = "Before correction\nRMS = {0:8.5} ".format(inrms)+unit
            self._plot_surface(conversion * original, title, fig, ax, vmin, vmax, screws=screws, unit=unit)
        else:
            fig, ax = plt.subplots(1, 3, figsize=[15, 5])
            ourms = conversion * self._compute_rms_array(residuals)
            title = "Before correction\nRMS = {0:.3} ".format(inrms)+unit
            self._plot_surface(conversion * original, title, fig, ax[0], vmin, vmax, screws=screws, unit=unit)
            title = "Corrections"
            self._plot_surface(conversion * corrections, title, fig, ax[1], vmin, vmax, screws=screws, unit=unit)
            title = "After correction\nRMS = {0:.3} ".format(ourms)+unit
            self._plot_surface(conversion * residuals, title, fig, ax[2], vmin, vmax, screws=screws, unit=unit)
        fig.suptitle(suptitle)
        fig.tight_layout()

    def _plot_surface(self, data, title, fig, ax, vmin, vmax, screws=False, mask=False, unit="mm"):
        """
        Does the plotting of a data array in a figure's subplot
        Args:
            data: The array to be plotted
            title: Title of the subplot
            fig: Global figure containing the subplots
            ax: matplotlib axes instance describing the subplot
            vmin: minimum to the color scale
            vmax: maximum to the color scale
            screws: Display screws
            mask: do not add colorbar if plotting a mask
            unit: Unit of the data in the color scale
        """
        ax.set_title(title)
        # set the limits of the plot to the limits of the data
        xmin = self.xaxis.idx_to_coor(-0.5)
        xmax = self.xaxis.idx_to_coor(self.xaxis.n - 0.5)
        ymin = self.yaxis.idx_to_coor(-0.5)
        ymax = self.yaxis.idx_to_coor(self.yaxis.n - 0.5)
        im = ax.imshow(
            np.flipud(data),
            cmap="viridis",
            interpolation="nearest",
            extent=[xmin, xmax, ymin, ymax],
            vmin=vmin,
            vmax=vmax,
        )
        divider = make_axes_locatable(ax)
        if not mask:
            cax = divider.append_axes("right", size="5%", pad=0.05)
            fig.colorbar(im, label="Z Scale [" + unit + "]", cax=cax)
        ax.set_xlabel("X axis [m]")
        ax.set_ylabel("Y axis [m]")
        for panel in self.panels:
            panel.plot(ax, screws=screws)

    def export_corrected(self, filename):
        """
        Export corrected surface to a FITS file
        Args:
            filename: Output FITS file name/path
        """
        if self.residuals is None:
            raise Exception("Cannot export corrected surface")
        _write_fits(self.devhead, self.residuals, filename)
        return

    def export_screw_adjustments(self, filename, unit="mm"):
        """
        Export screw adjustments for all panels onto an ASCII file
        Args:
            filename: ASCII file name/path
            unit: unit for panel screw adjustments ['mm','miliinches']
        """
        spc = " "
        outfile = "Screw adjustments for {0:s} {1:s} antenna\n".format(
            self.telescope.name, self.amphead["telescop"]
        )
        outfile += "Adjustments are in " + unit + lnbr
        outfile += 2 * lnbr
        outfile += 25 * spc + "{0:22s}{1:22s}".format("Inner Edge", "Outer Edge") + lnbr
        outfile += 5 * spc + "{0:8s}{1:8s}".format("Ring", "panel")
        outfile += 2 * spc + 2 * "{0:11s}{1:11s}".format("left", "right") + lnbr
        for panel in self.panels:
            outfile += panel.export_adjustments(unit=unit) + lnbr
        lefile = open(filename, "w")
        lefile.write(outfile)
        lefile.close()
