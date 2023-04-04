import os
import dask
import xarray as xr
import shutil

from astrohack._classes.antenna_surface import AntennaSurface
from astrohack._classes.telescope import Telescope
from astrohack._classes.base_panel import panelkinds
from astrohack._utils._constants import length_units
from astrohack._utils._io import _load_image_xds, _aips_holog_to_xds, check_if_file_will_be_overwritten, check_if_file_exists
from astrohack._utils._panel import _external_to_internal_parameters, _correct_phase
import numpy as np

from astrohack._utils._logger._astrohack_logger import _get_astrohack_logger
from astrohack._utils._parm_utils._check_parms import _check_parms
from astrohack._utils._utils import _remove_suffix


def panel(image_name, panel_name=None, cutoff=0.2, panel_kind=None, unit='mm', panel_margins=0.2, save_mask=False,
          save_deviations=True, save_phase=False, parallel=False, sel_ddi=None, overwrite=False):
    """
    Process holographies to produce screw adjustments for panels, several data products are also produced in the process
    Args:
        image_name: Input holography data, can be from astrohack.holog, but also preprocessed AIPS data
        panel_name: Name for the output directory structure containing the products
        
        cutoff: Cut off in amplitude for the physical deviation fitting, None means 20%
        panel_kind: Type of fitting function used to fit panel surfaces, defaults to corotated_paraboloid for ringed
                    telescopes
        unit: Unit for panel adjustments
        save_mask: Save plot of the mask derived from amplitude cutoff to a png file
        save_deviations: Save plot of physical deviations to a png file
        save_phase: Save plot of phases to a png file
        parallel: Run chunks of processing in parallel
        panel_margins: Margin to be ignored at edges of panels when fitting
        sel_ddi: Which DDIs are to be processed by panel, None means all of them
    """
    
    logger = _get_astrohack_logger()
    
    panel_params = check_panel_parms(image_name, panel_name, cutoff, panel_kind, unit, panel_margins, save_mask,
                                     save_deviations, save_phase, parallel, sel_ddi, overwrite)
          
    check_if_file_exists(panel_params['image_name'])
    check_if_file_will_be_overwritten(panel_params['panel_name'], panel_params['overwrite'])

    if os.path.exists(panel_params['image_name']+'/.aips'):
        panel_params['origin'] = 'AIPS'
        _panel_chunk(panel_params)

    else:
        panel_chunk_params = panel_params
        panel_chunk_params['origin'] = 'astrohack'
        delayed_list = []

        antennae = os.listdir(panel_chunk_params['image_name'])
        count = 0
        for antenna in antennae:
            if 'ant_' in antenna:
                panel_chunk_params['antenna'] = antenna
                
                if panel_chunk_params['sel_ddi'] == "all":
                    panel_chunk_params['sel_ddi'] = os.listdir(panel_chunk_params['image_name']+'/'+antenna)

                for ddi in panel_chunk_params['sel_ddi'] :
                    if 'ddi_' in ddi:
                        logger.info(f"Processing {ddi} for {antenna}")
                        panel_chunk_params['ddi'] = ddi
                        if parallel:
                            delayed_list.append(dask.delayed(_panel_chunk)(dask.delayed(panel_chunk_params)))
                        else:
                            _panel_chunk(panel_chunk_params)
                        count += 1
        if parallel:
            dask.compute(delayed_list)

        if count == 0:
            logger.warning("No data to process")


def _panel_chunk(panel_chunk_params):
    """
    Process a chunk of the holographies, usually a chunk consists of an antenna over a ddi
    Args:
        panel_chunk_params: dictionary of inputs
    """
    if panel_chunk_params['origin'] == 'AIPS':
        inputxds = xr.open_zarr(panel_chunk_params['image_name'])
        telescope = Telescope(inputxds.attrs['telescope_name'])
        panel_chunk_params['antenna'] = inputxds.attrs['ant_name']

    else:
        inputxds = _load_image_xds(panel_chunk_params['image_name'],
                                   panel_chunk_params['antenna'],
                                   panel_chunk_params['ddi'])

        inputxds.attrs['AIPS'] = False

        if inputxds.attrs['telescope_name'] == "ALMA":
            tname = inputxds.attrs['telescope_name']+'_'+inputxds.attrs['ant_name'][0:2]
            telescope = Telescope(tname)
        elif inputxds.attrs['telescope_name'] == "EVLA":
            tname = "VLA"
            telescope = Telescope(tname)
        else:
            raise ValueError('Unsuported telescope {0:s}'.format(inputxds.attrs['telescope_name']))

    surface = AntennaSurface(inputxds, telescope, panel_chunk_params['cutoff'], panel_chunk_params['panel_kind'],
                             panel_margins=panel_chunk_params['panel_margins'])

    surface.compile_panel_points()
    surface.fit_surface()
    surface.correct_surface()
    
    base_name = panel_chunk_params['panel_name'] + '/' + panel_chunk_params['antenna']

    os.makedirs(name=base_name, exist_ok=True)

    base_name += "/"
    xds = surface.export_xds()
    xds.to_zarr(base_name+'xds.zarr', mode='w')
    surface.export_screw_adjustments(base_name + "screws.txt", unit=panel_chunk_params['unit'])
    
    if panel_chunk_params['save_mask']:
        surface.plot_surface(filename=base_name + "mask.png", mask=True, screws=True)
    
    if panel_chunk_params['save_deviations']:
        surface.plot_surface(filename=base_name + "surface.png")
    
    if panel_chunk_params['save_phase']:
        surface.plot_surface(filename=base_name + "phase.png", plotphase=True)


