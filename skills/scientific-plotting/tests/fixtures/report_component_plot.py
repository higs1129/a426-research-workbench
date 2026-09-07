"""Synthetic two-series point-line regression; no research records."""
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator


def load_data():
    return list(range(1, 17)), [20 + (i * 7 % 19) for i in range(16)]


def build_figure(data, profile):
    x, y = data
    fig, ax = plt.subplots(constrained_layout=True)
    first, = ax.plot(x, y, marker="o", label="Group A", color="#0072b2")
    second, = ax.plot(x, [v / 2 for v in y], marker="o", linewidth=0.7, label="Group B", color="#d55e00")
    ax.set(xlabel="Sample", ylabel="Response (dB)", xlim=(0.5, 16.5), ylim=(0, 60))
    ax.xaxis.set_major_locator(FixedLocator([1, 4, 7, 10, 13, 16]))
    ax.yaxis.set_major_locator(FixedLocator([0, 10, 20, 30, 40, 50, 60]))
    ax.legend(loc="lower left", frameon=False)
    return {"figure": fig, "axes": ax, "series": [first, second]}
