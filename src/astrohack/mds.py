import os
import numpy as np
import numbers
import distributed
from prettytable import PrettyTable
from matplotlib import colormaps as cmaps

from astrohack._utils._logger._astrohack_logger import _get_astrohack_logger
from astrohack._utils._dio import _read_meta_data
from astrohack._utils._dio import _load_holog_file
from astrohack._utils._dio import _load_image_file
from astrohack._utils._dio import _load_panel_file
from astrohack._utils._dio import _load_point_file
from astrohack._utils._dio import _load_locit_file
from astrohack._utils._dio import _load_position_file

from astrohack._utils._dio import _create_destination_folder
from astrohack._utils._param_utils._check_parms import _check_parms, _parm_check_passed
from astrohack._utils._constants import length_units, trigo_units, plot_types, possible_splits, time_units
from astrohack._utils._dask_graph_tools import _dask_general_compute
from astrohack._utils._tools import _print_method_list, _print_attributes, _print_data_contents, _print_summary_header
from astrohack._utils._tools import _rad_to_deg_str, _rad_to_hour_str

from astrohack._utils._panel import _plot_antenna_chunk, _export_to_fits_panel_chunk, _export_screws_chunk
from astrohack._utils._holog import _export_to_fits_holog_chunk, _plot_aperture_chunk, _plot_beam_chunk
from astrohack._utils._diagnostics import _calibration_plot_chunk
from astrohack._utils._extract_locit import _plot_source_table, _plot_antenna_table
from astrohack._utils._locit import _export_fit_results, _plot_sky_coverage_chunk
from astrohack._utils._locit import _plot_delays_chunk

from astrohack._utils._panel_classes.antenna_surface import AntennaSurface
from astrohack._utils._panel_classes.telescope import Telescope


class AstrohackDataFile:
    """ Base class for the Astrohack data files
    """
    def __init__(self, file_stem, path='./'):
                        
        self._image_path = None
        self._holog_path = None
        self._panel_path = None
        self._point_path = None

        self.holog = None
        self.image = None
        self.panel = None
        self.point = None
            
        self._verify_holog_files(file_stem, path)

    def _verify_holog_files(self, file_stem, path):
        logger = _get_astrohack_logger()
        logger.info("Verifying {stem}.* files in path={path} ...".format(stem=file_stem, path=path))

        file_path = "{path}/{stem}.holog.zarr".format(path=path, stem=file_stem)
            
        if os.path.isdir(file_path):
            logger.info("Found {stem}.holog.zarr directory ...".format(stem=file_stem))
            
            self._holog_path = file_path
            self.holog = AstrohackHologFile(file_path)

        file_path = "{path}/{stem}.image.zarr".format(path=path, stem=file_stem)

        if os.path.isdir(file_path):
            logger.info("Found {stem}.image.zarr directory ...".format(stem=file_stem))
            
            self._image_path = file_path
            self.image = AstrohackImageFile(file_path)

        file_path = "{path}/{stem}.panel.zarr".format(path=path, stem=file_stem)

        if os.path.isdir(file_path):
            logger.info("Found {stem}.panel.zarr directory ...".format(stem=file_stem))
            
            self._image_path = file_path
            self.panel = AstrohackPanelFile(file_path)

        file_path = "{path}/{stem}.point.zarr".format(path=path, stem=file_stem)

        if os.path.isdir(file_path):
            logger.info("Found {stem}.point.zarr directory ...".format(stem=file_stem))
            
            self._point_path = file_path
            self.point = AstrohackPointFile(file_path)


