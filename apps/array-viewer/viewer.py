"""Offline, read-only NumPy array viewer. Run with an optional NPY/NPZ path."""
from __future__ import annotations

import argparse
import queue
import sys
import threading

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    import numpy as np
    from PIL import Image, ImageTk
    if not hasattr(Image, "Resampling"):
        raise ImportError("需要 Pillow 9.1 或更新版本")
    from array_data import (ArraySource, DataError, format_value, heatmap_rgb,
                            normalized_finite, preview_sample, readable_size,
                            slice_view, table_page, table_shape)
except ImportError as exc:
    raise SystemExit(f"缺少依赖：{exc}。请使用已安装 NumPy、Pillow 和 tkinter 的 Python；参见 README.md。")


class ArrayViewer:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.source = None
        self.array = None
        self.info = None
        self.view = None
        self.labels = None
        self.busy = False
        self.closed = False
        self.messages = queue.Queue()
        self.fixed = {}
        self.plot_after = None
        self.photo = None
        self.last_error = ""
        root.title("NumPy 数据查看器 · 只读")
        root.geometry("1320x820")
        root.minsize(1020, 650)
        root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", rowheight=27, font=("Consolas", 10))
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 10))
        root.option_add("*Font", ("Microsoft YaHei UI", 10))

        top = ttk.Frame(root, padding=10)
        top.pack(fill="x")
        self.open_button = ttk.Button(top, text="打开文件…", command=self.choose_file)
        self.open_button.pack(side="left")
        self.path_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.path_var)
        entry.pack(side="left", fill="x", expand=True, padx=8)
        entry.bind("<Return>", lambda _: self.open_path(self.path_var.get()))
        self.path_button = ttk.Button(top, text="打开路径", command=lambda: self.open_path(self.path_var.get()))
        self.path_button.pack(side="left")
        ttk.Label(top, text="  离线 · 只读").pack(side="left")

        panes = ttk.Panedwindow(root, orient="horizontal")
        panes.pack(fill="both", expand=True, padx=10)
        left = ttk.Frame(panes, width=440)
        right = ttk.Frame(panes)
        panes.add(left, weight=0)
        panes.add(right, weight=1)
        ttk.Label(left, text="变量  /  估算内存为数组数据大小", padding=(0, 0, 0, 6)).pack(anchor="w")
        catalog_frame = ttk.Frame(left)
        catalog_frame.pack(fill="both", expand=True)
        self.catalog = ttk.Treeview(catalog_frame, columns=("dtype", "shape", "memory"), selectmode="browse")
        self.catalog.heading("#0", text="名称")
        self.catalog.column("#0", width=135, minwidth=90)
        for key, label, width in (("dtype", "dtype", 85), ("shape", "shape", 135), ("memory", "内存", 80)):
            self.catalog.heading(key, text=label)
            self.catalog.column(key, width=width, minwidth=65)
        self.catalog.grid(row=0, column=0, sticky="nsew")
        bar = ttk.Scrollbar(catalog_frame, orient="vertical", command=self.catalog.yview)
        bar.grid(row=0, column=1, sticky="ns")
        hbar = ttk.Scrollbar(catalog_frame, orient="horizontal", command=self.catalog.xview)
        hbar.grid(row=1, column=0, sticky="ew")
        self.catalog.configure(yscrollcommand=bar.set, xscrollcommand=hbar.set)
        catalog_frame.rowconfigure(0, weight=1)
        catalog_frame.columnconfigure(0, weight=1)
        self.catalog.bind("<<TreeviewSelect>>", self.select_array)
        self.catalog.tag_configure("unsupported", foreground="#9c4535")
        ttk.Label(left, text="索引从 0 开始；红色变量为不支持的类型。\n选择变量后查看原始值，预览不修改数据。", padding=(0, 8)).pack(anchor="w")

        self.info_var = tk.StringVar(value="打开 .npz / .npy，选择左侧变量开始查看。")
        ttk.Label(right, textvariable=self.info_var, wraplength=750, padding=(10, 0, 4, 6)).pack(anchor="w")
        controls = ttk.Frame(right, padding=(10, 2))
        controls.pack(fill="x")
        ttk.Label(controls, text="行轴").pack(side="left")
        self.row_axis = tk.StringVar(value="0")
        self.col_axis = tk.StringVar(value="1")
        self.row_combo = ttk.Combobox(controls, textvariable=self.row_axis, width=5, state="disabled")
        self.row_combo.pack(side="left", padx=(4, 12))
        ttk.Label(controls, text="列轴").pack(side="left")
        self.col_combo = ttk.Combobox(controls, textvariable=self.col_axis, width=5, state="disabled")
        self.col_combo.pack(side="left", padx=4)
        for combo in (self.row_combo, self.col_combo):
            combo.bind("<<ComboboxSelected>>", lambda _: self.rebuild_slices())
        ttk.Label(controls, text="  选择顺序就是显示顺序").pack(side="left")
        self.slice_frame = ttk.Frame(right, padding=(10, 4))
        self.slice_frame.pack(fill="x")
        self.slice_var = tk.StringVar()
        ttk.Label(right, textvariable=self.slice_var, wraplength=750, padding=(10, 2)).pack(anchor="w")

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True, padx=(10, 0), pady=6)
        data_tab = ttk.Frame(self.tabs)
        plot_tab = ttk.Frame(self.tabs)
        self.tabs.add(data_tab, text=" 数值表格 ")
        self.tabs.add(plot_tab, text=" 快速预览 ")
        self.tabs.bind("<<NotebookTabChanged>>", lambda _: self.schedule_plot())
        pagebar = ttk.Frame(data_tab, padding=6)
        pagebar.pack(fill="x")
        self.row_start = tk.StringVar(value="0")
        self.col_start = tk.StringVar(value="0")
        for label, variable in (("起始行", self.row_start), ("起始列", self.col_start)):
            ttk.Label(pagebar, text=label).pack(side="left")
            widget = ttk.Entry(pagebar, textvariable=variable, width=7)
            widget.pack(side="left", padx=(4, 8))
            widget.bind("<Return>", lambda _: self.render_table())
        ttk.Button(pagebar, text="跳转", command=self.render_table, width=5).pack(side="left")
        for label, dr, dc in (("↑", -50, 0), ("↓", 50, 0), ("←", 0, -12), ("→", 0, 12)):
            ttk.Button(pagebar, text=label, width=3, command=lambda r=dr, c=dc: self.move_page(r, c)).pack(side="left", padx=2)
        self.page_var = tk.StringVar()
        ttk.Label(data_tab, textvariable=self.page_var, padding=(6, 0)).pack(anchor="w")
        table_frame = ttk.Frame(data_tab)
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_frame, selectmode="browse")
        self.table.heading("#0", text="行 \\ 列")
        self.table.column("#0", width=80, stretch=False)
        self.table.grid(row=0, column=0, sticky="nsew")
        vscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        vscroll.grid(row=0, column=1, sticky="ns")
        hscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        hscroll.grid(row=1, column=0, sticky="ew")
        self.table.configure(yscrollcommand=vscroll.set, xscrollcommand=hscroll.set)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.table.bind("<ButtonRelease-1>", self.inspect_cell)
        ttk.Label(data_tab, text="表格显示约 8 位有效数值；点击单元格，在下方查看原始精度字符串。", padding=6).pack(anchor="w")
        self.cell_var = tk.StringVar()
        ttk.Entry(data_tab, textvariable=self.cell_var, state="readonly").pack(fill="x", padx=6, pady=(0, 6))

        plotbar = ttk.Frame(plot_tab, padding=6)
        plotbar.pack(fill="x")
        ttk.Label(plotbar, text="预览分量").pack(side="left")
        self.component = tk.StringVar(value="实部")
        self.component_combo = ttk.Combobox(plotbar, textvariable=self.component, values=("实部", "虚部", "幅值"), state="readonly", width=8)
        self.component_combo.pack(side="left", padx=6)
        self.component_combo.bind("<<ComboboxSelected>>", lambda _: self.render_plot())
        ttk.Label(plotbar, text="灰色 / 曲线断开：NaN、Inf；色阶为抽样范围").pack(side="left")
        self.plot_var = tk.StringVar(value="选择数组后显示当前切片。")
        ttk.Label(plot_tab, textvariable=self.plot_var, wraplength=750, padding=(6, 0)).pack(anchor="w")
        self.canvas = tk.Canvas(plot_tab, background="#fafbfc", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=6, pady=6)
        self.canvas.bind("<Configure>", lambda _: self.schedule_plot())
        self.status = tk.StringVar(value="就绪。文件只以读取方式打开，不产生数据副本或导出文件。")
        ttk.Label(root, textvariable=self.status, padding=10, wraplength=1250).pack(fill="x")
        root.bind("<Control-o>", lambda _: self.choose_file())
        self.poll_id = root.after(50, self.poll)

    def error(self, exc):
        self.last_error = str(exc)
        self.status.set(f"无法完成：{exc}")
        messagebox.showerror("无法查看数据", str(exc), parent=self.root)

    def run_job(self, work, done):
        if self.busy:
            return
        self.busy = True
        self.open_button.state(["disabled"])
        self.path_button.state(["disabled"])
        self.status.set("正在读取… 窗口保持响应；完成后可继续选择。")

        def worker():
            try:
                result = work()
            except Exception as exc:
                self.messages.put((False, exc, done))
            else:
                self.messages.put((True, result, done))
        threading.Thread(target=worker, daemon=True, name="array-reader").start()

    def poll(self):
        if self.closed:
            return
        try:
            ok, value, done = self.messages.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.open_button.state(["!disabled"])
            self.path_button.state(["!disabled"])
            if ok:
                done(value)
            else:
                self.error(value)
        self.poll_id = self.root.after(50, self.poll)

    def choose_file(self):
        if self.busy:
            return
        path = filedialog.askopenfilename(parent=self.root, title="打开 NumPy 数据（只读）",
                                          filetypes=[("NumPy 数据", "*.npz *.npy"), ("所有文件", "*.*")])
        if path:
            self.open_path(path)

    def open_path(self, path):
        path = str(path).strip().strip('"')
        if not path or self.busy:
            return

        def work():
            source = ArraySource(path)
            try:
                return source, source.column_labels()
            except Exception:
                source.close()
                raise

        def done(value):
            if self.source:
                self.source.close()
            self.source, self.labels = value
            self.array = self.view = self.info = None
            self.path_var.set(str(self.source.path))
            self.root.title(f"{self.source.path.name} — NumPy 数据查看器 · 只读")
            self.catalog.delete(*self.catalog.get_children())
            for index, info in enumerate(self.source.arrays):
                self.catalog.insert("", "end", iid=str(index), text=info.name, values=(str(info.dtype), str(info.shape), readable_size(info.nbytes)), tags=("unsupported",) if info.error else ())
            self.status.set(f"已打开 {len(self.source.arrays)} 个数组。" + "；".join(self.source.notes[:3]))
            selected = next((i for i, item in enumerate(self.source.arrays) if not item.error and item.name != "columns"), 0)
            self.catalog.selection_set(str(selected))
            self.catalog.see(str(selected))
        self.run_job(work, done)

    def select_array(self, _=None):
        selection = self.catalog.selection()
        if self.busy:
            if self.info and self.source:
                expected = str(self.source.arrays.index(self.info))
                if selection != (expected,):
                    self.catalog.selection_set(expected)
            return
        if not selection or not self.source:
            return
        info = self.source.arrays[int(selection[0])]
        if info is self.info:
            return
        self.info = info
        self.array = self.view = None
        self.fixed = {}
        for child in self.slice_frame.winfo_children():
            child.destroy()
        self.row_combo.configure(state="disabled")
        self.col_combo.configure(state="disabled")
        self.table.delete(*self.table.get_children())
        self.table.configure(columns=())
        self.canvas.delete("all")
        self.cell_var.set("")
        self.page_var.set("")
        self.slice_var.set("")
        self.info_var.set(f"{info.name}   dtype={info.dtype}   shape={info.shape}   {readable_size(info.nbytes)}" + ("   [Fortran 存储]" if info.fortran else ""))
        if info.error:
            self.status.set(info.error)
            return

        def done(array):
            self.array = array
            self.row_axis.set("0")
            self.col_axis.set("1" if array.ndim >= 2 else "—")
            for combo in (self.row_combo, self.col_combo):
                combo.configure(values=tuple(range(array.ndim)), state="readonly" if array.ndim >= 2 else "disabled")
            self.component.set("幅值" if np.iscomplexobj(array) else "实部")
            self.fixed = {}
            self.rebuild_slices()
            self.status.set("只读加载完成。表格显示原始复数；预览可选择实部、虚部或幅值。" if np.iscomplexobj(array) else "只读加载完成。索引从 0 开始。")
        self.run_job(lambda: self.source.load(info), done)

    def matching_labels(self):
        return bool(self.array is not None and self.array.ndim >= 2 and self.labels
                    and len(self.labels) == self.array.shape[-1])

    def rebuild_slices(self):
        if self.array is None:
            return
        old = {axis: variable.get() for axis, variable in self.fixed.items()}
        for child in self.slice_frame.winfo_children():
            child.destroy()
        self.fixed = {}
        try:
            axes = {int(self.row_axis.get()), int(self.col_axis.get())} if self.array.ndim >= 2 else {0}
            if self.array.ndim >= 2 and len(axes) != 2:
                self.view = None
                self.table.delete(*self.table.get_children())
                self.canvas.delete("all")
                self.slice_var.set("请为行、列选择不同的轴。")
                return
            for i, axis in enumerate(a for a in range(self.array.ndim) if a not in axes):
                cell = ttk.Frame(self.slice_frame)
                cell.grid(row=i // 3, column=i % 3, sticky="w", pady=2, padx=(0, 12))
                ttk.Label(cell, text=f"轴 {axis} [0…{self.array.shape[axis] - 1}]").pack(side="left")
                var = tk.StringVar(value=old.get(axis, "0"))
                self.fixed[axis] = var
                if self.matching_labels() and axis == self.array.ndim - 1:
                    values = [f"{j} · {label[:50]}" for j, label in enumerate(self.labels)]
                    index = int(var.get().split(" · ")[0])
                    var.set(values[index] if 0 <= index < len(values) else values[0])
                    widget = ttk.Combobox(cell, textvariable=var, values=values, state="readonly", width=19)
                    widget.bind("<<ComboboxSelected>>", lambda _: self.apply_slice())
                else:
                    widget = ttk.Spinbox(cell, textvariable=var, from_=0, to=max(0, self.array.shape[axis] - 1), width=7, command=self.apply_slice)
                    widget.bind("<Return>", lambda _: self.apply_slice())
                widget.pack(side="left", padx=4)
            if self.fixed:
                ttk.Button(self.slice_frame, text="应用切片", command=self.apply_slice).grid(row=(len(self.fixed) + 2) // 3, column=0, sticky="w")
            self.apply_slice()
        except (ValueError, DataError) as exc:
            self.error(exc)

    def apply_slice(self):
        if self.array is None:
            return
        try:
            fixed = {axis: int(var.get().split(" · ")[0]) for axis, var in self.fixed.items()}
            row, col = (int(self.row_axis.get()), int(self.col_axis.get())) if self.array.ndim >= 2 else (0, 1)
            self.view = slice_view(self.array, row, col, fixed)
            if self.array.ndim >= 2:
                parts = [":" if axis in (row, col) else str(fixed[axis]) for axis in range(self.array.ndim)]
                description = f"{self.info.name}[{', '.join(parts)}] → 行轴 {row}、列轴 {col}；切片 shape={self.view.shape}"
            else:
                description = "标量：单个值" if self.array.ndim == 0 else f"一维数组：轴 0 显示为行，长度 {self.array.size}"
            if self.matching_labels():
                description += "；columns 与末轴长度匹配，作为辅助标签"
            self.slice_var.set(description)
            self.row_start.set("0")
            self.col_start.set("0")
            self.cell_var.set("")
            self.render_table()
            self.schedule_plot()
        except (ValueError, DataError) as exc:
            self.view = None
            self.table.delete(*self.table.get_children())
            self.canvas.delete("all")
            self.slice_var.set(f"切片无效：{exc}")
            self.error(exc)

    def render_table(self):
        if self.view is None:
            return
        try:
            row, col = int(self.row_start.get()), int(self.col_start.get())
            page = table_page(self.view, row, col)
        except (ValueError, DataError) as exc:
            self.error(exc)
            return
        self.table.delete(*self.table.get_children())
        self.table.configure(columns=tuple(f"c{i}" for i in range(page.shape[1])))
        for j in range(page.shape[1]):
            heading = str(col + j) if self.view.ndim == 2 else "值"
            if self.matching_labels() and int(self.col_axis.get()) == self.array.ndim - 1:
                heading += f" · {self.labels[col + j]}"
            self.table.heading(f"c{j}", text=heading)
            self.table.column(f"c{j}", width=165 if np.iscomplexobj(self.view) else 130, minwidth=70, stretch=False)
        for i, values in enumerate(page):
            label = str(row + i)
            if self.matching_labels() and int(self.row_axis.get()) == self.array.ndim - 1:
                label += f" · {self.labels[row + i]}"
            self.table.insert("", "end", iid=str(i), text=label, values=tuple(format_value(value) for value in values))
        self.page_origin = row, col
        height, width = table_shape(self.view)
        self.page_var.set(f"总计 {height} 行 × {width} 列；本页 {page.shape[0]} 行 × {page.shape[1]} 列（每页最多 50 × 12）")

    def move_page(self, dr, dc):
        if self.view is None:
            return
        try:
            height, width = table_shape(self.view)
            self.row_start.set(str(max(0, min(int(self.row_start.get()) + dr, max(0, height - 1)))))
            self.col_start.set(str(max(0, min(int(self.col_start.get()) + dc, max(0, width - 1)))))
            self.render_table()
        except ValueError as exc:
            self.error(exc)

    def inspect_cell(self, event):
        if self.view is None or self.table.identify_region(event.x, event.y) != "cell":
            return
        iid = self.table.identify_row(event.y)
        column = self.table.identify_column(event.x)
        if not iid or column == "#0":
            return
        row = self.page_origin[0] + int(iid)
        col = self.page_origin[1] + int(column[1:]) - 1
        value = self.view.reshape(table_shape(self.view))[row, col]
        text = format_value(value, full=True)
        if len(text) > 4096:
            text = text[:4096] + "…（长文本已截断）"
        self.cell_var.set(f"当前切片 [{row}, {col}] = {text}")

    def schedule_plot(self):
        if self.plot_after:
            self.root.after_cancel(self.plot_after)
        self.plot_after = self.root.after(120, self.render_plot)

    def render_plot(self):
        self.plot_after = None
        if self.closed or self.view is None or self.tabs.index(self.tabs.select()) != 1:
            return
        canvas = self.canvas
        canvas.delete("all")
        self.photo = None
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 100 or height < 100:
            return
        try:
            indices, values = preview_sample(self.view, self.component.get())
            normalized, finite, low, high = normalized_finite(values)
        except DataError as exc:
            self.plot_var.set(str(exc))
            return
        left, top, bottom = 82, 30, height - 65
        right = max(left + 30, width - (150 if values.ndim == 2 else 30))
        if values.ndim == 1:
            previous = None
            for i, original in enumerate(indices):
                if not finite[i]:
                    previous = None
                    continue
                x = left + (right - left) * int(original) / max(1, self.view.size - 1)
                y = bottom - normalized[i] * (bottom - top)
                if previous:
                    canvas.create_line(*previous, x, y, fill="#188a9c", width=2)
                else:
                    canvas.create_oval(x - 2, y - 2, x + 2, y + 2, fill="#188a9c", outline="")
                previous = x, y
            canvas.create_text(left - 8, top, text=f"{high:.5g}", anchor="e")
            canvas.create_text(left - 8, bottom, text=f"{low:.5g}", anchor="e")
            xlast = self.view.size - 1
            xlabel = "轴 0 索引"
            title = f"{self.component.get()}曲线"
            detail = f"{self.view.size} 点 → {values.size} 个等间距样本（含端点）；不插值、不聚合，抽样可能漏掉窄峰"
        else:
            rgb, low, high = heatmap_rgb(values)
            self.photo = ImageTk.PhotoImage(Image.fromarray(rgb).resize((right - left, bottom - top), Image.Resampling.NEAREST), master=self.root)
            canvas.create_image(left, top, anchor="nw", image=self.photo)
            for i in range(100):
                color, _, _ = heatmap_rgb(np.array([[0., i / 99, 1.]]))
                hex_color = "#%02x%02x%02x" % tuple(color[0, 1])
                yy = bottom - (bottom - top) * i / 100
                canvas.create_rectangle(right + 22, yy - (bottom - top) / 100, right + 40, yy, fill=hex_color, outline=hex_color)
            canvas.create_text(right + 45, top, text=f"{high:.5g}", anchor="w")
            canvas.create_text(right + 45, bottom, text=f"{low:.5g}", anchor="w")
            canvas.create_text(left - 8, top, text="0", anchor="e")
            canvas.create_text(left - 8, bottom, text=str(self.view.shape[0] - 1), anchor="e")
            canvas.create_text(20, (top + bottom) / 2, text=f"行轴 {self.row_axis.get()}\n索引", anchor="w")
            xlast = self.view.shape[1] - 1
            xlabel = f"列轴 {self.col_axis.get()} 索引"
            title = f"{self.component.get()}热图 · 第 0 行在顶部"
            detail = f"切片 {self.view.shape} → 等间距抽样 {values.shape}（含端点）；按索引拉伸显示，非物理坐标/比例"
        canvas.create_rectangle(left, top, right, bottom, outline="#697789")
        canvas.create_text(left, bottom + 17, text="0")
        canvas.create_text(right, bottom + 17, text=str(xlast))
        canvas.create_text((left + right) / 2, bottom + 42, text=xlabel)
        canvas.create_text((left + right) / 2, 13, text=title)
        self.plot_var.set(detail + f"；非有限样本 {values.size - int(finite.sum())}")

    def close(self):
        self.closed = True
        self.root.after_cancel(self.poll_id)
        if self.plot_after:
            self.root.after_cancel(self.plot_after)
        # Do not close a stream while a reader thread is using it. Daemon workers
        # cannot keep the process alive; the OS closes their read-only handles.
        if self.source and not self.busy:
            self.source.close()
        self.view = self.array = None
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="离线、只读的 NPZ / NPY 数据查看器")
    parser.add_argument("path", nargs="?", help="要打开的 .npz / .npy 文件")
    parser.add_argument("--check", action="store_true", help="检查依赖和 Tk 窗口创建，然后退出")
    args = parser.parse_args()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise SystemExit(f"无法创建 Tk 桌面窗口：{exc}")
    if args.check:
        root.withdraw()
        print(f"Python {sys.version.split()[0]} | NumPy {np.__version__} | Tk {root.tk.call('info', 'patchlevel')} | Pillow OK")
        root.destroy()
        return
    app = ArrayViewer(root)
    if args.path:
        root.after(100, lambda: app.open_path(args.path))
    root.mainloop()


if __name__ == "__main__":
    main()
