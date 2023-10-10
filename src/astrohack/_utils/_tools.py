import json

import numpy as np
from prettytable import PrettyTable
from textwrap import fill
from astropy.coordinates import EarthLocation, AltAz, HADec, SkyCoord
from astropy.time import Time
import astropy.units as units

from astrohack._utils._logger._astrohack_logger import _get_astrohack_logger
from astrohack._utils._conversion import _convert_unit
from astrohack._utils._algorithms import _significant_digits


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        
        elif isinstance(obj, np.floating):
            return float(obj)
        
        elif isinstance(obj, np.integer):
            return int(obj)

        elif isinstance(obj, NoneType):
            return "None"


        return json.JSONEncoder.default(self, obj)


def _casa_time_to_mjd(times):
    corrected = times/3600/24.0
    return corrected


def _altaz_to_hadec(az, el, lat):
    """Convert AltAz to HA + DEC coordinates.

    (HA [rad], dec [rad])

    Provided by D. Faes DSOC
    """
    sinlat = np.sin(lat)
    coslat = np.cos(lat)
    sinel  = np.sin(el)
    cosel  = np.cos(el)
    cosaz  = np.cos(az)
    sindec = sinlat*sinel+coslat*cosel*cosaz
    dec = np.arcsin(sindec)
    argarccos = (sinel-sinlat*sindec)/(coslat*np.cos(dec))
    lt1 = argarccos < -1
    argarccos[lt1] = -1.0
    ha = np.arccos(argarccos)
    return ha, dec


def _hadec_to_altaz(ha, dec, lat):
    """Convert HA + DEC to Alt + Az coordinates.

    (HA [rad], dec [rad])

    Provided by D. Faes DSOC
    """
    #
    sinha = np.sin(ha)
    cosha = np.cos(ha)
    coslat = np.cos(lat)
    sinlat = np.sin(lat)
    bottom = cosha * sinlat - np.tan(dec) * coslat
    sin_el = sinlat * np.sin(dec) + coslat * np.cos(dec) * cosha
    az = np.arctan2(sinha, bottom)
    el = np.arcsin(sin_el)
    az += np.pi  # formula is starting from *South* instead of North
    if az > 2*np.pi:
        az -= 2*np.pi
    return az, el


def _hadec_to_elevation(hadec, lat):
    """Convert HA + DEC to elevation.

    (HA [rad], dec [rad])

    Provided by D. Faes DSOC
    """
    #
    cosha = np.cos(hadec[0])
    coslat = np.cos(lat)
    sinlat = np.sin(lat)
    sin_el = sinlat * np.sin(hadec[1]) + coslat * np.cos(hadec[1]) * cosha
    el = np.arcsin(sin_el)
    return el


def _altaz_to_hadec_astropy(az, el, time, x_ant, y_ant, z_ant):
    """
    Astropy convertion from Alt Az to Ha Dec, seems to be more precise but it is VERY slow
    Args:
        az: Azimuth
        el: Elevation
        time: Time
        x_ant: Antenna x position in geocentric coordinates
        y_ant: Antenna y position in geocentric coordinates
        z_ant: Antenna z position in geocentric coordinates

    Returns: Hour angle and Declination

    """
    ant_pos = EarthLocation.from_geocentric(x_ant, y_ant, z_ant, 'meter')
    mjd_time = Time(_casa_time_to_mjd(time), format='mjd', scale='utc')
    az_el_frame = AltAz(location=ant_pos, obstime=mjd_time)
    ha_dec_frame = HADec(location=ant_pos, obstime=mjd_time)
    azel_coor = SkyCoord(az*units.rad, el*units.rad, frame=az_el_frame)
    ha_dec_coor = azel_coor.transform_to(ha_dec_frame)
    
    return ha_dec_coor.ha, ha_dec_coor.dec


