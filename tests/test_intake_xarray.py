# -*- coding: utf-8 -*-
import os
import numpy as np
import pytest

import intake

here = os.path.dirname(__file__)


@pytest.mark.parametrize('source', ['netcdf', 'zarr'])
def test_discover(source, netcdf_source, zarr_source, dataset):
    source = {'netcdf': netcdf_source, 'zarr': zarr_source}[source]
    r = source.discover()

    assert r['datashape'] is None
    assert r['dtype'] is None
    assert r['metadata'] is not None

    assert source.datashape is None
    assert source.metadata['dims'] == dict(dataset.dims)
    assert set(source.metadata['data_vars']) == set(dataset.data_vars.keys())
    assert set(source.metadata['coords']) == set(dataset.coords.keys())


@pytest.mark.parametrize('source', ['netcdf', 'zarr'])
def test_read(source, netcdf_source, zarr_source, dataset):
    source = {'netcdf': netcdf_source, 'zarr': zarr_source}[source]

    ds = source.read_chunked()
    assert ds.temp.chunks

    ds = source.read()
    assert ds.dims == dataset.dims
    assert np.all(ds.temp == dataset.temp)
    assert np.all(ds.rh == dataset.rh)


def test_read_partition_netcdf(netcdf_source):
    source = netcdf_source
    with pytest.raises(TypeError):
        source.read_partition(None)
    out = source.read_partition(('temp', 0, 0, 0, 0))
    d = source.to_dask()['temp'].data
    expected = d[:1, :4, :5, :10].compute()
    assert np.all(out == expected)


def test_read_list_of_netcdf_files():
    from intake_xarray.netcdf import NetCDFSource
    source = NetCDFSource([
        os.path.join(here, 'data', 'example_1.nc'),
        os.path.join(here, 'data', 'example_2.nc'),
    ])
    d = source.to_dask()
    assert d.dims == {'lat': 5, 'lon': 10, 'level': 4, 'time': 1,
                      'concat_dim': 2}


def test_read_glob_pattern_of_netcdf_files():
    """If xarray is old, prompt user to update to use pattern"""
    from intake_xarray.netcdf import NetCDFSource
    source = NetCDFSource(os.path.join(here, 'data', 'example_{num: d}.nc'),
                          concat_dim='num')
    d = source.to_dask()
    assert d.dims == {'lat': 5, 'lon': 10, 'level': 4, 'time': 1,
                      'num': 2}
    assert (d.num.data == np.array([1, 2])).all()


@pytest.fixture()
def old_xarray():
    import xarray as xr
    version = xr.__version__
    try:
        xr.__version__ = "0.1"
        yield
    finally:
        xr.__version__ = version


def test_old_xarray(old_xarray):
    from intake_xarray.netcdf import NetCDFSource
    source = NetCDFSource(os.path.join(here, 'data', 'example_{num: d}.nc'),
                          concat_dim='num')
    with pytest.raises(ImportError,
                       match='open_dataset was added in 0.11.2'):
        source.to_dask()


def test_read_partition_zarr(zarr_source):
    source = zarr_source
    with pytest.raises(TypeError):
        source.read_partition(None)
    out = source.read_partition(('temp', 0, 0, 0, 0))
    expected = source.to_dask()['temp'].values
    assert np.all(out == expected)


@pytest.mark.parametrize('source', ['netcdf', 'zarr'])
def test_to_dask(source, netcdf_source, zarr_source, dataset):
    source = {'netcdf': netcdf_source, 'zarr': zarr_source}[source]
    ds = source.to_dask()

    assert ds.dims == dataset.dims
    assert np.all(ds.temp == dataset.temp)
    assert np.all(ds.rh == dataset.rh)


def test_grib_dask():
    pytest.importorskip('Nio')
    import dask.array as da
    cat = intake.open_catalog(os.path.join(here, 'data', 'catalog.yaml'))
    x = cat.grib.to_dask()
    assert len(x.fileno) == 2
    assert isinstance(x.APCP_P8_L1_GLL0_acc6h.data, da.Array)
    values = x.APCP_P8_L1_GLL0_acc6h.data.compute()
    x2 = cat.grib.read()
    assert (values == x2.APCP_P8_L1_GLL0_acc6h.values).all()


def test_rasterio():
    import dask.array as da
    pytest.importorskip('rasterio')
    cat = intake.open_catalog(os.path.join(here, 'data', 'catalog.yaml'))
    s = cat.tiff_source
    info = s.discover()
    assert info['shape'] == (3, 718, 791)
    x = s.to_dask()
    assert isinstance(x.data, da.Array)
    x = s.read()
    assert x.data.shape == (3, 718, 791)


def test_rasterio_glob():
    import dask.array as da
    pytest.importorskip('rasterio')
    cat = intake.open_catalog(os.path.join(here, 'data', 'catalog.yaml'))
    s = cat.tiff_glob_source
    info = s.discover()
    assert info['shape'] == (1, 3, 718, 791)
    x = s.to_dask()
    assert isinstance(x.data, da.Array)
    x = s.read()
    assert x.data.shape == (1, 3, 718, 791)


def test_rasterio_empty_glob():
    pytest.importorskip('rasterio')
    cat = intake.open_catalog(os.path.join(here, 'data', 'catalog.yaml'))
    s = cat.empty_glob
    with pytest.raises(Exception):
        s.discover()


