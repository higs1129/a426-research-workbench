"""Exercise real Tk widgets (programmatic interaction, not a visual assertion).

Optionally accepts the user's water_local.npz for read-only acceptance. Fixtures
and any artifacts stay under this application's tests/artifacts directory.
"""
import argparse
import hashlib
from pathlib import Path
import sys
import time
import tkinter as tk

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from viewer import ArrayViewer
from array_data import ArraySource, format_value, slice_view


def fingerprint(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024**2), b""):
            sha.update(chunk)
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, sha.hexdigest()


def run(real=None):
    artifacts = Path(__file__).resolve().parent / "artifacts"
    artifacts.mkdir(exist_ok=True)
    fixture = artifacts / "gui-fixture.npz"
    np.savez(fixture, matrix=np.arange(3000).reshape(60, 50),
             complex_line=np.array([1 + 2j, -3 - 4j, np.nan, np.inf, 5 + 1j]),
             cube=np.arange(3 * 4 * 5 * 6).reshape(3, 4, 5, 6),
             scalar=np.array(1.2345678901234567), empty=np.empty((0, 3)),
             text=np.array(["中文", "NaN 不代表文本缺失"]))
    root = tk.Tk()
    app = ArrayViewer(root)
    callbacks = []
    root.report_callback_exception = lambda *error: callbacks.append(error)

    def wait_ready():
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            root.update()
            if not app.busy and app.array is not None:
                root.update()
                assert not callbacks, callbacks
                return
            time.sleep(.01)
        raise AssertionError(f"GUI timed out: {app.last_error}")

    def select(name):
        index = next(i for i, item in enumerate(app.source.arrays) if item.name == name)
        app.catalog.selection_set(str(index))
        root.update()
        wait_ready()

    try:
        app.open_path(fixture)
        wait_ready()
        assert len(app.table.get_children()) == 50
        app.move_page(50, 12)
        assert app.page_origin == (50, 12)
        assert app.table.item("0", "values")[0] == "2512"
        app.tabs.select(1)
        root.update()
        app.render_plot()
        assert app.photo is not None
        select("complex_line")
        for component in ("实部", "虚部", "幅值"):
            app.component.set(component)
            app.render_plot()
            assert app.canvas.find_all()
        select("cube")
        app.row_axis.set("3")
        app.col_axis.set("0")
        app.rebuild_slices()
        app.fixed[1].set("2")
        app.fixed[2].set("3")
        app.apply_slice()
        assert app.view.shape == (6, 3)
        assert app.view[5, 2] == app.array[2, 2, 3, 5]
        select("scalar")
        assert app.table.item("0", "values")[0] == format_value(app.array[()])
        select("empty")
        assert not app.table.get_children()
        app.render_plot()
        assert "空数组" in app.plot_var.get()
        select("text")
        assert app.table.item("0", "values")[0] == "中文"

        if real:
            paths = [real]
            for name in ("water_overview.npz", "water_coreline.npz"):
                candidate = real.with_name(name)
                if candidate.is_file():
                    paths.append(candidate)
            before = {path: fingerprint(path) for path in paths}
            app.open_path(real)
            wait_ready()
            select("values")
            assert app.array.dtype == np.dtype("float64")
            assert app.array.shape == (301, 401, 5)
            assert app.labels == ["r_um", "z_um", "dT_K", "q_r_W_m2", "q_z_W_m2"]
            app.fixed[2].set("2 · dT_K")
            app.apply_slice()
            assert app.view.shape == (301, 401)
            with np.load(real, allow_pickle=False) as reference:
                np.testing.assert_array_equal(app.view, reference["values"][:, :, 2])
            app.tabs.select(0)
            root.update()
            for row, col in ((0, 0), (150, 200), (300, 400)):
                app.row_start.set(str(row))
                app.col_start.set(str(col))
                app.render_table()
                assert app.table.item("0", "values")[0] == format_value(app.array[row, col, 2])
            app.tabs.select(1)
            root.update()
            app.render_plot()
            assert app.photo is not None
            for path in paths[1:]:
                with ArraySource(path) as source, np.load(path, allow_pickle=False) as reference:
                    for info in source.arrays:
                        if not info.error:
                            np.testing.assert_array_equal(source.load(info), reference[info.name])
                    print(f"REAL: {path.name}: " + ", ".join(f"{i.name} {i.shape} {i.dtype}" for i in source.arrays))
            after = {path: fingerprint(path) for path in paths}
            assert before == after, "An input file changed during acceptance"
            for path, value in before.items():
                print(f"UNCHANGED: {path.name}: bytes={value[0]}, mtime_ns={value[1]}, sha256={value[2]}")
            print("REAL: water_local values[:, :, 2] -> (301, 401); full slice equals NumPy reference")
        root.update()
        assert not callbacks, callbacks
        assert not app.last_error, app.last_error
        print("PASS: actual Tk startup, async load, table paging, axis order, complex components, heatmap, empty/text/scalar widgets")
    finally:
        app.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", type=Path, help="Explicit read-only water_local.npz acceptance path")
    run(parser.parse_args().real)
