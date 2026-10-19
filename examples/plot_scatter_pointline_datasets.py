"""Render four seaborn dataset comparisons with the shared plotting skill."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scientific-plotting" / "scripts"))
from plot_template import _check_text_layout, _hide_edge_grids, render_plot


OUTPUT = ROOT / "figures" / "scatter_pointline"
DATA = OUTPUT / "data"
SOURCE = "https://raw.githubusercontent.com/mwaskom/seaborn-data/master"
TIME_ORDER = ("1 min", "15 min", "30 min")
KIND_ORDER = ("rest", "walking", "running")


def load_dataset(name: str) -> tuple[pd.DataFrame, dict]:
    DATA.mkdir(parents=True, exist_ok=True)
    snapshot = DATA / f"{name}.csv"
    source = f"{SOURCE}/{name}.csv"
    if not snapshot.exists():
        temporary = snapshot.with_suffix(".download")
        try:
            subprocess.run(
                ["curl", "--fail", "--location", "--silent", "--show-error",
                 "--retry", "2", "--connect-timeout", "20", "--max-time", "120",
                 source, "--output", str(temporary)],
                check=True,
            )
            pd.read_csv(temporary)
            temporary.replace(snapshot)
        finally:
            temporary.unlink(missing_ok=True)
    frame = pd.read_csv(snapshot)
    return frame, {
        "dataset": name,
        "source": source,
        "snapshot": str(snapshot.resolve()),
        "sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        "original_rows": len(frame),
    }


def group_order(frame: pd.DataFrame, column: str, labels: tuple[str, ...]) -> pd.DataFrame:
    return pd.concat([frame.loc[frame[column] == label] for label in labels], ignore_index=True)


def save_plot(frame: pd.DataFrame, filename: str, *, kind: str, x: str, y: str,
              group: str, xlabel: str, ylabel: str, title: str) -> dict:
    figure, axes, _ = render_plot(
        frame, kind=kind, x=x, y=y, group=group, group_kind="categorical",
        xlabel=xlabel, ylabel=ylabel, title=title, size="double",
    )
    try:
        if kind == "scatter":
            for collection in axes.collections:
                collection.set_alpha(0.7)
            for handle in axes.get_legend().legend_handles:
                handle.set_alpha(0.7)
            assert not axes.lines
            assert sum(len(collection.get_offsets()) for collection in axes.collections) == len(frame)
            assert all(collection.get_alpha() == 0.7 for collection in axes.collections)
            marker_shapes = {collection.get_paths()[0].vertices.tobytes() for collection in axes.collections}
            assert len(marker_shapes) == frame[group].nunique()
        else:
            axes.set_xticks([1, 15, 30], TIME_ORDER)
            assert len(axes.lines) == 3
            for line in axes.lines:
                assert line.get_marker() not in (None, "None", "")
                assert line.get_linestyle() not in (None, "None", "")
                np.testing.assert_array_equal(line.get_xdata(), [1, 15, 30])
                expected = frame.loc[frame[group] == line.get_label(), y].to_numpy()
                np.testing.assert_allclose(line.get_ydata(), expected)
        assert axes.get_title() and axes.get_xlabel() and axes.get_ylabel()
        assert len(axes.get_legend().get_texts()) == frame[group].nunique()
        _hide_edge_grids(axes)
        _check_text_layout(figure)
        destination = OUTPUT / f"{filename}.png"
        figure.savefig(destination, dpi=300, facecolor="white")
        print(f"Saved: {destination.resolve()} ({len(frame)} plotted rows)", flush=True)
        return {
            "png": str(destination.resolve()),
            "kind": kind,
            "plotted_rows": len(frame),
            "series_counts": {str(label): int(count) for label, count in frame.groupby(group, sort=False).size().items()},
            "scatter_alpha": 0.7 if kind == "scatter" else None,
        }
    finally:
        plt.close(figure)


def main() -> None:
    jobs = (
        ("tips", "01_total_bill_vs_tip_by_sex", "total_bill", "tip", "sex",
         ("Male", "Female"), "Total Bill (USD)", "Tip (USD)", "Total Bill vs Tip by Sex"),
        ("mpg", "02_horsepower_vs_mpg_by_origin", "horsepower", "mpg", "origin",
         ("usa", "europe", "japan"), "Horsepower (hp)", "Fuel Economy (mpg)",
         "Horsepower vs MPG by Origin"),
        ("diamonds", "03_diamond_carat_vs_price_by_cut", "carat", "price", "cut",
         ("Ideal", "Premium", "Very Good", "Good", "Fair"), "Carat (ct)", "Price (USD)",
         "Diamond Carat vs Price by Cut"),
        ("exercise", "04_average_pulse_over_time_by_exercise_kind", "minutes", "pulse", "kind",
         KIND_ORDER, "Time (min)", "Average Pulse (beats/min)",
         "Average Pulse Over Time by Exercise Kind"),
    )
    records = []
    for name, filename, x, y, group, labels, xlabel, ylabel, title in jobs:
        try:
            frame, record = load_dataset(name)
            kind = "scatter"
            if name == "mpg":
                frame = frame.dropna(subset=["horsepower"])
                record["dropped_missing_horsepower"] = record["original_rows"] - len(frame)
            elif name == "diamonds":
                frame = frame.sample(n=2000, random_state=42)
                record["sampling"] = {"rows": 2000, "random_state": 42, "replace": False}
            elif name == "exercise":
                frame = frame.groupby(["kind", "time"], as_index=False, observed=True)["pulse"].mean()
                frame["minutes"] = frame["time"].map(dict(zip(TIME_ORDER, [1, 15, 30])))
                frame = frame.sort_values("minutes", kind="stable")
                kind = "point-line"
                record["aggregation"] = "Arithmetic mean of pulse across all records per kind and time"
                record["mean_pulse"] = frame[["kind", "time", "pulse"]].to_dict(orient="records")
            frame = group_order(frame, group, labels)
            record.update(save_plot(frame, filename, kind=kind, x=x, y=y, group=group,
                                    xlabel=xlabel, ylabel=ylabel, title=title))
            records.append(record)
        except Exception as error:
            print(f"FAILED {name}: {type(error).__name__}: {error}; continuing to next dataset.",
                  file=sys.stderr, flush=True)
            records.append({"dataset": name, "error": f"{type(error).__name__}: {error}"})
    (OUTPUT / "manifest.json").write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
    if any("error" in record for record in records):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