def _remove_suffix(input_string, suffix):
    """
    Removes extension suffixes from file names
    Args:
        input_string: filename string
        suffix: The suffix to be removed

    Returns: the input string minus suffix

    """
    if suffix and input_string.endswith(suffix):
        return input_string[:-len(suffix)]
        
    return input_string


# DEPRECATED
def _jsonify(holog_obj):
    """ Convert holog_obs_description dictionay to json format. This just means converting numpy.ndarry
        entries to string lists.

    # DEPRECATED

    :param holog_obj: holog_obs_description dictionary.
    :type holog_obj: dict
    :param holog_obj: holog_obs_description dictionary.
    :type holog_obj: dict
    """
    for ddi_key, ddi_value in holog_obj.items():
        for map_key, map_value in holog_obj[ddi_key].items():
            for attr_key, attr_value in holog_obj[ddi_key][map_key].items():
                if "scans" in attr_key:
                    holog_obj[ddi_key][map_key][attr_key] = list(map(str, attr_value))
                
                elif "ant" in attr_key:
                    for ant_key, ant_value in holog_obj[ddi_key][map_key][attr_key].items():
                        holog_obj[ddi_key][map_key][attr_key][ant_key] = list(map(str, ant_value))

                else:
                    pass


def _add_prefix(input_string, prefix):
    """
    Adds a prefix to a string filename, if the filename is a path with /, adds the prefix to the actual filename at the
    end of the path
    Args:
        input_string: filename or file path
        prefix: prefix to be added to the filename

    Returns: filename or path plus prefix added to the filename

    """
    wrds = input_string.split('/')
    wrds[-1] = prefix+'_'+wrds[-1]
    return '/'.join(wrds)


def _print_holog_obs_dict(holog_obj):
    logger = _get_astrohack_logger()
    
    OPEN_DICT  = ":{"
    CLOSE_DICT = "}"
    
    OPEN_LIST  = ":["
    CLOSE_LIST = "]"

    logger.info("| ********************************************************** |")
    logger.info("|                 HOLOG OBSERVATION DICTIONARY               |")
    logger.info("| ********************************************************** |\n\n")
    
    for ddi_key, ddi_value in holog_obj.items():
        logger.info("{ddi_key} {open_bracket}".format(ddi_key=ddi_key, open_bracket=OPEN_DICT))
        for map_key, map_value in holog_obj[ddi_key].items():
            logger.info("{map_key: >10} {open_bracket}".format(map_key=map_key, open_bracket=OPEN_DICT))
            for attr_key, attr_value in holog_obj[ddi_key][map_key].items():
                if "scans" in attr_key:
                    logger.info("{attr_key: >12} {open_list}".format(attr_key=attr_key, open_list=OPEN_LIST))
    
                    scan_list = ", ".join(list(map(str, holog_obj[ddi_key][map_key][attr_key])))
                    logger.info("{scan: >18}".format(scan=scan_list))                                   # The print just ification in notebook is weird on this and seems to move according to list length ...
                    logger.info("{close_bracket: >10}".format(close_bracket=CLOSE_LIST))
                
                elif "ant" in attr_key:
                    logger.info("{attr_key: >12} {open_bracket}".format(attr_key=attr_key, open_bracket=OPEN_DICT))
                    for ant_key, ant_value in holog_obj[ddi_key][map_key][attr_key].items():
                        logger.info("{ant_key: >18} {open_list}".format(ant_key=ant_key, open_list=OPEN_LIST))
                        logger.info("{antenna: >25}".format( antenna=", ".join(ant_value) ))
                        logger.info("{close_list: >15}".format(close_list=CLOSE_LIST))
                    
                    logger.info("{close_bracket: >10}".format(close_bracket=CLOSE_DICT))

                else:
                    pass
        logger.info("{close_bracket: >5}".format(close_bracket=CLOSE_DICT))
        
    logger.info("{close_bracket}".format(close_bracket=CLOSE_DICT))