def create_phase_model(npix, parameters, wavelength, telescope, cellxy):
    """
    Create a phase model with npix by npix size according to the given parameters
    Args:
        npix: Number of pixels in each size of the model
        parameters: Parameters for the phase model in the units described in _phase_fitting
        wavelength: Observing wavelength, in meters
        telescope: Telescope object containing the optics parameters
        cellxy: Map cell spacing, in meters

    Returns:

    """
    iNPARameters = _external_to_internal_parameters(parameters, wavelength, telescope, cellxy)
    dummyphase = np.zeros((npix, npix))

    _, model = _correct_phase(dummyphase, cellxy, iNPARameters, telescope.magnification, telescope.focus,
                              telescope.surp_slope)
    return model


def aips_holog_to_astrohack(amp_image, dev_image, telescope_name, holog_name, overwrite=False):
    check_if_file_exists(amp_image)
    check_if_file_exists(dev_image)
    check_if_file_will_be_overwritten(holog_name, overwrite)

    xds = _aips_holog_to_xds(amp_image, dev_image)
    xds.attrs['telescope_name'] = telescope_name
    if os.path.exists(holog_name):
        shutil.rmtree(holog_name, ignore_errors=False, onerror=None)
    xds.to_zarr(holog_name, mode='w', compute=True, consolidated=True)
    aips_mark = open(holog_name+'/.aips', 'w')
    aips_mark.close()


def check_panel_parms(image_name, panel_name, cutoff, panel_kind, unit, panel_margins, save_mask, save_deviations,
                      save_phase, parallel, sel_ddi, overwrite):

    panel_params = {'image_name': image_name,
                    'panel_name': panel_name,
                    'cutoff': cutoff,
                    'panel_kind': panel_kind,
                    'unit': unit,
                    'panel_margins': panel_margins,
                    'save_mask': save_mask,
                    'save_deviations': save_deviations,
                    'save_phase': save_phase,
                    'parallel': parallel,
                    'sel_ddi': sel_ddi,
                    'overwrite': overwrite
                    }
                          
    #### Parameter Checking ####
    logger = _get_astrohack_logger()
    parms_passed = True
    
    parms_passed = parms_passed and _check_parms(panel_params, 'image_name', [str], default=None)
    base_name = _remove_suffix(panel_params['image_name'], '.image.zarr')
    parms_passed = parms_passed and _check_parms(panel_params, 'panel_name', [str], default=base_name+'.panel.zarr')
    parms_passed = parms_passed and _check_parms(panel_params, 'cutoff', [float], acceptable_range=[0, 1], default=0.2)
    parms_passed = parms_passed and _check_parms(panel_params, 'panel_kind', [str], acceptable_data=panelkinds, default="rigid")
    parms_passed = parms_passed and _check_parms(panel_params, 'unit', [str], acceptable_data=length_units, default="mm")
    parms_passed = parms_passed and _check_parms(panel_params, 'panel_margins', [float], acceptable_range=[0, 0.5], default=0.2)
    parms_passed = parms_passed and _check_parms(panel_params, 'save_mask', [bool], default=False)
    parms_passed = parms_passed and _check_parms(panel_params, 'save_deviations', [bool], default=False)
    parms_passed = parms_passed and _check_parms(panel_params, 'save_phase', [bool], default=False)
    parms_passed = parms_passed and _check_parms(panel_params, 'parallel', [bool], default=False)
    parms_passed = parms_passed and _check_parms(panel_params, 'sel_ddi', [list, np.array], list_acceptable_data_types=[int, np.int], default='all')
    parms_passed = parms_passed and _check_parms(panel_params, 'overwrite', [bool], default=False)

    if not parms_passed:
        logger.error("extract_holog parameter checking failed.")
        raise Exception("extract_holog parameter checking failed.")
    
    return panel_params


