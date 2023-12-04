import inspect

import skriba.logger
import auror.parameter

from astrohack._utils._combine import _combine_chunk
from astrohack._utils._dask_graph_tools import _dask_general_compute
from astrohack._utils._dio import _check_if_file_will_be_overwritten, _check_if_file_exists, _write_meta_data
from astrohack._utils._tools import _remove_suffix
from astrohack.mds import AstrohackImageFile

CURRENT_FUNCTION = 0


@auror.parameter.validate(
    logger=skriba.logger.get_logger(logger_name="astrohack")
)
def combine(
        image_name,
        combine_name=None,
        ant="all",
        ddi="all",
        weighted=False,
        parallel=False,
        overwrite=False
):
    """Combine DDIs in a Holography image to increase SNR

    :param image_name: Input holography data file name. Accepted data format is the output from ``astrohack.holog.holog``
    :type image_name: str
    :param combine_name: Name of output file; File name will be appended with suffix *.combine.zarr*. Defaults to \
    *basename* of input file plus holography panel file suffix.
    :type combine_name: str, optional
    :param ant: List of antennas to be processed. None will use all antennas. Defaults to None, ex. ea25.
    :type ant: list or str, optional
    :param ddi: List of DDIs to be combined. None will use all DDIs. Defaults to None, ex. [0, ..., 8].
    :type ddi: list of int, optional
    :param weighted: Weight phases by the corresponding amplitudes.
    :type weighted: bool, optional
    :param parallel: Run in parallel. Defaults to False.
    :type parallel: bool, optional
    :param overwrite: Overwrite files on disk. Defaults to False.
    :type overwrite: bool, optional

    :return: Holography image object.
    :rtype: AstrohackImageFile

    .. _Description:
    **AstrohackImageFile**

    Image object allows the user to access image data via compound dictionary keys with values, in order of depth, \
    `ant` -> `ddi`. The image object also provides a `summary()` helper function to list available keys for each file.\
     An outline of the image object structure is show below:

    .. parsed-literal::
        image_mds =
            {
            ant_0:{
                ddi_0: image_ds,
                 ⋮
                ddi_m: image_ds
            },
            ⋮
            ant_n: …
        }
    """

    combine_params = locals()
    logger = skriba.logger.get_logger(logger_name="astrohack")

    function_name = inspect.stack()[CURRENT_FUNCTION].function

    if combine_name is None:
        logger.info('File not specified or doesn\'t exist. Creating ...')

        combine_name = _remove_suffix(image_name, '.image.zarr') + '.combine.zarr'
        combine_params['combine_name'] = combine_name

        logger.info('Extracting combine name to {output}'.format(output=combine_name))

    input_params = combine_params.copy()

    _check_if_file_exists(combine_params['image_name'])
    _check_if_file_will_be_overwritten(combine_params['combine_name'], combine_params['overwrite'])

    image_mds = AstrohackImageFile(combine_params['image_name'])
    image_mds._open()

    combine_params['image_mds'] = image_mds
    image_attr = image_mds._meta_data

    if _dask_general_compute(function_name, image_mds, _combine_chunk, combine_params, ['ant'], parallel=parallel):
        logger.info("Finished processing")

        output_attr_file = "{name}/{ext}".format(name=combine_params['combine_name'], ext=".image_attr")
        _write_meta_data(output_attr_file, image_attr)

        output_attr_file = "{name}/{ext}".format(name=combine_params['combine_name'], ext=".image_input")
        _write_meta_data(output_attr_file, input_params)

        combine_mds = AstrohackImageFile(combine_params['combine_name'])
        combine_mds._open()
        return combine_mds
    else:
        logger.warning("No data to process")
        return None