class AstrohackImageFile(dict):
    """ Data class for holography image data.

    Data within an object of this class can be selected for further inspection, plotted or outputed to FITS files.
    """
    def __init__(self, file):
        """ Initialize an AstrohackImageFile object.
        :param file: File to be linked to this object
        :type file: str

        :return: AstrohackImageFile object
        :rtype: AstrohackImageFile
        """
        super().__init__()
        self._meta_data = None
        self.file = file
        self._file_is_open = False

    def __getitem__(self, key):
        return super().__getitem__(key)
    
    def __setitem__(self, key, value):
        return super().__setitem__(key, value)
        
    def _is_open(self):
        """ Check wether the object has opened the corresponding hack file.

        :return: True if open, else False.
        :rtype: bool
        """
        return self._file_is_open

    def _open(self, file=None):
        """ Open holography image file.
        :param file: File to be opened, if None defaults to the previously defined file
        :type file: str, optional

        :return: True if file is properly opened, else returns False
        :rtype: bool
        """
        logger = _get_astrohack_logger()
        if file is None:
            file = self.file

        try:
            _load_image_file(file, image_dict=self)

            self._file_is_open = True

        except Exception as e:
            logger.error("[AstroHackImageFile.open()]: {}".format(e))
            self._file_is_open = False

        self._meta_data = _read_meta_data(file+'/.image_attr')

        return self._file_is_open

    def summary(self):
        """ Prints summary of the AstrohackImageFile object, with available data, attributes and available methods
        """
        _print_summary_header(self.file)
        _print_attributes(self._meta_data)
        _print_data_contents(self, ["Antenna", "DDI"])
        _print_method_list([self.summary, self.select, self.export_to_fits, self.plot_beams, self.plot_apertures])

    def select(self, ant_id, ddi, complex_split='cartesian'):
        """ Select data on the basis of ddi, scan, ant. This is a convenience function.

        :param ddi: Data description ID, ex. 0.
        :type ddi: int
        :param ant_id: Antenna ID, ex. ea25.
        :type ant_id: str
        :param complex_split: Is the data to b left as is (Real + imag: cartesian, default) or split into Amplitude and Phase (polar)
        :type complex_split: str, optional

        :return: Corresponding xarray dataset, or self if selection is None
        :rtype: xarray.Dataset or AstrohackImageFile
        """
        logger = _get_astrohack_logger()

        ant_id = 'ant_'+ant_id
        ddi = f'ddi_{ddi}'

        if ant_id is None or ddi is None:
            logger.info("[select]: No selections made ...")
            return self
        else:
            if complex_split == 'polar':
                return self[ant_id][ddi].apply(np.absolute), self[ant_id][ddi].apply(np.angle, deg=True)
            else:
                return self[ant_id][ddi]

    def export_to_fits(self, destination, complex_split='cartesian', ant_id=None, ddi=None, parallel=False):
        """ Export contents of an AstrohackImageFile object to several FITS files in the destination folder

        :param destination: Name of the destination folder to contain plots
        :type destination: str
        :param complex_split: How to split complex data, cartesian (real + imag, default) or polar (amplitude + phase)
        :type complex_split: str, optional
        :param ant_id: List of antennae/antenna to be plotted, defaults to "all" when None, ex. ea25
        :type ant_id: list or str, optional
        :param ddi: List of ddis/ddi to be plotted, defaults to "all" when None, ex. 0
        :type ddi: list or int, optional
        :param parallel: If True will use an existing astrohack client to export FITS in parallel, default is False
        :type parallel: bool, optional

        .. _Description:
        Export the products from the holog mds onto FITS files to be read by other software packages

        **Additional Information**
        The image products of holog are complex images due to the nature of interferometric measurements and Fourier
        transforms, currently complex128 FITS files are not supported by astropy, hence the need to split complex images
        onto two real image products, we present the user with two options to carry out this split.

        .. rubric:: Available complex splitting possibilities:
        - *cartesian*: Split is done to a real part and an imaginary part FITS files
        - *polar*:     Split is done to an amplitude and a phase FITS files


        The FITS files produced by this function have been tested and are known to work with CARTA and DS9
        """

        parm_dict = {'ant': ant_id,
                     'ddi': ddi,
                     'destination': destination,
                     'complex_split': complex_split,
                     'parallel': parallel}
        
        fname = 'export_to_fits'
        parms_passed = _check_parms(fname, parm_dict, 'complex_split', [str], acceptable_data=possible_splits,
                                    default="cartesian")
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'ant', [str, list],
                                                     list_acceptable_data_types=[str], default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'ddi', [int, list],
                                                     list_acceptable_data_types=[int], default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'destination', [str], default=None)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'parallel', [bool], default=True)

        _parm_check_passed(fname, parms_passed)
        _create_destination_folder(parm_dict['destination'])
        parm_dict['metadata'] = self._meta_data
        _dask_general_compute(fname, self, _export_to_fits_holog_chunk, parm_dict, ['ant', 'ddi'], parallel=parallel)

    def plot_apertures(self, destination, ant_id=None, ddi=None, plot_screws=False, unit=None, display=True,
                       colormap='viridis', figure_size=None, dpi=300, parallel=False):
        """ Aperture amplitude and phase plots from the data in an AstrohackImageFIle object.

        :param destination: Name of the destination folder to contain plots
        :type destination: str
        :param ant_id: List of antennae/antenna to be plotted, defaults to "all" when None, ex. ea25
        :type ant_id: list or str, optional
        :param ddi: List of ddis/ddi to be plotted, defaults to "all" when None, ex. 0
        :type ddi: list or int, optional
        :param plot_screws: Add screw positions to plot, default is False
        :type plot_screws: bool, optional
        :param unit: Unit for phase plots, defaults to 'deg'
        :type unit: str, optional
        :param display: Display plots inline or suppress, defaults to True
        :type display: bool, optional
        :param colormap: Colormap for plots, default is viridis
        :type colormap: str, optional
        :param figure_size: 2 element array/list/tuple with the plot sizes in inches
        :type figure_size: numpy.ndarray, list, tuple, optional
        :param dpi: dots per inch to be used in plots, default is 300
        :type dpi: int, optional
        :param parallel: If True will use an existing astrohack client to produce plots in parallel, default is False
        :type parallel: bool, optional

        .. _Description:

        Produce plots from ``astrohack.holog`` results for analysis
        """
        parm_dict = {'ant': ant_id,
                     'ddi': ddi,
                     'destination': destination,
                     'unit': unit,
                     'plot_screws': plot_screws,
                     'display': display,
                     'colormap': colormap,
                     'figuresize': figure_size,
                     'dpi': dpi,
                     'parallel': parallel}

        fname = 'plot_apertures'
        parms_passed = _check_parms(fname, parm_dict, 'ant', [str, list], list_acceptable_data_types=[str],
                                    default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'ddi', [int, list],
                                                     list_acceptable_data_types=[int], default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'destination', [str], default=None)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'unit', [str], acceptable_data=trigo_units,
                                                     default='deg')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'display', [bool], default=True)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'parallel', [bool], default=True)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'plot_screws', [bool], default=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'colormap', [str], acceptable_data=cmaps,
                                                     default='viridis')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'figuresize', [list, np.ndarray],
                                                     list_acceptable_data_types=[numbers.Number], list_len=2,
                                                     default='None', log_default_setting=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'dpi', [int], default=300)

        _parm_check_passed(fname, parms_passed)
        _create_destination_folder(parm_dict['destination'])
        _dask_general_compute(fname, self, _plot_aperture_chunk, parm_dict, ['ant', 'ddi'], parallel=parallel)

    def plot_beams(self, destination, ant_id=None, ddi=None, complex_split='polar', display=True, colormap='viridis',
                   figure_size=None, dpi=300, parallel=False):
        """ Beam plots from the data in an AstrohackImageFIle object.

        :param destination: Name of the destination folder to contain plots
        :type destination: str
        :param ant_id: List of antennae/antenna to be plotted, defaults to "all" when None, ex. ea25
        :type ant_id: list or str, optional
        :param ddi: List of ddis/ddi to be plotted, defaults to "all" when None, ex. 0
        :type ddi: list or int, optional
        :param complex_split: How to split complex beam data, cartesian (real + imag) or polar (amplitude + phase, default)
        :type complex_split: str, optional
        :param display: Display plots inline or suppress, defaults to True
        :type display: bool, optional
        :param colormap: Colormap for plots, default is viridis
        :type colormap: str, optional
        :param figure_size: 2 element array/list/tuple with the plot sizes in inches
        :type figure_size: numpy.ndarray, list, tuple, optional
        :param dpi: dots per inch to be used in plots, default is 300
        :type dpi: int, optional
        :param parallel: If True will use an existing astrohack client to produce plots in parallel, default is False
        :type parallel: bool, optional

        .. _Description:

        Produce plots from ``astrohack.holog`` results for analysis
        """
        parm_dict = {'ant': ant_id,
                     'ddi': ddi,
                     'destination': destination,
                     'complex_split': complex_split,
                     'display': display,
                     'colormap': colormap,
                     'figuresize': figure_size,
                     'dpi': dpi,
                     'parallel': parallel}

        fname = 'plot_apertures'
        parms_passed = _check_parms(fname, parm_dict, 'ant', [str, list], list_acceptable_data_types=[str],
                                    default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'ddi', [int, list],
                                                     list_acceptable_data_types=[int], default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'destination', [str], default=None)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'complex_split', [str],
                                                     acceptable_data=possible_splits, default="polar")
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'display', [bool], default=True)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'parallel', [bool], default=True)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'colormap', [str], acceptable_data=cmaps,
                                                     default='viridis')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'figuresize', [list, np.ndarray],
                                                     list_acceptable_data_types=[numbers.Number], list_len=2,
                                                     default='None', log_default_setting=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'dpi', [int], default=300)

        _parm_check_passed(fname, parms_passed)
        _create_destination_folder(parm_dict['destination'])
        _dask_general_compute(fname, self, _plot_beam_chunk, parm_dict, ['ant', 'ddi'], parallel=parallel)