def _parm_to_list(caller, parm, data_dict, prefix):
    """
    Transforms a string parameter to a list if parameter is all or a single string
    Args:
        parm: string or list parameter
        data_dict: Dictionary in which to search for data to be listed
        prefix: prefix to be added to parameter

    Returns: parameter converted to a list

    """
    logger = _get_astrohack_logger()
    
    if parm == 'all':
        oulist = list(data_dict.keys())
    elif isinstance(parm, str):
        oulist = [_add_prefix(parm, prefix)]
    elif isinstance(parm, int):
        oulist = [f'{prefix}_{parm}']
    elif isinstance(parm, (list, tuple)):
        oulist = []
        for item in parm:
            if isinstance(item, str):
                oulist.append(_add_prefix(item, prefix))
            elif isinstance(item, int):
                oulist.append(f'{prefix}_{item}')
            else:
                msg = f'[{caller}]: cannot interpret parameter {item} of type {type(item)}'
                logger.error(msg)
                raise Exception(msg)
    else:
        msg = f'[{caller}] cannot interpret parameter {parm} of type {type(parm)}'
        logger.error(msg)
        raise Exception(msg)
        
    return oulist


def _split_pointing_table(ms_name, antennas):
    """ Split pointing table to contain only specified antennas

    :param ms_name: Measurement file
    :type ms_name: str
    :param antennas: List of antennas to sub-select on.
    :type antennas: list (str)
    """

    # Need to get thea antenna-id values for teh input antenna names. This is not available in the POINTING table
    # so we build the values from the ANTENNA table.
    
    table = "/".join((ms_name, 'ANTENNA'))
    query = 'select NAME from {table}'.format(table=table)
    
    ant_names = np.array(tables.taql(query).getcol('NAME'))
    ant_id = np.arange(len(ant_names))
    
    query_ant = np.searchsorted(ant_names, antennas)
    
    ant_list = " or ".join(["ANTENNA_ID=={ant}".format(ant=ant) for ant in query_ant])
    
    # Build new POINTING table from the sub-selection of antenna values.
    table = "/".join((ms_name, "POINTING"))    
    
    selection = "select * from {table} where {antennas}".format(table=table, antennas=ant_list)
    
    reduced = tables.taql(selection)
    
    # Copy the new table to the source measurement set.
    table = "/".join((ms_name, 'REDUCED'))
    
    reduced.copy(newtablename='{table}'.format(table=table), deep=True)
    reduced.done()
    
    # Remove old POINTING table.
    shutil.rmtree("/".join((ms_name, 'POINTING')))
    
    # Rename REDUCED table to POINTING
    tables.tablerename(
        tablename="/".join((ms_name, 'REDUCED')), 
        newtablename="/".join((ms_name, 'POINTING'))
    )


def _stokes_axis_to_fits_header(header, iaxis):
    """
    Inserts a dedicated stokes axis in the header at iaxis
    Args:
        header: The header to add the axis description to
        iaxis: The position of the axis in the data

    Returns: The augmented header

    """
    header[f'NAXIS{iaxis}'] = 4
    header[f'CRVAL{iaxis}'] = 1.0
    header[f'CDELT{iaxis}'] = 1.0
    header[f'CRPIX{iaxis}'] = 1.0
    header[f'CROTA{iaxis}'] = 0.
    header[f'CTYPE{iaxis}'] = 'STOKES'
    header[f'CUNIT{iaxis}'] = ''

    return header


def _axis_to_fits_header(header, axis, iaxis, axistype, unit):
    """
    Process an axis to create a FITS compatible linear axis description
    Args:
        header: The header to add the axis description to
        axis: The axis to be described in the header
        iaxis: The position of the axis in the data
        axistype: Axis type to be displayed in the fits header

    Returns: The augmented header

    """
    logger = _get_astrohack_logger()
    naxis = len(axis)
    if naxis == 1:
        inc = axis[0]
    else:
        inc = axis[1] - axis[0]
        if inc == 0:
            logger.error('[_axis_to_fits_header]: Axis increment is zero valued')
            raise Exception
        absdiff = abs((axis[-1]-axis[-2])-inc)/inc
        if absdiff > 1e-7:
            logger.error('[_axis_to_fits_header]: Axis is not linear!')
            raise Exception

    ref = naxis//2
    val = axis[ref]

    header[f'NAXIS{iaxis}'] = naxis
    header[f'CRVAL{iaxis}'] = val
    header[f'CDELT{iaxis}'] = inc
    header[f'CRPIX{iaxis}'] = ref
    header[f'CROTA{iaxis}'] = 0.
    header[f'CTYPE{iaxis}'] = axistype
    header[f'CUNIT{iaxis}'] = unit
    return header


