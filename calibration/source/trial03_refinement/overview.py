"""Export the eight development circles with endpoint and turn-count context."""
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/trial03_matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from setup import OUT


def main():
    names = ["LAT4_L150_s1", "LAT4_R150_s2", "LAT4_L75_s1", "LAT4_R75_s1",
             "LAT4_L120_s1", "LAT4_R120_s1", "LAT5_L_s1", "LAT5_L_s2"]
    metrics = pd.read_csv(OUT / "metrics.csv").set_index(["label", "session"])
    fig, axes = plt.subplots(4, 2, figsize=(12, 17), layout="constrained")
    for ax, name in zip(axes.flat, names):
        base = pd.read_csv(OUT / "comparisons" / ("T0_" + name + ".csv"))
        final = pd.read_csv(OUT / "comparisons" / ("R5_" + name + ".csv"))
        x0, y0 = base.observed_x.iloc[0], base.observed_y.iloc[0]
        ax.plot(base.observed_x-x0, base.observed_y-y0, color="black", lw=2, label="Recorded")
        ax.plot(base.native_x-x0, base.native_y-y0, color="#cd7c30", lw=1.1, alpha=.8, label="trial03")
        ax.plot(final.native_x-x0, final.native_y-y0, color="#1678bd", lw=1.2, label="R5")
        ax.scatter([base.observed_x.iloc[-1]-x0, base.native_x.iloc[-1]-x0, final.native_x.iloc[-1]-x0],
                   [base.observed_y.iloc[-1]-y0, base.native_y.iloc[-1]-y0, final.native_y.iloc[-1]-y0],
                   c=["black", "#cd7c30", "#1678bd"], marker="x", s=45, zorder=5)
        before, after = metrics.loc[("T0", name)], metrics.loc[("R5", name)]
        ax.set_title(f"{name} | endpoint: {before.endpoint_m:.2f} to {after.endpoint_m:.2f} m\n"
                     f"signed turns, recorded / trial03 / R5: {after.observed_turns:.3f} / "
                     f"{before.native_turns:.3f} / {after.native_turns:.3f}", fontsize=10)
        ax.set(xlabel="Rear axle X from initial pose (m)", ylabel="Rear axle Y from initial pose (m)")
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(alpha=.2)
    axes.flat[0].legend(fontsize=9)
    fig.suptitle("Eight development circles: fixed inputs, continuous replay\n"
                 "Initial pose only; no post-hoc alignment. All eight were exposed to calibration.", fontsize=13)
    for extension in ["png", "pdf"]:
        fig.savefig(OUT / ("circle_comparison_R5." + extension), dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
