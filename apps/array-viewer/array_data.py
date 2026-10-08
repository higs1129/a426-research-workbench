"""Bounded, read-only NPY/NPZ access and dimension-preserving display helpers.

No pickle deserialization is used, including when reading archive members.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import math
from pathlib import Path
import struct
import zipfile

import numpy as np


class DataError(ValueError):
    """A safe, user-readable data/limit error."""


@dataclass(frozen=True)
class Limits:
    header_bytes: int = 16 * 1024
    archive_bytes: int = 512 * 1024**2
    member_bytes: int = 256 * 1024**2
    mapped_bytes: int = 16 * 1024**3
    directory_bytes: int = 4 * 1024**2
    members: int = 1024
    compression_ratio: int = 2000
    dimensions: int = 32


@dataclass(frozen=True)
class ArrayInfo:
    name: str
    dtype: np.dtype
    shape: tuple[int, ...]
    nbytes: int
    offset: int
    fortran: bool
    member: str | None = None
    error: str = ""


def readable_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.3g} {unit}"
        value /= 1024
    raise AssertionError


def _read_exact(stream, count: int) -> bytes:
    value = stream.read(count)
    if len(value) != count:
        raise DataError("文件被截断，未读取到完整的数据。")
    return value


def read_header(stream, name: str, limits: Limits, member=None) -> ArrayInfo:
    if _read_exact(stream, 6) != b"\x93NUMPY":
        raise DataError("不是有效的 NPY 数据。")
    version = tuple(_read_exact(stream, 2))
    if version == (1, 0):
        length = struct.unpack("<H", _read_exact(stream, 2))[0]
    elif version in ((2, 0), (3, 0)):
        length = struct.unpack("<I", _read_exact(stream, 4))[0]
    else:
        raise DataError(f"不支持 NPY 格式版本 {version}。")
    if length > limits.header_bytes:
        raise DataError(f"NPY 头部超过 {readable_size(limits.header_bytes)} 安全上限。")
    try:
        header = ast.literal_eval(_read_exact(stream, length).decode("utf-8" if version == (3, 0) else "latin1"))
        if not isinstance(header, dict) or set(header) != {"descr", "fortran_order", "shape"}:
            raise ValueError("header keys")
        shape = header["shape"]
        if (not isinstance(shape, tuple) or len(shape) > limits.dimensions
                or any(type(n) is not int or n < 0 or n > np.iinfo(np.intp).max for n in shape)):
            raise ValueError("invalid shape")
        if type(header["fortran_order"]) is not bool:
            raise ValueError("invalid order")
        dtype = np.lib.format.descr_to_dtype(header["descr"])
        # Avoid shapes whose stride products overflow even if an axis is empty.
        if math.prod(max(1, n) for n in shape) * max(1, dtype.itemsize) > np.iinfo(np.intp).max:
            raise ValueError("shape overflow")
    except (ValueError, TypeError, SyntaxError, UnicodeError, OverflowError, RecursionError) as exc:
        raise DataError("NPY 头部无效，或维度超过安全上限。") from exc
    error = ""
    if dtype.hasobject:
        error = "对象数组不受支持：不会启用 pickle。"
    elif dtype.fields or dtype.subdtype or dtype.kind not in "biufcSUMm":
        error = "暂不支持结构化、嵌套或原始字节 dtype。"
    elif dtype.itemsize == 0:
        error = "暂不支持元素字节数为 0 的 dtype。"
    elif dtype.itemsize > 65536:
        error = "单个元素超过 64 KiB，无法安全地在单元格中显示。"
    return ArrayInfo(name, dtype, shape, math.prod(shape) * dtype.itemsize,
                     stream.tell(), header["fortran_order"], member, error)


def _check_zip_index(stream, limits: Limits):
    """Bound the central directory before ZipFile allocates its entry objects."""
    stream.seek(0, 2)
    size = stream.tell()
    if size > limits.archive_bytes:
        raise DataError(f"NPZ 文件超过 {readable_size(limits.archive_bytes)} 安全上限。请分拆数据。")
    stream.seek(max(0, size - 65557))
    tail = stream.read()
    pos = tail.rfind(b"PK\x05\x06")
    if pos < 0 or pos + 22 > len(tail):
        raise DataError("NPZ 压缩包目录无效或文件不完整。")
    _, disk, cd_disk, disk_count, count, cd_size, _, comment_len = struct.unpack_from("<4s4H2IH", tail, pos)
    if pos + 22 + comment_len != len(tail):
        raise DataError("NPZ 压缩包尾部无效。")
    if disk or cd_disk or disk_count != count:
        raise DataError("不支持分卷 NPZ。")
    if count > limits.members or cd_size > limits.directory_bytes:
        raise DataError("NPZ 目录过大（最多 1024 项、4 MiB 目录）；请分拆文件。")
    stream.seek(0)


class ArraySource:
    """A catalog reads headers only; load() owns only the chosen array's data."""
    def __init__(self, path: str | Path, limits: Limits | None = None):
        self.path = Path(path).expanduser().resolve()
        self.limits = limits or Limits()
        self.arrays: list[ArrayInfo] = []
        self.notes: list[str] = []
        self._stream = None
        self._zip = None
        self._signature = None
        try:
            if self.path.suffix.lower() not in (".npz", ".npy"):
                raise DataError("请选择 .npz 或 .npy 文件。")
            self._stream = self.path.open("rb")
            self._signature = self._stat()
            if self.path.suffix.lower() == ".npy":
                info = read_header(self._stream, self.path.stem, self.limits)
                self.arrays.append(self._validate(info, self._signature[0], self.limits.mapped_bytes))
            else:
                _check_zip_index(self._stream, self.limits)
                self._zip = zipfile.ZipFile(self._stream, "r")
                entries = self._zip.infolist()
                if len(entries) > self.limits.members:
                    raise DataError("NPZ 数组数量超过安全上限。")
                seen = set()
                for entry in entries:
                    if entry.is_dir() or not entry.filename.endswith(".npy"):
                        self.notes.append(f"忽略非 NPY 项：{entry.filename[:100]}")
                        continue
                    if entry.filename in seen:
                        raise DataError("NPZ 内含重名数组，无法可靠区分。")
                    seen.add(entry.filename)
                    if entry.flag_bits & 1:
                        raise DataError("不支持加密的 NPZ。")
                    if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                        raise DataError("仅支持标准 stored/deflate NPZ 压缩。")
                    # Check size/ratio before decompressing even the header.
                    if entry.file_size > self.limits.member_bytes + self.limits.header_bytes + 12:
                        raise DataError(f"数组 {entry.filename[:100]} 超过解压上限 {readable_size(self.limits.member_bytes)}。")
                    if entry.file_size / max(1, entry.compress_size) > self.limits.compression_ratio:
                        raise DataError("NPZ 压缩比过高，已停止解压；可改用未压缩的 NPY。")
                    with self._zip.open(entry, "r") as member_stream:
                        info = read_header(member_stream, entry.filename[:-4], self.limits, entry.filename)
                    self.arrays.append(self._validate(info, entry.file_size, self.limits.member_bytes))
            if not self.arrays:
                raise DataError("文件中没有 NPY 数组。")
        except Exception:
            self.close()
            raise

    def _stat(self):
        stat = self.path.stat()
        return stat.st_size, stat.st_mtime_ns, stat.st_ino

    @staticmethod
    def _validate(info, file_size, limit):
        if info.error:
            return info
        if info.nbytes > limit:
            raise DataError(f"数组 {info.name[:100]} 的估算内存 {readable_size(info.nbytes)} 超过安全上限 {readable_size(limit)}。")
        if info.offset + info.nbytes != file_size:
            raise DataError(f"数组 {info.name[:100]} 的头部与数据大小不一致，文件可能损坏。")
        return info

    def load(self, info: ArrayInfo) -> np.ndarray:
        if info not in self.arrays:
            raise DataError("所选数组不属于当前文件。")
        if info.error:
            raise DataError(info.error)
        if self._stream is None:
            raise DataError("文件已经关闭。")
        if self._stat() != self._signature:
            raise DataError("文件在打开后发生变化，请重新打开。")
        if self._zip is None:
            if info.nbytes:
                array = np.memmap(self._stream, dtype=info.dtype, mode="r", offset=info.offset,
                                  shape=info.shape, order="F" if info.fortran else "C")
            else:
                array = np.empty(info.shape, dtype=info.dtype)
        else:
            with self._zip.open(info.member, "r") as stream:
                again = read_header(stream, info.name, self.limits, info.member)
                if again != info:
                    raise DataError("数组头部发生变化，请重新打开。")
                array = np.empty(info.shape, dtype=info.dtype, order="F" if info.fortran else "C")
                raw = memoryview(array.ravel(order="K").view(np.uint8))
                for start in range(0, info.nbytes, 1024**2):
                    count = min(1024**2, info.nbytes - start)
                    raw[start:start + count] = _read_exact(stream, count)
                if stream.read(1):
                    raise DataError("数组含多余数据，文件可能损坏。")
        array.flags.writeable = False
        return array

    def column_labels(self) -> list[str] | None:
        """Only small, explicit text 'columns' metadata is treated as labels."""
        for info in self.arrays:
            if (info.name == "columns" and not info.error and len(info.shape) == 1
                    and info.shape[0] <= 1024 and info.nbytes <= 65536 and info.dtype.kind in "SU"):
                return [format_value(value, full=True) for value in self.load(info)]
        return None

    def close(self):
        if self._zip is not None:
            self._zip.close()
            self._zip = None
        if self._stream is not None:
            self._stream.close()
            self._stream = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def slice_view(array: np.ndarray, row_axis=0, col_axis=1, fixed=None) -> np.ndarray:
    """Return a 0D/1D/2D view; explicit axes determine rows and columns."""
    fixed = fixed or {}
    if array.ndim <= 1:
        return array
    if row_axis == col_axis or not (0 <= row_axis < array.ndim and 0 <= col_axis < array.ndim):
        raise DataError("行轴和列轴必须是两个不同的有效轴。")
    index = []
    for axis, length in enumerate(array.shape):
        if axis in (row_axis, col_axis):
            index.append(slice(None))
        else:
            value = fixed.get(axis, 0)
            if not 0 <= value < length:
                raise DataError(f"轴 {axis} 的切片索引应在 0 到 {length - 1}；空轴无法取切片。")
            index.append(value)
    result = array[tuple(index)]
    # Basic indexing retains original axis order, which may differ from the user's selection.
    return result if row_axis < col_axis else result.T