def _resolution_to_fits_header(header, resolution):
    """
    Adds resolution information to standard header keywords: BMAJ, BMIN and BPA
    Args:
        header: The dictionary header to be augmented
        resolution: The lenght=2 array with the resolution elements

    Returns: The augmented header dictionary
    """
    if resolution is None:
        return header
    if resolution[0] >= resolution[1]:
        header['BMAJ'] = resolution[0]
        header['BMIN'] = resolution[1]
        header['BPA']  = 0.0
    else:
        header['BMAJ'] = resolution[1]
        header['BMIN'] = resolution[0]
        header['BPA']  = 90.0
    return header


def _bool_to_string(flag):
    """
    Converts a boolean to a yes or no string
    Args:
        flag: boolean to be converted to string

    Returns: 'yes' or 'no'

    """
    if flag:
        return 'yes'
    else:
        return 'no'


def _print_data_contents(data_dict, field_names, alignment='l'):
    """
    Factorized printing of the prettytable with the data contents
    Args:
        data_dict: Dictionary with data to be displayed
        field_names: Field names in the table
        alignment: Contents of the table to be aligned Left or Right
    """
    table = PrettyTable()
    table.field_names = field_names
    table.align = alignment
    depth = len(field_names)
    if depth == 3:
        for item_l1 in data_dict.keys():
            for item_l2 in data_dict[item_l1].keys():
                table.add_row([item_l1, item_l2, list(data_dict[item_l1][item_l2].keys())])
    elif depth == 2:
        for item_l1 in data_dict.keys():
            if 'info' in item_l1:
                pass
            else:
                table.add_row([item_l1, list(data_dict[item_l1].keys())])
    elif depth == 1:
        for item_l1 in data_dict.keys():
            table.add_row([item_l1])
    else:
        raise Exception(f'Unhandled case len(field_names) == {depth}')

    print('\nContents:')
    print(table)


def _print_attributes(meta_dict, split_key=None, alignment='l'):
    """
    Print a summary of the atributes
    Args:
        meta_dict: Dictionary containing metadata attributes
        split_key: key to be sqrt and displayed as nx X ny

    Returns:

    """
    print("\nAttributes:")
    table = PrettyTable()
    table.field_names = ['Attribute', 'Value']
    table.align = alignment
    if split_key is None:
        for key in meta_dict.keys():
            table.add_row([key, meta_dict[key]])

    else:
        for key in meta_dict.keys():
            if key == split_key:
                n_side = int(np.sqrt(meta_dict[key]))
                table.add_row([key, f'{n_side:d} x {n_side:d}'])
            else:
                table.add_row([key, meta_dict[key]])
    print(table)


def _rad_to_hour_str(rad):
    """
    Converts an angle in radians to hours minutes and seconds
    Args:
        rad: angle in radians

    Returns:
    xxhyymzz.zzzs
    """
    h_float = rad * _convert_unit('rad', 'hour', 'trigonometric')
    h_int = np.floor(h_float)
    m_float = (h_float-h_int)*60
    m_int = np.floor(m_float)
    s_float = (m_float-m_int)*60
    return f'{int(h_int):02d}h{int(m_int):02d}m{s_float:06.3f}s'


