"""In-memory fake backend for the LumiPy Measurement interface.

Local test code: it imports nothing from the upstream clone and reaches no instrument.  It
implements the public members of ``libs.pqlumi:Measurement``, ``ImgConf`` and ``PointConf``
that the driver uses, so gate G7 can check the native surface against the pinned AST.  The
starting values, the 3x3 analysis image, the five-point curve and the type lists are
placeholders; they are not measurements, Luminosa limits or a real image size.  The pinned
upstream is_fake fallback itself returns a 3x3 image and a five-point curve
(libs/pqlumi.py:882-942); this fake adds a small running/stopped model so start, stop and
the safe-state action are observable, and a ``stop_ignored`` test switch for a stop_meas that
returns while meas_status still reports a running measurement.  Nothing here moves by itself.
"""


class _FakeImgConf:
    """Stand-in for ``ImgConf``; only the properties the driver binds."""

    def __init__(self):
        self._scan_speed = 10  # placeholder: percent
        self._image_size = (3, 3)  # placeholder: pixels
        self._stop_on_num_frames = False  # placeholder
        self._num_frames = 1  # placeholder
        self._stop_on_photons_in_brightest_px = False  # placeholder
        self._photons_in_brightest_px = 1000  # placeholder
        self._stop_on_meas_time = False  # placeholder
        self._meas_time = 1.0  # placeholder: seconds

    @property
    def scan_speed(self):
        return self._scan_speed

    @scan_speed.setter
    def scan_speed(self, value):
        self._scan_speed = int(value)

    @property
    def image_size(self):
        return self._image_size

    @image_size.setter
    def image_size(self, value):
        self._image_size = (int(value[0]), int(value[1]))

    @property
    def stop_on_num_frames(self):
        return self._stop_on_num_frames

    @stop_on_num_frames.setter
    def stop_on_num_frames(self, value):
        self._stop_on_num_frames = bool(value)

    @property
    def num_frames(self):
        return self._num_frames

    @num_frames.setter
    def num_frames(self, value):
        self._num_frames = int(value)

    @property
    def stop_on_photons_in_brightest_px(self):
        return self._stop_on_photons_in_brightest_px

    @stop_on_photons_in_brightest_px.setter
    def stop_on_photons_in_brightest_px(self, value):
        self._stop_on_photons_in_brightest_px = bool(value)

    @property
    def photons_in_brightest_px(self):
        return self._photons_in_brightest_px

    @photons_in_brightest_px.setter
    def photons_in_brightest_px(self, value):
        self._photons_in_brightest_px = int(value)

    @property
    def stop_on_meas_time(self):
        return self._stop_on_meas_time

    @stop_on_meas_time.setter
    def stop_on_meas_time(self, value):
        self._stop_on_meas_time = bool(value)

    @property
    def meas_time(self):
        return self._meas_time

    @meas_time.setter
    def meas_time(self, value):
        self._meas_time = float(value)


class _FakePointConf:
    """Stand-in for ``PointConf``; only the properties the driver binds."""

    def __init__(self):
        self._stop_on_photons = False  # placeholder
        self._num_photons = 1000  # placeholder
        self._stop_on_meas_time = False  # placeholder
        self._meas_time = 1.0  # placeholder: seconds

    @property
    def stop_on_photons(self):
        return self._stop_on_photons

    @stop_on_photons.setter
    def stop_on_photons(self, value):
        self._stop_on_photons = bool(value)

    @property
    def num_photons(self):
        return self._num_photons

    @num_photons.setter
    def num_photons(self, value):
        self._num_photons = int(value)

    @property
    def stop_on_meas_time(self):
        return self._stop_on_meas_time

    @stop_on_meas_time.setter
    def stop_on_meas_time(self, value):
        self._stop_on_meas_time = bool(value)

    @property
    def meas_time(self):
        return self._meas_time

    @meas_time.setter
    def meas_time(self, value):
        self._meas_time = float(value)