def table_shape(view):
    return (1, 1) if view.ndim == 0 else ((view.shape[0], 1) if view.ndim == 1 else view.shape)


def table_page(view, row=0, col=0, rows=50, cols=12):
    if rows < 1 or cols < 1 or rows > 100 or cols > 24:
        raise DataError("每页最多 100 行、24 列。")
    matrix = view.reshape(table_shape(view))
    height, width = matrix.shape
    if not 0 <= row < max(1, height) or not 0 <= col < max(1, width):
        raise DataError("起始行或列超出当前切片范围。")
    return matrix[row:row + rows, col:col + cols]


def format_value(value, full=False):
    if isinstance(value, (np.floating, float)):
        text = str(value) if full else f"{value:.8g}"
    elif isinstance(value, (np.complexfloating, complex)):
        text = str(value) if full else f"{value.real:.8g}{'-' if np.signbit(value.imag) else '+'}{abs(value.imag):.8g}j"
    elif isinstance(value, (bytes, np.bytes_)):
        text = bytes(value).decode("utf-8", errors="replace")
    else:
        text = str(value)
    text = text.replace("\x00", "\\0").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
    return text if full or len(text) <= 96 else text[:93] + "…"


def preview_sample(view, component="实部", max_line=2000, max_side=512):
    if view.dtype.kind not in "biufc":
        raise DataError("曲线和热图仅支持数值或布尔数组。")
    if view.ndim == 0:
        raise DataError("标量可在表格中直接查看，没有曲线或热图。")
    if view.size == 0:
        raise DataError("空数组没有可预览的数据。")
    if view.ndim == 1:
        indices = np.linspace(0, view.size - 1, min(view.size, max_line), dtype=np.intp)
        sample = view[indices]
    else:
        ri = np.linspace(0, view.shape[0] - 1, min(view.shape[0], max_side), dtype=np.intp)
        ci = np.linspace(0, view.shape[1] - 1, min(view.shape[1], max_side), dtype=np.intp)
        indices = (ri, ci)
        sample = view[np.ix_(ri, ci)]
    if component not in ("实部", "虚部", "幅值"):
        raise DataError("请选择实部、虚部或幅值。")
    # Convert only the bounded sample. Never transform an entire mapped matrix.
    with np.errstate(over="ignore", invalid="ignore"):
        if component == "幅值":
            sample = np.abs(sample.astype(np.complex128 if np.iscomplexobj(sample) else np.float64))
        else:
            sample = (sample.imag if component == "虚部" else sample.real).astype(np.float64)
    return indices, sample


def normalized_finite(values):
    finite = np.isfinite(values)
    if not finite.any():
        raise DataError("抽样数据没有有限值，无法确定预览色阶/纵轴。")
    low, high = float(values[finite].min()), float(values[finite].max())
    scale = max(abs(low), abs(high), 1e-300)
    normalized = np.zeros(values.shape, dtype=float)
    if high == low:
        normalized[finite] = 0.5
    else:
        normalized[finite] = (values[finite] / scale - low / scale) / (high / scale - low / scale)
    return normalized, finite, low, high


def heatmap_rgb(values):
    normalized, finite, low, high = normalized_finite(values)
    anchors = np.array([[24, 52, 103], [24, 148, 160], [249, 222, 79]], dtype=float)
    rgb = np.stack([np.interp(normalized, [0, .5, 1], anchors[:, channel]) for channel in range(3)], axis=-1).astype(np.uint8)
    rgb[~finite] = (180, 180, 180)
    return rgb, low, high