def _rad_to_deg_str(rad):
    """
    Converts an angle in radians to degrees minutes and seconds
    Args:
        rad: angle in radians

    Returns:
    xx\u00B0yymzz.zzzs
    """
    d_float = rad * _convert_unit('rad', 'deg', 'trigonometric')
    if d_float < 0:
        d_float *= -1
        sign = '-'
    else:
        sign = '+'
    d_int = np.floor(d_float)
    m_float = (d_float-d_int)*60
    m_int = np.floor(m_float)
    s_float = (m_float-m_int)*60
    return f'{sign}{int(d_int):02d}\u00B0{int(m_int):02d}m{s_float:06.3f}s'


def _print_summary_header(filename, print_len=100, frame_char='#', frame_width=3):
    """
    Print a summary header dynamically adjusted to the filename
    Args:
        filename: filename
        print_len: Lenght of the print on screen
        frame_char: Character to frame header
        frame_width: Width of the frame

    Returns:

    """
    title = 'Summary for:'
    filename, file_nlead, file_ntrail, print_len = _compute_spacing(filename, print_len=print_len,
                                                                    frame_width=frame_width)
    title, title_nlead, title_ntrail, _ = _compute_spacing(title, print_len=print_len, frame_width=frame_width)
    print(print_len * frame_char)
    _print_centralized(title, title_nlead, title_ntrail, frame_width, frame_char)
    _print_centralized(filename, file_nlead, file_ntrail, frame_width, frame_char)
    print(print_len * frame_char)


def _compute_spacing(string, print_len=100, frame_width=3):
    spc = ' '
    nchar = len(string)
    if 2*(nchar//2) != nchar:
        nchar += 1
        string += spc
    cont_len = nchar+2*frame_width+2
    if 2*(print_len//2) != print_len:
        print_len += 1
    if cont_len > print_len:
        print_len += cont_len - print_len

    nlead = int(print_len // 2 - nchar // 2 - frame_width)
    ntrail = print_len - nlead - 2*frame_width - nchar
    return string, nlead, ntrail, print_len


def _print_centralized(string, nlead, ntrail, frame_width, frame_char):
    spc = ' '
    print(f'{frame_width * frame_char}{nlead * spc}{string}{ntrail * spc}{frame_width * frame_char}')


def _print_method_list(method_list, alignment='l', print_len=100):
    """Print the method list of an mds object"""
    name_len = 0
    for obj_method in method_list:
        meth_len = len(obj_method.__name__)
        if meth_len > name_len:
            name_len = meth_len
    desc_len = print_len - name_len - 3 - 4  # Separators and padding

    print('\nAvailable methods:')
    table = PrettyTable()
    table.field_names = ['Methods', 'Description']
    table.align = alignment
    for obj_method in method_list:
        table.add_row([obj_method.__name__, fill(obj_method.__doc__.splitlines()[0][1:], width=desc_len)])
    print(table)
    print()


def _format_value_error(value, error, scaling, tolerance):
    """Format values based and errors based on the significant digits"""
    if np.isfinite(value) and np.isfinite(error):
        value *= scaling
        error *= scaling
        if abs(value) < tolerance:
            value = 0.0
        if abs(error) < tolerance:
            error = 0.0
        if value == 0 and error == 0:
            return f'{value} \u00b1 {error}'
        elif error > abs(value):
            places = round(np.log10(error))
            if places < 0:
                places = abs(places)
                return f'{value:.{places}f} \u00B1 {error:.{places}f}'
            else:
                if places in [-1, 0, 1]:
                    places = 2
                if value == 0:
                    digits = places - round(np.log10(abs(error)))
                else:
                    digits = places - round(np.log10(abs(value)))
                value = _significant_digits(value, digits)
                error = _significant_digits(error, places)
                return f'{value} \u00b1 {error}'
        else:
            digits = round(abs(np.log10(abs(value))))-1
            if digits in [-1, 0, 1]:
                digits = 2
            value = _significant_digits(value, digits)
            error = _significant_digits(error, digits-1)
            return f'{value} \u00b1 {error}'
    else:
        return f'{value} \u00b1 {error}'
