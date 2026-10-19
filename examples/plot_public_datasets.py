"""Reproduce five comparisons using seaborn's public example datasets."""

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scientific-plotting" / "scripts"))
from plot_template import render_plot


COUNTRIES = ("USA", "Japan", "Germany", "France", "Great Britain")
MONTHS = ("Jan", "Apr", "Jul", "Oct")
OUTPUT = ROOT / "figures"


def selected_series(frame: pd.DataFrame, column: str, labels: tuple[str, ...], order: str) -> pd.DataFrame:
    return pd.concat(
        [frame.loc[frame[column] == label].sort_values(order) for label in labels],
        ignore_index=True,
    )


def save(frame: pd.DataFrame, filename: str, **options: str) -> None:
    figure, _, paths = render_plot(
        frame, size="double", output=OUTPUT / filename, **options
    )
    plt.close(figure)
    print(paths[0].resolve())


def main() -> None:
    health = sns.load_dataset("healthexp")
    iris = sns.load_dataset("iris")
    flights = sns.load_dataset("flights")
    penguins = sns.load_dataset("penguins")

    health = selected_series(health, "Country", COUNTRIES, "Year")
    flights = selected_series(flights, "month", MONTHS, "year")
    penguins = penguins.dropna()

    save(
        health,
        "01_life_expectancy_by_country",
        kind="point-line", x="Year", y="Life_Expectancy", group="Country",
        group_kind="categorical", xlabel="Year", ylabel="Life Expectancy (years)",
        title="Life Expectancy Over Time by Country",
    )
    save(
        iris,
        "02_iris_sepal_by_species",
        kind="scatter", x="sepal_length", y="sepal_width", group="species",
        xlabel="Sepal Length (cm)", ylabel="Sepal Width (cm)",
        title="Iris: Sepal Length vs Sepal Width by Species",
    )
    save(
        flights,
        "03_airline_passengers_by_month",
        kind="point-line", x="year", y="passengers", group="month",
        group_kind="categorical", xlabel="Year", ylabel="Passengers",
        title="Airline Passengers by Year and Month",
    )
    save(
        penguins,
        "04_penguin_bill_vs_flipper",
        kind="scatter", x="bill_length_mm", y="flipper_length_mm", group="species",
        xlabel="Bill Length (mm)", ylabel="Flipper Length (mm)",
        title="Penguins: Bill Length vs Flipper Length by Species",
    )
    save(
        health,
        "05_spending_vs_life_expectancy",
        kind="point-line", x="Spending_USD", y="Life_Expectancy", group="Country",
        group_kind="categorical", xlabel="Health Spending (USD)",
        ylabel="Life Expectancy (years)",
        title="Health Spending vs Life Expectancy Trajectories by Country",
    )


if __name__ == "__main__":
    main()