class AstrohackHologFile(dict):
    """ Data Class for extracted holography data

    Data within an object of this class can be selected for further inspection or plotted for calibration diagnostics.
    """
    def __init__(self, file):
        """ Initialize an AstrohackHologFile object.
        :param file: File to be linked to this object
        :type file: str

        :return: AstrohackHologFile object
        :rtype: AstrohackHologFile
        """
        super().__init__()
        
        self.file = file
        self._meta_data = None
        self._file_is_open = False

    def __getitem__(self, key):
        return super().__getitem__(key)
    
    def __setitem__(self, key, value):
        return super().__setitem__(key, value)

    def _is_open(self):
        """ Check wether the object has opened the corresponding hack file.

        :return: True if open, else False.
        :rtype: bool
        """
        return self._file_is_open

    def _open(self, file=None, dask_load=True):
        """ Open extracted holography file.
        :param file: File to be opened, if None defaults to the previously defined file
        :type file: str, optional
        :param dask_load: Is file to be loaded with dask?, default is True
        :type dask_load: bool, optional

        :return: True if file is properly opened, else returns False
        :rtype: bool
        """
        logger = _get_astrohack_logger()

        if file is None:
            file = self.file

        try:
            _load_holog_file(holog_file=file, dask_load=dask_load, load_pnt_dict=False, holog_dict=self)
            self._file_is_open = True

        except Exception as e:
            logger.error("[AstrohackHologFile]: {}".format(e))
            self._file_is_open = False

        self._meta_data = _read_meta_data(file+'/.holog_attr')

        return self._file_is_open

    def summary(self):
        """ Prints summary of the AstrohackHologFile object, with available data, attributes and available methods
        """
        _print_summary_header(self.file)
        _print_attributes(self._meta_data)
        _print_data_contents(self, ["DDI", "Map", "Antenna"])
        _print_method_list([self.summary, self.select, self.plot_diagnostics])

    def select(self, ddi=None, map_id=None, ant_id=None):
        """ Select data on the basis of ddi, scan, ant. This is a convenience function.

        :param ddi: Data description ID, ex. 0.
        :type ddi: int
        :param map_id: Mapping ID, ex. 0.
        :type map_id: int
        :param ant_id: Antenna ID, ex. ea25.
        :type ant_id: str

        :return: Corresponding xarray dataset, or self if selection is None
        :rtype: xarray.Dataset or AstrohackHologFile
        """
        logger = _get_astrohack_logger()
        ant_id = 'ant_'+ant_id
        ddi = f'ddi_{ddi}'
        map_id = f'map_{map_id}'

        if ant_id is None or ddi is None or map_id is None:
            logger.info("[select]: No selection made ...")
            return self
        else:
            return self[ddi][map_id][ant_id]

    @property
    def meta_data(self):
        """ Retrieve AstrohackHologFile JSON metadata.

        :return: JSON metadata for this AstrohackHologFile object
        :rtype: dict
        """

        return self._meta_data

    def plot_diagnostics(self, destination, delta=0.01, ant_id=None, ddi=None, map_id=None, complex_split='polar',
                         display=True, figure_size=None, dpi=300, parallel=False):
        """ Plot diagnostic calibration plots from the holography data file.

        :param destination: Name of the destination folder to contain diagnostic plots
        :type destination: str
        :param delta: Defines a fraction of cell_size around which to look for peaks., defaults to 0.01
        :type delta: float, optional
        :param ant_id: antenna ID to use in subselection, defaults to "all" when None, ex. ea25
        :type ant_id: list or str, optional
        :param ddi: data description ID to use in subselection, defaults to "all" when None, ex. 0
        :type ddi: list or int, optional
        :param map_id: map ID to use in subselection. This relates to which antenna are in the mapping vs. scanning configuration,  defaults to "all" when None, ex. 0
        :type map_id: list or int, optional
        :param complex_split: How to split complex data, cartesian (real + imaginary) or polar (amplitude + phase), default is polar
        :type complex_split: str, optional
        :param display: Display plots inline or suppress, defaults to True
        :type display: bool, optional
        :param figure_size: 2 element array/list/tuple with the plot sizes in inches
        :type figure_size: numpy.ndarray, list, tuple, optional
        :param dpi: dots per inch to be used in plots, default is 300
        :type dpi: int, optional
        :param parallel: Run in parallel, defaults to False
        :type parallel: bool, optional

        **Additional Information**
        The visibilities extracted by extract_holog are complex due to the nature of interferometric measurements. To
        ease the visualization of the complex data it can be split into real and imaginary parts (cartesian) or in
        amplitude and phase (polar).

        .. rubric:: Available complex splitting possibilities:
        - *cartesian*: Split is done to a real part and an imaginary part in the plots
        - *polar*:     Split is done to an amplitude and a phase in the plots

        """

        # This is the default address used by Dask. Note that in the client check below, if the user has multiple
        # clients running a new client may still be spawned but only once. If run again in a notebook session the
        # local_client check will catch it. It will also be caught if the user spawns their own instance in the
        # notebook.
        DEFAULT_DASK_ADDRESS="127.0.0.1:8786"

        logger = _get_astrohack_logger()

        if parallel:
            if not distributed.client._get_global_client():
                try:
                    distributed.Client(DEFAULT_DASK_ADDRESS, timeout=2)

                except Exception:
                    from astrohack.astrohack_client import astrohack_local_client

                    logger.info("local client not found, starting ...")

                    log_parms = {'log_level': 'DEBUG'}
                    client = astrohack_local_client(cores=2, memory_limit='8GB', log_parms=log_parms)
                    logger.info(client.dashboard_link)

        parm_dict = {
            'destination': destination,
            'delta': delta,
            'ant': ant_id,
            'ddi': ddi,
            'map': map_id,
            'complex_split': complex_split,
            'display': display,
            'figuresize': figure_size,
            'dpi': dpi,
            'parallel': parallel
        }
        fname = 'plot_diagnostics'
        parms_passed = _check_parms(fname, parm_dict, 'destination', [str], default=None)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'delta', [float], default=0.01)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'ant', [str, list],
                                                     list_acceptable_data_types=[str], default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'ddi', [int, list],
                                                     list_acceptable_data_types=[int], default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'map', [int, list],
                                                     list_acceptable_data_types=[int], default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'complex_split', [str],
                                                     acceptable_data=possible_splits, default="polar")
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'display', [bool], default=True)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'figuresize', [list, np.ndarray],
                                                     list_acceptable_data_types=[numbers.Number], list_len=2,
                                                     default='None', log_default_setting=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'dpi', [int], default=300)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'parallel', [bool], default=False)

        _parm_check_passed(fname, parms_passed)
        _create_destination_folder(parm_dict['destination'])
        key_order = ["ddi", "map", "ant"]
        _dask_general_compute(fname, self, _calibration_plot_chunk, parm_dict, key_order, parallel)


