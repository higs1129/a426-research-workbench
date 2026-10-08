"""Fixtures are generated under this application's ignored tests/artifacts only."""
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from array_data import (ArraySource, DataError, Limits, format_value, heatmap_rgb,
                        normalized_finite, preview_sample, slice_view, table_page)

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"


class DataTests(unittest.TestCase):
    def setUp(self):
        ARTIFACTS.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ARTIFACTS)
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)

    def save(self, array, name="sample.npy"):
        path = self.folder / name
        np.save(path, array)
        return path

    def test_scalar_vector_matrix_endian_fortran_and_empty_readonly(self):
        cases = [np.array(3.25), np.arange(13), np.arange(30).reshape(5, 6),
                 np.arange(30, dtype=">f8").reshape(5, 6),
                 np.asfortranarray(np.arange(30).reshape(5, 6)),
                 np.empty((0, 3)), np.empty((3, 0)), np.empty((0,))]
        for original in cases:
            with self.subTest(shape=original.shape, dtype=original.dtype):
                path = self.save(original)
                before = path.read_bytes()
                with ArraySource(path) as source:
                    loaded = source.load(source.arrays[0])
                    np.testing.assert_array_equal(loaded, original)
                    self.assertFalse(loaded.flags.writeable)
                    if loaded.size:
                        with self.assertRaises(ValueError):
                            loaded.flat[0] = 0
                    table_page(slice_view(loaded))
                    del loaded
                self.assertEqual(before, path.read_bytes())

    def test_archive_lazy_read_and_columns(self):
        path = self.folder / "data.npz"
        original = np.arange(301 * 401 * 5, dtype=float).reshape(301, 401, 5)
        np.savez_compressed(path, values=original, columns=np.array(["a", "b", "c", "d", "e"]), fortran=np.asfortranarray(original))
        with ArraySource(path) as source:
            self.assertEqual(source.column_labels(), list("abcde"))
            self.assertEqual(len(source.arrays), 3)
            for info in (source.arrays[0], source.arrays[2]):
                loaded = source.load(info)
                np.testing.assert_array_equal(loaded, original)
                view = slice_view(loaded, 0, 1, {2: 2})
                self.assertEqual(view.shape, (301, 401))
                np.testing.assert_array_equal(view, original[:, :, 2])

    def test_all_axis_orders_on_four_dimensions(self):
        array = np.arange(2 * 3 * 4 * 5).reshape(2, 3, 4, 5)
        for row in range(4):
            for col in range(4):
                if row == col:
                    continue
                fixed = {axis: 1 for axis in range(4) if axis not in (row, col)}
                view = slice_view(array, row, col, fixed)
                self.assertEqual(view.shape, (array.shape[row], array.shape[col]))
                self.assertTrue(np.shares_memory(array, view))
                for i in range(view.shape[0]):
                    for j in range(view.shape[1]):
                        index = [fixed.get(a, 0) for a in range(4)]
                        index[row], index[col] = i, j
                        self.assertEqual(view[i, j], array[tuple(index)])
        with self.assertRaises(DataError):
            slice_view(array, 1, 1)
        with self.assertRaises(DataError):
            slice_view(array, 0, 1, {2: 4})
        with self.assertRaises(DataError):
            slice_view(np.empty((3, 4, 0)))

    def test_paging_and_bounds(self):
        array = np.arange(1000 * 50).reshape(1000, 50)
        page = table_page(array, 975, 48)
        self.assertEqual(page.shape, (25, 2))
        self.assertEqual(page[0, 0], array[975, 48])
        self.assertTrue(np.shares_memory(page, array))
        for args in ((-1, 0), (1000, 0), (0, 50)):
            with self.assertRaises(DataError):
                table_page(array, *args)
        with self.assertRaises(DataError):
            table_page(array, rows=100000)

    def test_complex_nonfinite_and_precision(self):
        values = np.array([1 + 2j, -3 - 4j, complex(np.nan, np.inf)])
        self.assertEqual(format_value(values[0]), "1+2j")
        self.assertEqual(format_value(values[1]), "-3-4j")
        self.assertIn("nan+infj", format_value(values[2]))
        value = np.float64(1.2345678901234567)
        self.assertEqual(float(format_value(value, full=True)), value)
        _, magnitude = preview_sample(values, "幅值")
        self.assertAlmostEqual(magnitude[1], 5)
        np.testing.assert_equal(preview_sample(values, "实部")[1], values.real)
        np.testing.assert_equal(preview_sample(values, "虚部")[1], values.imag)
        np.testing.assert_equal(preview_sample(np.array([-128], dtype=np.int8), "幅值")[1], [128])

    def test_preview_bounded_and_orientation(self):
        array = np.arange(900 * 1300).reshape(900, 1300)
        (rows, cols), sample = preview_sample(array)
        self.assertEqual(sample.shape, (512, 512))
        self.assertEqual((sample[0, 0], sample[-1, -1]), (array[0, 0], array[-1, -1]))
        self.assertEqual(sample[47, 98], array[rows[47], cols[98]])
        indices, line = preview_sample(np.arange(100000))
        self.assertEqual(line.size, 2000)
        self.assertEqual(indices[-1], 99999)
        rgb, low, high = heatmap_rgb(np.array([[0, 1], [np.nan, np.inf]]))
        self.assertEqual((low, high), (0, 1))
        np.testing.assert_array_equal(rgb[1, 0], [180, 180, 180])
        normalized, _, _, _ = normalized_finite(np.array([-1e308, 1e308]))
        np.testing.assert_array_equal(normalized, [0, 1])
        with self.assertRaises(DataError):
            preview_sample(np.array(["abc"]))
        with self.assertRaises(DataError):
            normalized_finite(np.array([np.nan, np.inf]))

    def test_object_pickle_is_never_loaded(self):
        path = self.save(np.array([{"unsafe": True}], dtype=object))
        with mock.patch("pickle.load", side_effect=AssertionError("pickle must not run")):
            with ArraySource(path) as source:
                self.assertIn("pickle", source.arrays[0].error)
                with self.assertRaises(DataError):
                    source.load(source.arrays[0])
        path = self.folder / "mixed.npz"
        np.savez(path, objects=np.array([None], dtype=object), numeric=np.arange(3))
        with ArraySource(path) as source:
            self.assertTrue(source.arrays[0].error)
            np.testing.assert_array_equal(source.load(source.arrays[1]), np.arange(3))

    def test_unsupported_dtype_and_bounded_text(self):
        for array in (np.zeros(2, dtype=[("x", "f8")]), np.zeros(1, dtype="V4"), np.zeros(1, dtype="U20000")):
            with ArraySource(self.save(array)) as source:
                self.assertTrue(source.arrays[0].error)
        self.assertLessEqual(len(format_value("a" * 1000)), 96)
        self.assertEqual(format_value(b"abc"), "abc")

    def test_truncated_invalid_and_oversized_headers(self):
        path = self.save(np.arange(10))
        original = path.read_bytes()
        for content in (original[:-4], original + b"extra", b"garbage", b"\x93NUMPY\x01\x00" + struct.pack("<H", 65535)):
            path.write_bytes(content)
            with self.assertRaises(DataError):
                ArraySource(path)
        header = {"descr": "<f8", "fortran_order": False, "shape": (-1,)}
        buffer = io.BytesIO()
        np.lib.format.write_array_header_1_0(buffer, header)
        path.write_bytes(buffer.getvalue())
        with self.assertRaises(DataError):
            ArraySource(path)

    def test_memory_zip_limits_and_duplicate_entries(self):
        path = self.save(np.arange(100))
        with self.assertRaises(DataError):
            ArraySource(path, Limits(mapped_bytes=10))
        archive = self.folder / "data.npz"
        np.savez_compressed(archive, data=np.zeros(10000))
        for limits in (Limits(member_bytes=10), Limits(archive_bytes=10), Limits(compression_ratio=2), Limits(directory_bytes=10), Limits(members=0)):
            with self.assertRaises(DataError):
                ArraySource(archive, limits)
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("a.npy", path.read_bytes())
            with self.assertWarns(UserWarning):
                output.writestr("a.npy", path.read_bytes())
        with self.assertRaises(DataError):
            ArraySource(archive)

    def test_file_change_detected(self):
        path = self.save(np.arange(10))
        with ArraySource(path) as source:
            with path.open("ab") as output:
                output.write(b"changed")
            with self.assertRaises(DataError):
                source.load(source.arrays[0])

    def test_npy_v2_v3_text_and_dates(self):
        for version in ((1, 0), (2, 0), (3, 0)):
            path = self.folder / "version.npy"
            original = np.array(["温升", "径向", "轴向"])
            with path.open("wb") as output:
                np.lib.format.write_array(output, original, version=version, allow_pickle=False)
            with ArraySource(path) as source:
                np.testing.assert_array_equal(source.load(source.arrays[0]), original)
        path = self.save(np.array(["2026-09-16"], dtype="datetime64[D]"))
        with ArraySource(path) as source:
            self.assertEqual(format_value(source.load(source.arrays[0])[0]), "2026-09-16")


if __name__ == "__main__":
    unittest.main()
