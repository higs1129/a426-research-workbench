"""Synthetic single scatter with an explicit legend and fixed ticks."""
from report_component_plot import load_data
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator


def build_figure(data, profile):
    x, y = data
    fig, ax = plt.subplots(constrained_layout=True)
    points, = ax.plot(x, y, linestyle="none", marker="o", label="Scatter A", color="#0072b2")
    ax.set(xlabel="Sample", ylabel="Response (dB)", xlim=(0.5, 16.5), ylim=(0, 60))
    ax.xaxis.set_major_locator(FixedLocator([1, 4, 7, 10, 13, 16]))
    ax.legend(loc="lower left", frameon=False)
    return {"figure": fig, "axes": ax, "series": [points]}