class AstrohackPanelFile(dict):
    """ Data class for holography panel data.

    Data within an object of this class can be selected for further inspection, plotted or exported to FITS for analysis
    or exported to csv for panel adjustments.
    """
    def __init__(self, file):
        """ Initialize an AstrohackPanelFile object.
        :param file: File to be linked to this object
        :type file: str

        :return: AstrohackPanelFile object
        :rtype: AstrohackPanelFile
        """
        super().__init__()

        self.file = file
        self._file_is_open = False
        self._meta_data = None

    def __getitem__(self, key):
        return super().__getitem__(key)
    
    def __setitem__(self, key, value):
        return super().__setitem__(key, value)
        
    def _is_open(self):
        """ Check wether the object has opened the corresponding hack file.

        :return: True if open, else False.
        :rtype: bool
        """
        return self._file_is_open

    def _open(self, file=None):
        """ Open panel holography file.
        :param file: File to be opened, if None defaults to the previously defined file
        :type file: str, optional

        :return: True if file is properly opened, else returns False
        :rtype: bool
        """
        logger = _get_astrohack_logger()

        if file is None:
            file = self.file

        try:
            _load_panel_file(file, panel_dict=self)
            self._file_is_open = True
        except Exception as e:
            logger.error("[AstroHackPanelFile.open()]: {}".format(e))
            self._file_is_open = False

        self._meta_data = _read_meta_data(file+'/.panel_attr')

        return self._file_is_open

    def summary(self):
        """ Prints summary of the AstrohackPanelFile object, with available data, attributes and available methods
        """
        _print_summary_header(self.file)
        _print_attributes(self._meta_data)
        _print_data_contents(self, ["Antenna", "DDI"])
        _print_method_list([self.summary, self.get_antenna, self.export_screws, self.export_to_fits,
                            self.plot_antennae])

    def get_antenna(self, ant_id, ddi):
        """ Retrieve an AntennaSurface object for interaction

        :param ant_id: Antenna to be retrieved, ex. ea25.
        :type ant_id: str
        :param ddi: DDI to be retrieved for ant_id, ex. 0
        :type ddi: int

        :return: AntennaSurface object describing for further interaction
        :rtype: AntennaSurface
        """
        ant_id = 'ant_'+ant_id
        ddi = f'ddi_{ddi}'
        xds = self[ant_id][ddi]
        telescope = Telescope(xds.attrs['telescope_name'])
        return AntennaSurface(xds, telescope, reread=True)

    def export_screws(self, destination, ant_id=None, ddi=None, unit='mm', threshold=None, display=True,
                      colormap='RdBu_r', figure_size=None, dpi=300):
        """ Export screw adjustments to text files and optionally plots.

        :param destination: Name of the destination folder to contain exported screw adjustments
        :type destination: str
        :param ant_id: List of antennae/antenna to be exported, defaults to "all" when None, ex. ea25
        :type ant_id: list or str, optional
        :param ddi: List of ddis/ddi to be exported, defaults to "all" when None, ex. 0
        :type ddi: list or int, optional
        :param unit: Unit for screws adjustments, most length units supported, defaults to "mm"
        :type unit: str, optional
        :param threshold: Threshold below which data is considered negligable, value is assumed to be in the same unit as the plot, if not given defaults to 10% of the maximal deviation
        :type threshold: float, optional
        :param display: Display plots inline or suppress, defaults to True
        :type display: bool, optional
        :param colormap: Colormap for screw adjustment map, default is RdBu_r
        :type colormap: str, optional
        :param figure_size: 2 element array/list/tuple with the screw adjustment map size in inches
        :type figure_size: numpy.ndarray, list, tuple, optional
        :param dpi: Screw adjustment map resolution in pixels per inch, default is 300
        :type dpi: int, optional

        .. _Description:

        Produce the screw adjustments from ``astrohack.panel`` results to be used at the antenna site to improve the antenna surface

        """
        parm_dict = {'ant': ant_id,
                     'ddi': ddi,
                     'destination': destination,
                     'unit': unit,
                     'threshold': threshold,
                     'display': display,
                     'colormap': colormap,
                     'figuresize': figure_size,
                     'dpi': dpi}

        fname = 'export_screws'
        parms_passed = _check_parms(fname, parm_dict, 'ant', [str, list], list_acceptable_data_types=[str],
                                    default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'ddi', [int, list],
                                                     list_acceptable_data_types=[int], default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'destination', [str], default=None)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'unit', [str], acceptable_data=length_units, 
                                                     default='mm')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'threshold', [int, float], default='None')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'display', [bool], default=True)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'colormap', [str], acceptable_data=cmaps, 
                                                     default='RdBu_r')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'figuresize', [list, np.ndarray],
                                                     list_acceptable_data_types=[numbers.Number], list_len=2,
                                                     default='None', log_default_setting=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'dpi', [int], default=300)
        
        _parm_check_passed(fname, parms_passed)
        _create_destination_folder(parm_dict['destination'])
        _dask_general_compute(fname, self, _export_screws_chunk, parm_dict, ['ant', 'ddi'], parallel=False)

    def plot_antennae(self, destination, ant_id=None, ddi=None, plot_type='deviation', plot_screws=False, unit=None,
                      display=True, colormap='viridis', figure_size=None, dpi=300, parallel=False):
        """ Create diagnostic plots of antenna surfaces from panel data file.

        :param destination: Name of the destination folder to contain plots
        :type destination: str
        :param ant_id: List of antennae/antenna to be plotted, defaults to "all" when None, ex. ea25
        :type ant_id: list or str, optional
        :param ddi: List of ddis/ddi to be plotted, defaults to "all" when None, ex. 0
        :type ddi: list or int, optional
        :param plot_type: type of plot to be produced, deviation, phase, ancillary or all, default is deviation
        :type plot_type: str, optional
        :param plot_screws: Add screw positions to plot
        :type plot_screws: bool, optional
        :param unit: Unit for phase or deviation plots, defaults to "mm" for deviation and 'deg' for phase
        :type unit: str, optional
        :param display: Display plots inline or suppress, defaults to True
        :type display: bool, optional
        :param colormap: Colormap for plots, default is viridis
        :type colormap: str, optional
        :param figure_size: 2 element array/list/tuple with the plot sizes in inches
        :type figure_size: numpy.ndarray, list, tuple, optional
        :param dpi: dots per inch to be used in plots, default is 300
        :type dpi: int, optional
        :param parallel: If True will use an existing astrohack client to produce plots in parallel, default is False
        :type parallel: bool, optional

        .. _Description:

        Produce plots from ``astrohack.panel`` results to be analyzed to judge the quality of the results

        **Additional Information**
        .. rubric:: Available plot types:
        - *deviation*: Surface deviation estimated from phase and wavelength, three plots are produced for each antenna
                       and ddi combination, surface before correction, the corrections applied and the corrected
                       surface, most length units available
        - *phase*: Phase deviations over the surface, three plots are produced for each antenna and ddi combination,
                   phase before correction, the corrections applied and the corrected phase, deg and rad available as
                   units
        - *ancillary*: Two ancillary plots with useful information: The mask used to select data to be fitted, the
                       amplitude data used to derive the mask, units are irrelevant for these plots
        - *all*: All the plots listed above. In this case the unit parameter is taken to mean the deviation unit, the
                 phase unit is set to degrees
        """
        logger = _get_astrohack_logger()
        parm_dict = {'ant': ant_id,
                     'ddi': ddi,
                     'destination': destination,
                     'unit': unit,
                     'display': display,
                     'plot_type': plot_type,
                     'plot_screws': plot_screws,
                     'colormap': colormap,
                     'figuresize': figure_size,
                     'dpi': dpi,
                     'parallel': parallel}

        fname = 'plot_antennae'
        parms_passed = _check_parms(fname, parm_dict, 'ant', [str, list], list_acceptable_data_types=[str],
                                    default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'ddi', [int, list],
                                                     list_acceptable_data_types=[int], default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'destination', [str], default=None)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'plot_type', [str], acceptable_data=plot_types,
                                                     default=plot_types[0])
        if parm_dict['plot_type'] == plot_types[0]:  # Length units for deviation plots
            parms_passed = parms_passed and _check_parms(fname, parm_dict, 'unit', [str], acceptable_data=length_units,
                                                         default='mm')
        elif parm_dict['plot_type'] == plot_types[1]:  # Trigonometric units for phase plots
            parms_passed = parms_passed and _check_parms(fname, parm_dict, 'unit', [str], acceptable_data=trigo_units,
                                                         default='deg')
        elif parm_dict['plot_type'] == plot_types[2]:  # Ancillary plots, no units
            logger.info(f'[{fname}]: Unit ignored for ancillary plots')
        else:  # Unit is taken for the deviation plot, phase is then in degrees
            parms_passed = parms_passed and _check_parms(fname, parm_dict, 'unit', [str], acceptable_data=length_units,
                                                         default='mm')
            logger.info(f'[{fname}]: Unit for phase plots set to degrees')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'display', [bool], default=True)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'parallel', [bool], default=True)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'plot_screws', [bool], default=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'colormap', [str], acceptable_data=cmaps,
                                                     default='viridis')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'figuresize', [list, np.ndarray],
                                                     list_acceptable_data_types=[numbers.Number], list_len=2,
                                                     default='None', log_default_setting=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'dpi', [int], default=300)

        _parm_check_passed(fname, parms_passed)
        _create_destination_folder(parm_dict['destination'])
        _dask_general_compute(fname, self, _plot_antenna_chunk, parm_dict, ['ant', 'ddi'], parallel=parallel)

    def export_to_fits(self, destination, ant_id=None, ddi=None, parallel=False):
        """ Export contents of an Astrohack MDS file to several FITS files in the destination folder

        :param destination: Name of the destination folder to contain plots
        :type destination: str
        :param ant_id: List of antennae/antenna to be plotted, defaults to "all" when None, ex. ea25
        :type ant_id: list or str, optional
        :param ddi: List of ddis/ddi to be plotted, defaults to "all" when None, ex. 0
        :type ddi: list or int, optional
        :param parallel: If True will use an existing astrohack client to export FITS in parallel, default is False
        :type parallel: bool, optional

        .. _Description:
        Export the products from the panel mds onto FITS files to be read by other software packages

        **Additional Information**

        The FITS fils produced by this method have been tested and are known to work with CARTA and DS9
        """

        parm_dict = {'ant': ant_id,
                     'ddi': ddi,
                     'destination': destination,
                     'parallel': parallel}
        
        fname = 'export_to_fits'
        parms_passed = _check_parms(fname, parm_dict, 'ant', [str, list], list_acceptable_data_types=[str],
                                    default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'ddi', [int, list],
                                                     list_acceptable_data_types=[int], default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'destination', [str], default=None)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'parallel', [bool], default=True)

        _parm_check_passed(fname, parms_passed)
        _create_destination_folder(parm_dict['destination'])
        _dask_general_compute(fname, self, _export_to_fits_panel_chunk, parm_dict, ['ant', 'ddi'], parallel=parallel)