class FakeMeasurement:
    """One controlled Luminosa Measurement endpoint."""

    def __init__(self, **_options):
        self._img_conf = _FakeImgConf()
        self._point_conf = _FakePointConf()
        self._version = "placeholder Luminosa version"  # placeholder
        self._scan_range_left = 0.0  # placeholder: meters
        self._scan_range_top = 0.0  # placeholder: meters
        self._scan_range_width = 100e-6  # placeholder: meters
        self._scan_range_height = 100e-6  # placeholder: meters
        self._scan_range_min_x = -100e-6  # placeholder: meters
        self._scan_range_max_x = 100e-6  # placeholder: meters
        self._scan_range_min_y = -100e-6  # placeholder: meters
        self._scan_range_max_y = 100e-6  # placeholder: meters
        self._write_ptu_file = False  # placeholder
        self._path_to_ptu = ""  # placeholder: no file yet
        self._running = False  # controlled placeholder state
        self.stop_ignored = False  # test switch: a stop_meas that returns while the measurement keeps running
        self._elapsed = 0.0  # placeholder: seconds
        self._next_name = ""  # placeholder: the Luminosa default name
        self._analysis_names = ["placeholder_analysis"]  # placeholder
        self._curve_types = ["placeholder_curve"]  # placeholder
        self._image_types = ["placeholder_image"]  # placeholder
        self._param_types = ["placeholder_param"]  # placeholder
        self._curve = {
            "name": "placeholder curve",  # placeholder
            "data_x": [1.0, 2.0, 3.0, 4.0, 5.0],  # placeholder
            "data_y": [0.0, 1.0, 10.0, 1.0, 0.0],  # placeholder
            "axis_title_x": "placeholder time",  # placeholder
            "axis_title_y": "placeholder intensity",  # placeholder
            "unit_x": "s",  # placeholder
            "unit_y": "counts",  # placeholder
        }
        self._image = {
            "img_name": "Intensity",  # placeholder
            "img_data": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]],  # placeholder 3x3
            "img_unit": "counts",  # placeholder
            "pos_min": (-100e-6, -100e-6, 0.0),  # placeholder: meters
            "pos_max": (100e-6, 100e-6, 0.0),  # placeholder: meters
            "pos_title": ("Pixel X", "Pixel Y", "Pixel Z"),  # placeholder
            "pos_unit": ("m", "m", "m"),  # placeholder
        }
        self._param = {"placeholder_param": 1.0}  # placeholder

    @property
    def img_conf(self):
        return self._img_conf

    @property
    def point_conf(self):
        return self._point_conf

    @property
    def version(self):
        return self._version

    @property
    def scan_range_min_x(self):
        return self._scan_range_min_x

    @property
    def scan_range_max_x(self):
        return self._scan_range_max_x

    @property
    def scan_range_min_y(self):
        return self._scan_range_min_y

    @property
    def scan_range_max_y(self):
        return self._scan_range_max_y

    @property
    def scan_range_left(self):
        return self._scan_range_left

    @scan_range_left.setter
    def scan_range_left(self, value):
        self._scan_range_left = float(value)

    @property
    def scan_range_top(self):
        return self._scan_range_top

    @scan_range_top.setter
    def scan_range_top(self, value):
        self._scan_range_top = float(value)

    @property
    def scan_range_width(self):
        return self._scan_range_width

    @scan_range_width.setter
    def scan_range_width(self, value):
        self._scan_range_width = float(value)

    @property
    def scan_range_height(self):
        return self._scan_range_height

    @scan_range_height.setter
    def scan_range_height(self, value):
        self._scan_range_height = float(value)

    @property
    def write_ptu_file(self):
        return self._write_ptu_file

    @write_ptu_file.setter
    def write_ptu_file(self, value):
        self._write_ptu_file = bool(value)

    @property
    def path_to_ptu(self):
        return self._path_to_ptu

    def set_next_measurement_name(self, name):
        self._next_name = str(name)

    def get_analysis_names(self):
        return list(self._analysis_names)

    def get_analysis_curve_types(self, name):
        return list(self._curve_types)

    def get_analysis_curve(self, name, curve_type):
        return dict(self._curve)

    def get_analysis_image_types(self, name):
        return list(self._image_types)

    def get_analysis_image(self, name, img_type):
        return dict(self._image)

    def get_analysis_param_types(self, name):
        return list(self._param_types)

    def get_analysis_param(self, name, param_type):
        return dict(self._param)

    def start_meas(self, meas_type):
        self._running = True
        self._elapsed = 0.0

    def meas_status(self):
        return self._running

    def stop_meas(self):
        if not self.stop_ignored:
            self._running = False

    def get_elapsed_meas_time(self):
        return self._elapsed


def connect(**options):
    return FakeMeasurement(**options)
