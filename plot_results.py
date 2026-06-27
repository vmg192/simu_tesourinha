"""Gera gráficos a partir de results.csv (saída de run_tesourinha.py)."""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

CSV_PATH = Path("results.csv")
OUT_DIR = Path("plots")


def load_results(path: Path = CSV_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["speed"] = df["speed"].astype(int)
    df["lam"] = df["lam"].astype(int)
    return df


def _style_axes(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=11, pad=8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(fontsize=8, loc="best", framealpha=0.9)


def plot_metrics_vs_lambda(df: pd.DataFrame, out_dir: Path) -> None:
    speeds = sorted(df["speed"].unique())
    colors = plt.cm.viridis([i / max(1, len(speeds) - 1) for i in range(len(speeds))])

    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharex=True)
    fig.suptitle("Desempenho da Air Tesourinha — grid search", fontsize=14, y=0.98)

    metrics = [
        ("avg_done", "Throughput médio (drones/4h)", axes[0, 0]),
        ("avg_wait_s", "Espera média nos merge nodes (s)", axes[0, 1]),
        ("avg_spill", "Eventos de spillback (média)", axes[1, 0]),
        ("sat_pct", "Saturação (% da demanda atendida)", axes[1, 1]),
    ]

    for col, ylabel, ax in metrics:
        for speed, color in zip(speeds, colors):
            sub = df[df["speed"] == speed].sort_values("lam")
            slots = sub["n_slots"].iloc[0]
            ax.plot(
                sub["lam"],
                sub[col],
                marker="o",
                markersize=4,
                linewidth=1.8,
                color=color,
                label=f"v={speed} m/s ({slots} slots)",
            )
        if col == "sat_pct":
            ax.axhline(95, color="crimson", linestyle=":", linewidth=1.2, label="limiar 95%")
        _style_axes(ax, ylabel, "Demanda λ (drones/h)", ylabel)

    plt.tight_layout()
    fig.savefig(out_dir / "metricas_vs_lambda.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_heatmaps(df: pd.DataFrame, out_dir: Path) -> None:
    metrics = [
        ("avg_wait_s", "Espera média (s)", "YlOrRd"),
        ("avg_spill", "Spillback (média)", "Reds"),
        ("sat_pct", "Saturação (%)", "RdYlGn"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("Mapas de calor — velocidade × demanda", fontsize=14, y=1.02)

    for ax, (col, title, cmap) in zip(axes, metrics):
        pivot = df.pivot(index="speed", columns="lam", values=col)
        im = ax.imshow(pivot.values, aspect="auto", cmap=cmap, origin="lower")
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns, rotation=45, ha="right")
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([f"{v} m/s" for v in pivot.index])
        ax.set_xlabel("λ (drones/h)")
        ax.set_ylabel("Velocidade")
        ax.set_title(title)
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cbar.ax.tick_params(labelsize=8)

    plt.tight_layout()
    fig.savefig(out_dir / "heatmaps.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_capacity(df: pd.DataFrame, out_dir: Path) -> None:
    by_speed = (
        df.groupby("speed", as_index=False)
        .agg(n_slots=("n_slots", "first"), gfence_m=("gfence_m", "first"))
        .sort_values("speed")
    )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.suptitle("Capacidade física da via por velocidade", fontsize=13)

    bars = ax1.bar(
        by_speed["speed"].astype(str) + " m/s",
        by_speed["n_slots"],
        color=plt.cm.Blues(by_speed["n_slots"] / by_speed["n_slots"].max()),
        edgecolor="white",
    )
    ax1.set_ylabel("Slots simultâneos na via (60 m)")
    ax1.set_xlabel("Velocidade de cruzeiro")
    ax1.set_title("Capacidade em slots")
    ax1.grid(axis="y", alpha=0.3, linestyle="--")
    for bar, val in zip(bars, by_speed["n_slots"]):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05, str(val), ha="center", fontsize=10)

    ax2.plot(by_speed["speed"], by_speed["gfence_m"], marker="s", color="darkorange", linewidth=2)
    ax2.set_xlabel("Velocidade (m/s)")
    ax2.set_ylabel("Geofence G(v) (m)")
    ax2.set_title("Bolha de segurança")
    ax2.grid(True, alpha=0.3, linestyle="--")
    ax2.set_xticks(by_speed["speed"])

    plt.tight_layout()
    fig.savefig(out_dir / "capacidade_fisica.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_results(csv_path: Path = CSV_PATH, out_dir: Path = OUT_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = load_results(csv_path)

    plot_metrics_vs_lambda(df, out_dir)
    plot_heatmaps(df, out_dir)
    plot_capacity(df, out_dir)

    outputs = sorted(out_dir.glob("*.png"))
    return outputs


if __name__ == "__main__":
    paths = plot_results()
    print("Gráficos salvos em plots/:")
    for p in paths:
        print(f"  • {p}")