class AstrohackPointFile(dict):
    """ Data Class for holography pointing data.
    """

    def __init__(self, file):
        """ Initialize an AstrohackPointFile object.
        :param file: File to be linked to this object
        :type file: str

        :return: AstrohackPointFile object
        :rtype: AstrohackPointFile
        """
        super().__init__()

        self.file = file
        self._meta_data = None
        self._file_is_open = False

    def __getitem__(self, key):
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        return super().__setitem__(key, value)

    def _is_open(self):
        """ Check wether the object has opened the corresponding hack file.

        :return: True if open, else False.
        :rtype: bool
        """
        return self._file_is_open

    def _open(self, file=None, dask_load=True):
        """ Open holography pointing file.
        :param file: File to be opened, if None defaults to the previously defined file
        :type file: str, optional
        :param dask_load: Is file to be loaded with dask?, default is True
        :type dask_load: bool, optional

        :return: True if file is properly opened, else returns False
        :rtype: bool
        """
        logger = _get_astrohack_logger()

        if file is None:
            file = self.file

        try:
            _load_point_file(file=file, dask_load=dask_load, pnt_dict=self)
            self._file_is_open = True

        except Exception as e:
            logger.error("[AstrohackPointFile]: {}".format(e))
            self._file_is_open = False

        self._meta_data = _read_meta_data(file+'/.point_attr')

        return self._file_is_open

    def summary(self):
        """ Prints summary of the AstrohackPointFile object, with available data, attributes and available methods
        """
        _print_summary_header(self.file)
        _print_attributes(self._meta_data)
        _print_data_contents(self, ["Antenna"])
        _print_method_list([self.summary])