def test_rasterio_cached_glob():
    import dask.array as da
    pytest.importorskip('rasterio')
    cat = intake.open_catalog(os.path.join(here, 'data', 'catalog.yaml'))
    s = cat.cached_tiff_glob_source
    cache = s.cache[0]
    info = s.discover()
    assert info['shape'] == (1, 3, 718, 791)
    x = s.to_dask()
    assert isinstance(x.data, da.Array)
    x = s.read()
    assert x.data.shape == (1, 3, 718, 791)
    cache.clear_all()


def test_read_partition_tiff():
    pytest.importorskip('rasterio')
    cat = intake.open_catalog(os.path.join(here, 'data', 'catalog.yaml'))
    s = cat.tiff_source()

    with pytest.raises(TypeError):
        s.read_partition(None)
    out = s.read_partition((0, 0, 0))
    d = s.to_dask().data
    expected = d[:1].compute()
    assert np.all(out == expected)


def test_read_pattern_concat_on_existing_dim():
    pytest.importorskip('rasterio')
    cat = intake.open_catalog(os.path.join(here, 'data', 'catalog.yaml'))
    colors = cat.pattern_tiff_source_concat_on_band()

    da = colors.read()
    assert da.shape == (6, 64, 64)
    assert len(da.color) == 6
    assert set(da.color.data) == set(['red', 'green'])

    assert (da.band == [1, 2, 3, 1, 2, 3]).all()
    assert da[da.color == 'red'].shape == (3, 64, 64)

    rgb = {'red': [204, 17, 17], 'green': [17, 204, 17]}
    for color, values in rgb.items():
        for i, v in enumerate(values):
            assert (da[da.color == color].sel(band=i+1).values == v).all()


def test_read_pattern_concat_on_new_dim():
    pytest.importorskip('rasterio')
    cat = intake.open_catalog(os.path.join(here, 'data', 'catalog.yaml'))
    colors = cat.pattern_tiff_source_concat_on_new_dim()

    da = colors.read()
    assert da.shape == (2, 3, 64, 64)
    assert len(da.color) == 2
    assert set(da.color.data) == set(['red', 'green'])
    assert da[da.color == 'red'].shape == (1, 3, 64, 64)

    rgb = {'red': [204, 17, 17], 'green': [17, 204, 17]}
    for color, values in rgb.items():
        for i, v in enumerate(values):
            assert (da[da.color == color][0].sel(band=i+1).values == v).all()


def test_read_pattern_field_as_band():
    pytest.importorskip('rasterio')
    cat = intake.open_catalog(os.path.join(here, 'data', 'catalog.yaml'))
    colors = cat.pattern_tiff_source_path_pattern_field_as_band()

    da = colors.read()
    assert len(da.band) == 6
    assert set(da.band.data) == set(['red', 'green'])
    assert da[da.band == 'red'].shape == (3, 64, 64)

    rgb = {'red': [204, 17, 17], 'green': [17, 204, 17]}
    for color, values in rgb.items():
        for i, v in enumerate(values):
            assert (da[da.band == color][i].values == v).all()


def test_read_pattern_path_not_as_pattern():
    pytest.importorskip('rasterio')
    cat = intake.open_catalog(os.path.join(here, 'data', 'catalog.yaml'))
    green = cat.pattern_tiff_source_path_not_as_pattern()

    da = green.read()
    assert len(da.band) == 3


def test_read_pattern_path_as_pattern_as_str_with_list_of_urlpaths():
    pytest.importorskip('rasterio')
    cat = intake.open_catalog(os.path.join(here, 'data', 'catalog.yaml'))
    colors = cat.pattern_tiff_source_path_pattern_as_str()

    da = colors.read()
    assert da.shape == (2, 3, 64, 64)
    assert len(da.color) == 2
    assert set(da.color.data) == set(['red', 'green'])

    assert da.sel(color='red').shape == (3, 64, 64)

    rgb = {'red': [204, 17, 17], 'green': [17, 204, 17]}
    for color, values in rgb.items():
        for i, v in enumerate(values):
            assert (da.sel(color=color).sel(band=i+1).values == v).all()


def test_read_image():
    pytest.importorskip('skimage')
    from intake_xarray.image import ImageSource
    im = ImageSource(os.path.join(here, 'data', 'little_red.tif'))
    da = im.read()
    assert da.shape == (64, 64, 3)


def test_read_images():
    pytest.importorskip('skimage')
    from intake_xarray.image import ImageSource
    im = ImageSource(os.path.join(here, 'data', 'little_*.tif'))
    da = im.read()
    assert da.shape == (2, 64, 64, 3)
    assert da.dims == ('concat_dim', 'y', 'x', 'channel')


def test_read_images_with_pattern():
    pytest.importorskip('skimage')
    from intake_xarray.image import ImageSource
    path = os.path.join(here, 'data', 'little_{color}.tif')
    im = ImageSource(path, concat_dim='color')
    da = im.read()
    assert da.shape == (2, 64, 64, 3)
    assert len(da.color) == 2
    assert set(da.color.data) == set(['red', 'green'])


def test_read_images_with_multiple_concat_dims_with_pattern():
    pytest.importorskip('skimage')
    from intake_xarray.image import ImageSource
    path = os.path.join(here, 'data', '{size}_{color}.tif')
    im = ImageSource(path, concat_dim=['size', 'color'])
    ds = im.read()
    assert ds.sel(color='red', size='little').shape == (64, 64, 3)


def test_read_jpg_image():
    pytest.importorskip('skimage')
    from intake_xarray.image import ImageSource
    im = ImageSource(os.path.join(here, 'data', 'dog.jpg'))
    da = im.read()
    assert da.shape == (192, 192)
