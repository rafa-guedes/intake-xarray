from .base import DataSourceMixin


class ZarrSource(DataSourceMixin):
    """Open a xarray dataset.

    Parameters
    ----------
    urlpath: str
        Path to source. This can be a local directory or a remote data
        service (i.e., with a protocol specifier like ``'s3://``).
    storage_options: dict
        Parameters passed to the backend file-system
    kwargs:
        Further parameters are passed to xr.open_zarr
    """
    name = 'zarr'

    def __init__(self, urlpath, storage_options=None, metadata=None, **kwargs):
        super(ZarrSource, self).__init__(metadata=metadata)
        self.urlpath = urlpath
        self.storage_options = storage_options
        self.kwargs = kwargs
        self._ds = None

    def _open_dataset(self):
        import xarray as xr
        import fsspec
        assert fsspec.__version__ >= "0.3.6", "zarr plugin requires fsspec >= 0.3.6"
        from fsspec import filesystem, get_mapper
        from fsspec.utils import update_storage_options, infer_storage_options

        storage_options = infer_storage_options(self.urlpath)
        update_storage_options(storage_options, self.storage_options)
        self._fs = filesystem(storage_options['protocol'])
        if storage_options['protocol'] != 'file':
            self._mapper = get_mapper(self.urlpath)
            self._ds = xr.open_zarr(self._mapper, **self.kwargs)
        else:
            self._ds = xr.open_zarr(self.urlpath, **self.kwargs)

    def close(self):
        super(ZarrSource, self).close()
        self._fs = None
        self._mapper = None