class AstrohackLocitFile(dict):
    """ Data Class for extracted gains for antenna location determination
    """

    def __init__(self, file):
        """ Initialize an AstrohackLocitFile object.
        :param file: File to be linked to this object
        :type file: str

        :return: AstrohackLocitFile object
        :rtype: AstrohackLocitFile
        """
        super().__init__()

        self.file = file
        self._meta_data = None
        self._file_is_open = False

    def __getitem__(self, key):
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        return super().__setitem__(key, value)

    def _is_open(self):
        """ Check wether the object has opened the corresponding hack file.

        :return: True if open, else False.
        :rtype: bool
        """
        return self._file_is_open

    def _open(self, file=None, dask_load=True):
        """ Open antenna location file.
        :param file: File to be opened, if None defaults to the previously defined file
        :type file: str, optional
        :param dask_load: Is file to be loaded with dask?, default is True
        :type dask_load: bool, optional

        :return: True if file is properly opened, else returns False
        :rtype: bool
        """
        logger = _get_astrohack_logger()

        if file is None:
            file = self.file

        try:
            _load_locit_file(file=file, dask_load=dask_load, locit_dict=self)
            self._file_is_open = True

        except Exception as e:
            logger.error("[AstrohackLocitFile]: {}".format(e))
            self._file_is_open = False

        self._meta_data = _read_meta_data(file+'/.locit_attr')

        return self._file_is_open

    def print_source_table(self):
        """ Prints a table with the sources observed for antenna location determination
        """
        alignment = 'l'
        print("\nSources:")
        table = PrettyTable()
        table.field_names = ['Id', 'Name', 'RA FK5', 'DEC FK5', 'RA precessed', 'DEC precessed']
        for source in self['obs_info']['src_dict'].values():
            table.add_row([source['id'], source['name'], _rad_to_hour_str(source['fk5'][0]),
                           _rad_to_deg_str(source['fk5'][1]), _rad_to_hour_str(source['precessed'][0]),
                           _rad_to_deg_str(source['precessed'][1])])
        table.align = alignment
        print(table)

    def print_antenna_table(self):
        """ Prints a table of the antennas included in the dataset
        """
        alignment = 'l'
        print(f"\n{self['obs_info']['telescope_name']} Antennae:")
        table = PrettyTable()
        table.field_names = ['Name', 'Station', 'Longitude', 'Latitude', 'Distance to earth center [m]']
        for antenna in self['ant_info'].values():
            if antenna['reference']:
                table.add_row([antenna['name']+' (ref)', antenna['station'], _rad_to_deg_str(antenna['longitude']),
                               _rad_to_deg_str(antenna['latitude']), antenna['radius']])
            else:
                table.add_row([antenna['name'], antenna['station'], _rad_to_deg_str(antenna['longitude']),
                              _rad_to_deg_str(antenna['latitude']), antenna['radius']])
        table.align = alignment
        print(table)

    def plot_source_positions(self, destination, display_labels=False, precessed=False, display=True, figure_size=None,
                              dpi=300):
        """ Plot source positions in either FK5 or precessed right ascension and declination.

        :param destination: Name of the destination folder to contain plot
        :type destination: str
        :param display_labels: Add source labels to the plot, defaults to False
        :type display_labels: bool, optional
        :param precessed: Plot in precessed coordinates? defaults to False (FK5)
        :type precessed: bool, optional
        :param display: Display plots inline or suppress, defaults to True
        :type display: bool, optional
        :param figure_size: 2 element array/list/tuple with the plot sizes in inches
        :type figure_size: numpy.ndarray, list, tuple, optional
        :param dpi: dots per inch to be used in plots, default is 300
        :type dpi: int, optional

        .. _Description:

        Plot the sources on the source list to a full 24 hours 180 degrees flat 2D representation of the full sky.
        If precessed is set to True the coordinates precessd to the midpoint of the observations is plotted, otherwise
        the FK5 coordinates are plotted.
        The source names can be plotted next to their positions if label is True, however plots may become too crowded
        if that is the case.

        """
        parm_dict = {'destination': destination,
                     'precessed': precessed,
                     'display': display,
                     'figuresize': figure_size,
                     'label': display_labels,
                     'dpi': dpi}

        fname = 'plot_source_positions'
        parms_passed = _check_parms(fname, parm_dict, 'destination', [str], default=None)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'display', [bool], default=True)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'precessed', [bool], default=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'label', [bool], default=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'figuresize', [list, np.ndarray],
                                                     list_acceptable_data_types=[numbers.Number], list_len=2,
                                                     default='None', log_default_setting=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'dpi', [int], default=300)

        _parm_check_passed(fname, parms_passed)
        _create_destination_folder(parm_dict['destination'])

        if precessed:
            filename = destination + '/locit_source_table_precessed.png'
            time_range = self['obs_info']['time_range']
            obs_midpoint = (time_range[1] + time_range[0]) / 2.
        else:
            filename = destination + '/locit_source_table_fk5.png'
            obs_midpoint = None
        _plot_source_table(filename, self['obs_info']['src_dict'], precessed=precessed, obs_midpoint=obs_midpoint,
                           display=display, figure_size=figure_size, dpi=dpi, label=display_labels)
        return

    def plot_antenna_positions(self, destination, display_stations=True, display=True, figure_size=None, dpi=300):
        """ Plot antenna positions.

        :param destination: Name of the destination folder to contain plot
        :type destination: str
        :param display_stations: Add station names to the plot, defaults to True
        :type display_stations: bool, optional
        :param display: Display plots inline or suppress, defaults to True
        :type display: bool, optional
        :param figure_size: 2 element array/list/tuple with the plot sizes in inches
        :type figure_size: numpy.ndarray, list, tuple, optional
        :param dpi: dots per inch to be used in plots, default is 300
        :type dpi: int, optional

        .. _Description:


        """
        parm_dict = {'destination': destination,
                     'display': display,
                     'figuresize': figure_size,
                     'stations': display_stations,
                     'dpi': dpi}

        fname = 'plot_source_positions'
        parms_passed = _check_parms(fname, parm_dict, 'destination', [str], default=None)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'display', [bool], default=True)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'precessed', [bool], default=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'stations', [bool], default=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'figuresize', [list, np.ndarray],
                                                     list_acceptable_data_types=[numbers.Number], list_len=2,
                                                     default='None', log_default_setting=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'dpi', [int], default=300)

        _parm_check_passed(fname, parms_passed)
        _create_destination_folder(parm_dict['destination'])

        filename = destination + '/locit_antenna_positions.png'
        _plot_antenna_table(filename, self['ant_info'], self['obs_info']['array_center_lonlatrad'], display=display,
                            figure_size=figure_size, dpi=dpi, stations=display_stations)
        return

    def summary(self):
        """ Prints summary of the AstrohackLocitFile object, with available data, attributes and available methods
        """
        _print_summary_header(self.file)
        _print_attributes(self._meta_data)
        _print_data_contents(self, ["Antenna", "Contents"])
        _print_method_list([self.summary, self.print_source_table, self.print_antenna_table,
                            self.plot_source_positions, self.plot_antenna_positions])


