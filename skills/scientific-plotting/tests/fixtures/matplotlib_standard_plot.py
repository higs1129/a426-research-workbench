"""Representative standard-data plot for the Matplotlib editable fast path."""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator


def load_data():
    frequency = np.linspace(-40.0, 40.0, 2401)
    transmission = 1.0 - 0.48 / (1.0 + (frequency / 4.2) ** 2)
    transmission += 0.012 * np.sin(frequency * 1.8)
    return frequency, transmission


def build_figure(data, profile):
    frequency, transmission = data
    figure, axes = plt.subplots(constrained_layout=True)
    line, = axes.plot(
        frequency,
        transmission,
        color="#2878B5",
        linewidth=profile["rawWidthPt"],
        label="Measured transmission",
    )
    axes.set_title("Optical transmission spectrum")
    axes.set_xlabel("Relative frequency (GHz)")
    axes.set_ylabel("Normalized transmission")
    axes.set_xlim(-40, 40)
    axes.set_ylim(0.48, 1.04)
    axes.yaxis.set_major_locator(MultipleLocator(0.2))
    axes.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, 1.0),
        borderaxespad=0.8,
        frameon=False,
    )
    return {"figure": figure, "axes": axes, "series": [line]}
