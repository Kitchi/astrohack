from scipy import optimize as opt
from astrohack._utils._linear_algebra import _gauss_elimination_numpy, _least_squares_fit
from astrohack._utils._globals import *

panelkinds = ["rigid", "mean", "xyparaboloid", "rotatedparaboloid", "corotatedparaboloid", "least_squares",
              "corotated_lst_sq"]
irigid = 0
imean = 1
ixypara = 2
irotpara = 3
icorpara = 4
ilstsqr = 5
icolstsq = 6


class BasePanel:
    markers = ['X', 'o', '*', 'P', 'D']
    colors = ['g', 'g', 'r', 'r', 'b']
    fontsize = 4
    linewidth = 0.5
    markersize = 2
    linecolor = 'black'

    def __init__(self, kind, screws, label, center=None, zeta=None):
        """
        Initializes a BasePanel with the common machinery to both PolygonPanel and RingPanel
        Args:
            kind: What kind of surface to be used in fitting ["rigid", "mean", "xyparaboloid",
            "rotatedparaboloid", "corotatedparaboloid"]
            label: Panel label
            screws: position of the screws
            center: Panel center
            zeta: panel center angle
        """
        self.kind = kind
        self.solved = False
        self.label = label
        self.screws = screws
        self.samples = []
        self.margins = []
        self.corr = None

        if center is None:
            self.center = [0, 0]
        else:
            self.center = center
        if zeta is None:
            self.zeta = 0
        else:
            self.zeta = zeta

        if self.kind == panelkinds[irigid]:
            self._associate_rigid()
        elif self.kind == panelkinds[imean]:
            self._associate_mean()
        elif self.kind == panelkinds[ixypara]:
            self._associate_scipy(self._xyaxes_paraboloid, 3)
        elif self.kind == panelkinds[irotpara]:
            self._associate_scipy(self._rotated_paraboloid, 4)
        elif self.kind == panelkinds[icorpara]:
            self._associate_scipy(self._corotated_paraboloid, 3)
        elif self.kind == panelkinds[ilstsqr]:
            self._associate_least_squares()
        elif self.kind == panelkinds[icolstsq]:
            self._associate_corotated_lst_sq()
        else:
            raise Exception("Unknown panel kind: ", self.kind)

    def _associate_scipy(self, fitting_function, npar):
        """
        Associate the proper methods to enable scipy fitting
        Args:
            fitting_function: The fitting function to be used by scipy
            npar: Number of paramenters in the fitting function
        """
        self.npar = npar
        self._solve_sub = self._solve_scipy
        self.corr_point = self._corr_point_scipy
        self._fitting_function = fitting_function

    def _associate_rigid(self):
        """
        Associate the proper methods to enable the rigid panel Linear algebra fitting
        """
        self.npar = 3
        self._solve_sub = self._solve_rigid
        self.corr_point = self._corr_point_rigid

    def _associate_mean(self):
        """
        Associate the proper methods to enable fitting by mean determination
        """
        self.npar = 1
        self._solve_sub = self._solve_mean
        self.corr_point = self._corr_point_mean

    def _associate_least_squares(self):
        """
        Associate the proper methods to enable least squares fitting of a fully fledged 9 parameter paraboloid
        """
        self.npar = 9
        self._solve_sub = self._solve_least_squares_paraboloid
        self.corr_point = self._corr_point_least_squares_paraboloid

    def _associate_corotated_lst_sq(self):
        """
        Associate the proper methods to enable least squares fitting of a corotated paraboloid
        """
        self.npar = 3
        self._solve_sub = self._solve_corotated_lst_sq
        self.corr_point = self._corr_point_corotated_lst_sq

    def add_sample(self, value):
        """
        Add a point to the panel's list of points to be fitted
        Args:
            value: tuple/list containing point description [xcoor,ycoor,xidx,yidx,value]
        """
        self.samples.append(value)

    def add_margin(self, value):
        """
        Add a point to the panel's list of points to be corrected, but not fitted
        Args:
            value: tuple/list containing point description [xcoor,ycoor,xidx,yidx,value]
        """
        self.margins.append(value)

    def solve(self):
        """
        Wrapping method around fitting to allow for a fallback to mean fitting in the case of an impossible fit
        """
        # fallback behaviour for impossible fits
        if len(self.samples) < self.npar:
            # WARNING SHOULD BE RAISED HERE
            self._fallback_solve()
        else:
            try:
                self._solve_sub()
            except np.linalg.LinAlgError:
                # WARNING SHOULD BE RAISED HERE
                self._fallback_solve()
        return

    def _fallback_solve(self):
        """
        Changes the method association to mean surface fitting, and fits the panel with it
        """
        self._associate_mean()
        self._solve_sub()

    def _solve_least_squares_paraboloid(self):
        """
        Builds the designer matrix for least squares fitting, and calls the _least_squares fitter for a fully fledged
        9 parameter paraboloid
        """
        # ax2y2 + bx2y + cxy2 + dx2 + ey2 + gxy + hx + iy + j
        data = np.array(self.samples)
        system = np.full((len(self.samples), self.npar), 1.0)
        system[:, 0] = data[:, 0]**2 * data[:, 1]**2
        system[:, 1] = data[:, 0]**2 * data[:, 1]
        system[:, 2] = data[:, 1]**2 * data[:, 0]
        system[:, 3] = data[:, 0] ** 2
        system[:, 4] = data[:, 1] ** 2
        system[:, 5] = data[:, 0] * data[:, 1]
        system[:, 6] = data[:, 0]
        system[:, 7] = data[:, 1]
        vector = data[:, -1]
        self.par, _, _ = _least_squares_fit(system, vector)
        self.solved = True

    def _corr_point_least_squares_paraboloid(self, xcoor, ycoor):
        """
        Computes the correction from the fitted parameters to the 9 parameter paraboloid at (xcoor, ycoor)
        Args:
            xcoor: Coordinate of point in X
            ycoor: Coordinate of point in Y
        Returns:
            The correction at point
        """
        # ax2y2 + bx2y + cxy2 + dx2 + ey2 + gxy + hx + iy + j
        xsq = xcoor**2
        ysq = ycoor**2
        point = self.par[0]*xsq*ysq + self.par[1]*xsq*ycoor + self.par[2]*ysq*xcoor
        point += self.par[3]*xsq + self.par[4]*ysq + self.par[5]*xcoor*ycoor
        point += self.par[6]*xcoor + self.par[7]*ycoor + self.par[8]
        return point

    def _solve_corotated_lst_sq(self):
        """
        Builds the designer matrix for least squares fitting, and calls the _least_squares fitter for a corotated
        paraboloid centered at the center of the panel
        """
        # a*u**2 + b*v**2 + c
        data = np.array(self.samples)
        system = np.full((len(self.samples), self.npar), 1.0)
        xc, yc = self.center
        system[:, 0] = ((data[:, 0] - xc) * np.cos(self.zeta) + (data[:, 1] - yc) * np.sin(self.zeta))**2  # U
        system[:, 1] = ((data[:, 0] - xc) * np.sin(self.zeta) + (data[:, 1] - yc) * np.cos(self.zeta))**2  # V
        vector = data[:, -1]
        self.par, _, _ = _least_squares_fit(system, vector)
        self.solved = True

    def _corr_point_corotated_lst_sq(self, xcoor, ycoor):
        """
        Computes the correction from the least squares fitted parameters to the corotated paraboloid
        Args:
            xcoor: Coordinate of point in X
            ycoor: Coordinate of point in Y
        Returns:
            The correction at point
        """
        # a*u**2 + b*v**2 + c
        xc, yc = self.center
        usq = ((xcoor - xc) * np.cos(self.zeta) + (ycoor - yc) * np.sin(self.zeta))**2
        vsq = ((xcoor - xc) * np.sin(self.zeta) + (ycoor - yc) * np.cos(self.zeta))**2
        return self.par[0]*usq + self.par[1]*vsq + self.par[2]

    def _solve_scipy(self, verbose=False):
        """
        Fit ponel surface by using arbitrary models through scipy fitting engine
        Args:
            verbose: Increase verbosity in the fitting process
        """
        devia = np.ndarray([len(self.samples)])
        coords = np.ndarray([2, len(self.samples)])
        for i in range(len(self.samples)):
            devia[i] = self.samples[i][-1]
            coords[:, i] = self.samples[i][0], self.samples[i][1]

        liminf = [0, 0, -np.inf]
        limsup = [np.inf, np.inf, np.inf]
        p0 = [1e2, 1e2, np.mean(devia)]

        if self.kind == panelkinds[irotpara]:
            liminf.append(0.0)
            limsup.append(np.pi)
            p0.append(0)

        maxfevs = [100000, 1000000, 10000000]
        for maxfev in maxfevs:
            try:
                result = opt.curve_fit(self._fitting_function, coords, devia,
                                       p0=p0, bounds=[liminf, limsup],
                                       maxfev=maxfev)
            except RuntimeError:
                if verbose:
                    print("Increasing number of iterations")
                continue
            else:
                self.par = result[0]
                self.solved = True
                if verbose:
                    print("Converged with less than {0:d} iterations".format(maxfev))
                break

    def _xyaxes_paraboloid(self, coords, ucurv, vcurv, zoff):
        """
        Surface model to be used in fitting with scipy
        Assumes that the center of the paraboloid is the center of the panel
        In this model the panel can only bend in the x and y directions
        Args:
            coords: [x,y] coordinate pair for point
            ucurv: curvature in x direction
            vcurv: curvature in y direction
            zoff:  Z offset of the paraboloid

        Returns:
        Paraboloid value at X and Y
        """
        u = coords[0] - self.center[0]
        v = coords[1] - self.center[1]
        return ucurv * u**2 + vcurv * v**2 + zoff

    def _rotated_paraboloid(self, coords, ucurv, vcurv, zoff, theta):
        """
        Surface model to be used in fitting with scipy
        Assumes that the center of the paraboloid is the center of the panel
        This model is degenerate in the combinations of theta, ucurv and vcurv
        Args:
            coords: [x,y] coordinate pair for point
            ucurv: curvature in projected u direction
            vcurv: curvature in projected v direction
            zoff:  Z offset of the paraboloid
            theta: Angle between x,y and u,v coordinate systems

        Returns:
        Paraboloid value at X and Y
        """
        x, y = coords
        xc, yc = self.center
        u = (x - xc) * np.cos(theta) + (y - yc) * np.sin(theta)
        v = (x - xc) * np.sin(theta) + (y - yc) * np.cos(theta)
        return ucurv * u**2 + vcurv * v**2 + zoff

    def _corotated_paraboloid(self, coords, ucurv, vcurv, zoff):
        """
        Surface model to be used in fitting with scipy
        Same as the rotated paraboloid above, but theta is the panel center angle
        Not valid for polygon panels
        Assumes that the center of the paraboloid is the center of the panel
        Args:
            coords: [x,y] coordinate pair for point
            ucurv: curvature in projected u direction
            vcurv: curvature in projected v direction
            zoff:  Z offset of the paraboloid

        Returns:
        Paraboloid value at X and Y
        """
        x, y = coords
        xc, yc = self.center
        u = (x - xc) * np.cos(self.zeta) + (y - yc) * np.sin(self.zeta)
        v = (x - xc) * np.sin(self.zeta) + (y - yc) * np.cos(self.zeta)
        return ucurv * u**2 + vcurv * v**2 + zoff

    def _solve_rigid(self):
        """
        Fit panel surface using AIPS gaussian elimination model for rigid panels
        """
        system = np.zeros([self.npar, self.npar])
        vector = np.zeros(self.npar)
        for ipoint in range(len(self.samples)):
            if self.samples[ipoint][-1] != 0:
                system[0, 0] += self.samples[ipoint][0] * self.samples[ipoint][0]
                system[0, 1] += self.samples[ipoint][0] * self.samples[ipoint][1]
                system[0, 2] += self.samples[ipoint][0]
                system[1, 0] = system[0, 1]
                system[1, 1] += self.samples[ipoint][1] * self.samples[ipoint][1]
                system[1, 2] += self.samples[ipoint][1]
                system[2, 0] = system[0, 2]
                system[2, 1] = system[1, 2]
                system[2, 2] += 1.0
                vector[0] += self.samples[ipoint][-1] * self.samples[ipoint][0]
                vector[1] += self.samples[ipoint][-1] * self.samples[ipoint][1]
                vector[2] += self.samples[ipoint][-1]

        self.par = _gauss_elimination_numpy(system, vector)
        self.solved = True
        return

    def _solve_mean(self):
        """
        Fit panel surface as a simple mean of its points Z deviation
        """
        if len(self.samples) > 0:
            # Solve panel adjustments for rigid vertical shift only panels
            self.par = [np.mean(self.samples)]
        else:
            self.par = [0]
        self.solved = True
        return

    def get_corrections(self):
        """
        Store corrections for the points in the panel
        """
        if not self.solved:
            raise Exception("Cannot correct a panel that is not solved")
        lencorr = len(self.samples)+len(self.margins)
        self.corr = np.ndarray([lencorr, 3])
        icorr = 0
        for isamp in range(len(self.samples)):
            xc, yc = self.samples[isamp][0:2]
            ix, iy = self.samples[isamp][2:4]
            self.corr[icorr, :] = ix, iy, self.corr_point(xc, yc)
            icorr += 1
        for imarg in range(len(self.margins)):
            xc, yc = self.margins[imarg][0:2]
            ix, iy = self.margins[imarg][2:4]
            self.corr[icorr, :] = ix, iy, self.corr_point(xc, yc)
            icorr += 1
        return self.corr

    def _corr_point_scipy(self, xcoor, ycoor):
        """
        Computes the fitted value for point [xcoor, ycoor] using the scipy models
        Args:
            xcoor: X coordinate of point
            ycoor: Y coordinate of point

        Returns:
        Fitted value at xcoor,ycoor
        """
        corrval = self._fitting_function([xcoor, ycoor], *self.par)
        return corrval

    def _corr_point_rigid(self, xcoor, ycoor):
        """
        Computes fitted value for point [xcoor, ycoor] using AIPS gaussian elimination model for rigid panels
        Args:
            xcoor: X coordinate of point
            ycoor: Y coordinate of point

        Returns:
        Fitted value at xcoor,ycoor
        """
        return xcoor * self.par[0] + ycoor * self.par[1] + self.par[2]

    def _corr_point_mean(self, xcoor, ycoor):
        """
        Computes fitted value for point [xcoor, ycoor] using AIPS shift only panels
        Args:
            xcoor: X coordinate of point
            ycoor: Y coordinate of point

        Returns:
        Fitted value at xcoor,ycoor
        """
        return self.par[0]

    def export_adjustments(self, unit='mm'):
        """
        Exports panel screw adjustments to a string
        Args:
            unit: Unit for screw adjustments ['mm','miliinches']
        Returns:
        String with screw adjustments for this panel
        """
        if unit == 'mm':
            fac = m2mm
        elif unit == 'miliinches':
            fac = m2mils
        else:
            raise Exception("Unknown unit: " + unit)
        string = self.label
        for screw in self.screws[:, ]:
            string += ' {0:10.2f}'.format(fac * self.corr_point(*screw))
        return string

    def plot_label(self, ax, rotate=True):
        """
        Plots panel label to ax
        Args:
            ax: matplotlib axes instance
            rotate: Rotate label for better display
        """
        if rotate:
            angle = (-self.zeta % pi - pi/2)*rad2deg
        else:
            angle = 0
        ax.text(self.center[1], self.center[0], self.label, fontsize=self.fontsize, ha='center', va='center',
                rotation=angle)

    def plot_screws(self, ax):
        """
        Plots panel screws to ax
        Args:
            ax: matplotlib axes instance
        """
        for iscrew in range(self.screws.shape[0]):
            screw = self.screws[iscrew, ]
            ax.scatter(screw[1], screw[0], marker=self.markers[iscrew], lw=self.linewidth, s=self.markersize,
                       color=self.colors[iscrew])