class AstrohackPositionFile(dict):
    """ Data Class for extracted antenna location determination
    """

    def __init__(self, file):
        """ Initialize an AstrohackPositionFile object.
        :param file: File to be linked to this object
        :type file: str

        :return: AstrohackPositionFile object
        :rtype: AstrohackPositionFile
        """
        super().__init__()

        self.file = file
        self._meta_data = None
        self._file_is_open = False

    def __getitem__(self, key):
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        return super().__setitem__(key, value)

    def _is_open(self):
        """ Check wether the object has opened the corresponding hack file.

        :return: True if open, else False.
        :rtype: bool
        """
        return self._file_is_open

    def _open(self, file=None, dask_load=True):
        """ Open antenna location file.
        :param file: File to be opened, if None defaults to the previously defined file
        :type file: str, optional
        :param dask_load: Is file to be loaded with dask?, default is True
        :type dask_load: bool, optional

        :return: True if file is properly opened, else returns False
        :rtype: bool
        """
        logger = _get_astrohack_logger()

        if file is None:
            file = self.file

        self._meta_data = _read_meta_data(file + '/.position_attr')
        self.combined = self._meta_data['combine_ddis']

        try:
            _load_position_file(file=file, dask_load=dask_load, position_dict=self,
                                combine=self.combined)
            self._file_is_open = True

        except Exception as e:
            logger.error("[AstrohackpositionFile]: {}".format(e))
            self._file_is_open = False

        return self._file_is_open

    def export_fit_results(self, destination, position_unit='m', time_unit='hour',
                           delay_unit='nsec'):
        """ Export antenna position fit results to a text file.

        :param destination: Name of the destination folder to contain exported fit results
        :type destination: str
        :param position_unit: Unit to list position fit results, defaults to 'm'
        :type position_unit: str, optional
        :param time_unit: Unit for time in position fit results, defaults to 'hour'
        :type time_unit: str, optional
        :param delay_unit: Unit for delays, defaults to 'ns'
        :type delay_unit: str, optional

        .. _Description:

        Produce a text file with the fit results from astrohack.locit for better determination of antenna locations.
        """
        
        parm_dict = {'destination': destination,
                     'position_unit': position_unit,
                     'delay_unit': delay_unit,
                     'time_unit': time_unit}

        fname = 'export_fit_results'
        parms_passed = True
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'destination', [str],
                                                     default=None)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'position_unit', [str],
                                                     acceptable_data=length_units, default='m')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'time_unit', [str],
                                                     acceptable_data=time_units, default='hour')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'delay_unit', [str],
                                                     acceptable_data=time_units, default='nsec')
        _parm_check_passed(fname, parms_passed)
        _create_destination_folder(parm_dict['destination'])
        _export_fit_results(self, parm_dict)

    def plot_sky_coverage(self, destination, ant_id=None, ddi=None, time_unit='hour', angle_unit='deg', display=True,
                          figure_size=None, dpi=300, parallel=False):
        """ Plot the sky coverage of the data used for antenna position fitting

        :param destination: Name of the destination folder to contain the plots
        :type destination: str
        :param ant_id: List of antennae/antenna to be plotted, defaults to "all" when None, ex. ea25
        :type ant_id: list or str, optional
        :param ddi: List of ddis/ddi to be plotted, defaults to "all" when None, ex. 0
        :type ddi: list or int, optional
        :param angle_unit: Unit for angle in plots, defaults to 'deg'
        :type angle_unit: str, optional
        :param time_unit: Unit for time in plots, defaults to 'hour'
        :type time_unit: str, optional
        :param display: Display plots inline or suppress, defaults to True
        :type display: bool, optional
        :param figure_size: 2 element array/list/tuple with the plot size in inches
        :type figure_size: numpy.ndarray, list, tuple, optional
        :param dpi: plot resolution in pixels per inch, default is 300
        :type dpi: int, optional
        :param parallel: If True will use an existing astrohack client to produce plots in parallel, default is False
        :type parallel: bool, optional

        .. _Description:

        This method produces 4 plots for each selected antenna and DDI. These plots are:
        1) Time vs Elevation
        2) Time vs Hour Angle
        3) Time vs Declination
        4) Hour Angle vs Declination

        These plots are intended to display the coverage of the sky of the fitted data

        """
        
        parm_dict = {'ant': ant_id,
                     'ddi': ddi,
                     'destination': destination,
                     'time_unit': time_unit,
                     'angle_unit': angle_unit,
                     'display': display,
                     'figure_size': figure_size,
                     'dpi': dpi,
                     'parallel': parallel}

        fname = 'plot_sky_coverage'
        parms_passed = _check_parms(fname, parm_dict, 'ant', [str, list],
                                    list_acceptable_data_types=[str], default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'ddi', [int, list],
                                                     list_acceptable_data_types=[int], default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'destination', [str],
                                                     default=None)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'time_unit', [str], acceptable_data=time_units,
                                                     default='hour')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'angle_unit', [str], acceptable_data=trigo_units,
                                                     default='deg')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'display', [bool], default=True)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'figuresize', [list, np.ndarray],
                                                     list_acceptable_data_types=[numbers.Number], list_len=2,
                                                     default='None', log_default_setting=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'dpi', [int], default=300)

        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'parallel', [bool],
                                                     default=False)
        _parm_check_passed(fname, parms_passed)
        _create_destination_folder(parm_dict['destination'])
        parm_dict['combined'] = self.combined
        if self.combined:
            _dask_general_compute(fname, self, _plot_sky_coverage_chunk, parm_dict, ['ant'], parallel=parallel)
        else:
            _dask_general_compute(fname, self, _plot_sky_coverage_chunk, parm_dict, ['ant', 'ddi'], parallel=parallel)

    def plot_delays(self, destination, ant_id=None, ddi=None, time_unit='hour', angle_unit='deg', delay_unit='nsec',
                    plot_fit=True, display=True, figure_size=None, dpi=300, parallel=False):
        """ Plot the delays used for antenna position fitting and optionally the resulting fit.

        :param destination: Name of the destination folder to contain the plots
        :type destination: str
        :param ant_id: List of antennae/antenna to be plotted, defaults to "all" when None, ex. ea25
        :type ant_id: list or str, optional
        :param ddi: List of ddis/ddi to be plotted, defaults to "all" when None, ex. 0
        :type ddi: list or int, optional
        :param angle_unit: Unit for angle in plots, defaults to 'deg'
        :type angle_unit: str, optional
        :param time_unit: Unit for time in plots, defaults to 'hour'
        :type time_unit: str, optional
        :param delay_unit: Unit for delay in plots, defaults to 'nsec'
        :type delay_unit: str, optional
        :param plot_fit: Plot the fit results alongside the data.
        :type plot_fit: bool, optional
        :param display: Display plots inline or suppress, defaults to True
        :type display: bool, optional
        :param figure_size: 2 element array/list/tuple with the plot size in inches
        :type figure_size: numpy.ndarray, list, tuple, optional
        :param dpi: plot resolution in pixels per inch, default is 300
        :type dpi: int, optional
        :param parallel: If True will use an existing astrohack client to produce plots in parallel, default is False
        :type parallel: bool, optional

        .. _Description:

        This method produces 4 plots for each selected antenna and DDI. These plots are:
        1) Time vs Delays
        2) Elevation vs Delays
        3) Hour Angle vs Delays
        4) Declination vs Delays

        These plots are intended to display the gain variation with the 4 relevant parameters for the fitting and also
        asses the quality of the position fit.

        """

        parm_dict = {'ant': ant_id,
                     'ddi': ddi,
                     'destination': destination,
                     'time_unit': time_unit,
                     'angle_unit': angle_unit,
                     'delay_unit': delay_unit,
                     'plot_fit': plot_fit,
                     'display': display,
                     'figure_size': figure_size,
                     'dpi': dpi,
                     'parallel': parallel}

        fname = 'plot_delays'
        parms_passed = _check_parms(fname, parm_dict, 'ant', [str, list],
                                    list_acceptable_data_types=[str], default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'ddi', [int, list],
                                                     list_acceptable_data_types=[int], default='all')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'destination', [str],
                                                     default=None)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'time_unit', [str], acceptable_data=time_units,
                                                     default='hour')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'angle_unit', [str], acceptable_data=trigo_units,
                                                     default='deg')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'delay_unit', [str], acceptable_data=time_units,
                                                     default='nsec')
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'plot_fit', [bool], default=True)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'display', [bool], default=True)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'figuresize', [list, np.ndarray],
                                                     list_acceptable_data_types=[numbers.Number], list_len=2,
                                                     default='None', log_default_setting=False)
        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'dpi', [int], default=300)

        parms_passed = parms_passed and _check_parms(fname, parm_dict, 'parallel', [bool],
                                                     default=False)
        _parm_check_passed(fname, parms_passed)
        _create_destination_folder(parm_dict['destination'])

        parm_dict['combined'] = self.combined
        if self.combined:
            _dask_general_compute(fname, self, _plot_delays_chunk, parm_dict, ['ant'], parallel=parallel)
        else:
            _dask_general_compute(fname, self, _plot_delays_chunk, parm_dict, ['ant', 'ddi'], parallel=parallel)

    def summary(self):
        """ Prints summary of the AstrohackpositionFile object, with available data, attributes and available methods
        """
        _print_summary_header(self.file)
        _print_attributes(self._meta_data)
        if self.combined:
            _print_data_contents(self, ["Antenna"])
        else:
            _print_data_contents(self, ["Antenna", "Contents"])
        _print_method_list([self.summary, self.export_fit_results, self.plot_sky_coverage, self.plot_delays])
