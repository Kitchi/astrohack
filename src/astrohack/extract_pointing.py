from astrohack._utils._extract_point import _extract_pointing

from astrohack._utils._dio import _load_point_file
from astrohack._utils._dio import _write_meta_data
from astrohack._utils._tools import get_default_file_name

from astrohack.mds import AstrohackPointFile

import skriba.logger
import auror.parameter


@auror.parameter.validate(
    logger=skriba.logger.get_logger(logger_name="astrohack")
)
def extract_pointing(
        ms_name: str,
        point_name: str = None,
        parallel: bool = False,
        overwrite: bool = False,
) -> AstrohackPointFile:
    """ Extract pointing data from measurement set.  Creates holography output file.

    :param ms_name: Name of input measurement file name.
    :type ms_name: str

    :param point_name: Name of *<point_name>.point.zarr* file to create. Defaults to measurement set name with *point.zarr* extension.
    :type point_name: str, optional

    :param parallel: Boolean for whether to process in parallel. Defaults to False
    :type parallel: bool, optional

    :param overwrite: Overwrite pointing file on disk, defaults to False
    :type overwrite: bool, optional

    :return: Holography point object.
    :rtype: AstrohackPointFile

    .. _Description:

    **Example Usage**
    In this case, the pointing_name is the file name to be created after extraction.

    .. parsed-literal::
        from astrohack.extract_pointing import extract_pointing

        extract_pointing(
            ms_name="astrohack_observation.ms",
            point_name="astrohack_observation.point.zarr"
        )

    **AstrohackPointFile**

    Point object allows the user to access point data via dictionary keys with values `ant`. The point object also
    provides a `summary()` helper function to list available keys for each file.

    """
    # Doing this here allows it to get captured by locals()
    if point_name is None:
        point_name = get_default_file_name(input_file=ms_name, output_type=".point.zarr")

    # Returns the current local variables in dictionary form
    extract_pointing_params = locals()

    logger = skriba.logger.get_logger(logger_name="astrohack")

    input_params = extract_pointing_params.copy()
    pnt_dict = _extract_pointing(
        ms_name=extract_pointing_params['ms_name'],
        pnt_name=extract_pointing_params['point_name'],
        parallel=extract_pointing_params['parallel']
    )

    # Calling this directly since it is so simple it doesn't need a "_create_{}" function.
    _write_meta_data(
        file_name="{name}/{ext}".format(name=extract_pointing_params['point_name'], ext=".point_input"),
        input_dict=input_params
    )

    logger.info(f"Finished processing")
    point_dict = _load_point_file(file=extract_pointing_params["point_name"], dask_load=True)

    pointing_mds = AstrohackPointFile(extract_pointing_params['point_name'])
    pointing_mds.open()

    return pointing_mds
