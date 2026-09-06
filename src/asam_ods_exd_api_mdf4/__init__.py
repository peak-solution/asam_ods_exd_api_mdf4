"""ASAM ODS EXD API implementation for MDF4 files."""

from importlib.metadata import PackageNotFoundError, version

from .external_data_file import ExternalDataFile

try:
    __version__ = version("asam-ods-exd-api-mdf4")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["ExternalDataFile", "__version__"]
