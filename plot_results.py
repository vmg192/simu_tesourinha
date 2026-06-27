"""Análise focada dos resultados da simulação."""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd
import numpy as np

CSV_PATH = Path("results.csv")
OUT_DIR  = Path("plots")


def load(path: Path = CSV_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["speed"] = df["speed"].astype(int)
    df["lam"]   = df["lam"].astype(int)
    return df


def _critical_lambda(group: pd.DataFrame, threshold: float = 95.0) -> float:
    """Menor λ onde sat_pct cai abaixo do threshold. Retorna inf se nunca cai."""
    sat = group.sort_values("lam")
    below = sat[sat["sat_pct"] < threshold]
    return float(below["lam"].min()) if not below.empty else float("inf")


# ── Plot 1: Fronteira de saturação ────────────────────────────────────────────
# Pergunta: em que λ cada velocidade começa a saturar?
# Mostra média + banda min/max entre todos os cenários.

def plot_saturation_frontier(df: pd.DataFrame, out_dir: Path) -> Path:
    speeds = sorted(df["speed"].unique())
    lambdas = sorted(df["lam"].unique())
    colors = plt.cm.viridis(np.linspace(0, 1, len(speeds)))

    fig, ax = plt.subplots(figsize=(11, 6))

    for speed, color in zip(speeds, colors):
        sub = df[df["speed"] == speed]
        # agrega sobre todos os cenários em cada λ
        agg = sub.groupby("lam")["sat_pct"].agg(["mean", "min", "max"]).reset_index()
        slots = df[df["speed"] == speed]["n_slots"].iloc[0]

        ax.plot(agg["lam"], agg["mean"],
                color=color, linewidth=2,
                label=f"v={speed} m/s ({slots} slot{'s' if slots > 1 else ''})")
        ax.fill_between(agg["lam"], agg["min"], agg["max"],
                        color=color, alpha=0.15)

    ax.axhline(95, color="crimson", linestyle="--", linewidth=1.2, label="limiar 95%")
    ax.set_xlabel("Demanda λ (drones/h)", fontsize=11)
    ax.set_ylabel("Saturação — % da demanda atendida", fontsize=11)
    ax.set_title("Fronteira de saturação por velocidade\n"
                 "(linha = média entre cenários · banda = min/max)", fontsize=12)
    ax.set_ylim(0, 105)
    ax.legend(fontsize=9, loc="lower left")
    ax.grid(True, alpha=0.3, linestyle="--")

    plt.tight_layout()
    path = out_dir / "1_saturacao_frontier.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


# ── Plot 2: λ* por velocidade com barra de variação entre cenários ────────────
# Pergunta: o ponto de saturação é estável ou depende muito do cenário?

def plot_critical_lambda(df: pd.DataFrame, out_dir: Path) -> Path:
    speeds = sorted(df["speed"].unique())
    scenarios = df[["source_scenario", "route_scenario"]].drop_duplicates()
    scenario_keys = list(zip(scenarios["source_scenario"], scenarios["route_scenario"]))

    # λ* por (speed, cenário)
    records = []
    for speed in speeds:
        for src, rte in scenario_keys:
            sub = df[(df["speed"] == speed) &
                     (df["source_scenario"] == src) &
                     (df["route_scenario"] == rte)]
            lstar = _critical_lambda(sub)
            records.append({"speed": speed, "lstar": lstar, "src": src, "rte": rte})

    agg = pd.DataFrame(records)
    summary = agg.groupby("speed")["lstar"].agg(["mean", "min", "max"]).reset_index()

    fig, ax = plt.subplots(figsize=(9, 5))
    x = range(len(speeds))

    bars = ax.bar(x, summary["mean"],
                  color=plt.cm.viridis(np.linspace(0.2, 0.8, len(speeds))),
                  edgecolor="white", width=0.55, zorder=3)

    # erro = variação entre cenários
    yerr_low  = summary["mean"] - summary["min"]
    yerr_high = summary["max"] - summary["mean"]
    ax.errorbar(x, summary["mean"],
                yerr=[yerr_low, yerr_high],
                fmt="none", color="black", capsize=6, linewidth=1.5, zorder=4)

    ax.set_xticks(x)
    ax.set_xticklabels([f"{v} m/s" for v in speeds])
    ax.set_xlabel("Velocidade", fontsize=11)
    ax.set_ylabel("λ* — densidade crítica (drones/h)", fontsize=11)
    ax.set_title("Ponto de saturação por velocidade\n"
                 "(barra = média · traço = variação entre cenários)", fontsize=12)
    ax.grid(axis="y", alpha=0.3, linestyle="--", zorder=0)

    for bar, val in zip(bars, summary["mean"]):
        if val < float("inf"):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 8,
                    f"{val:.0f}", ha="center", fontsize=9)
        else:
            ax.text(bar.get_x() + bar.get_width() / 2,
                    ax.get_ylim()[1] * 0.85,
                    "sem sat.", ha="center", fontsize=9, color="green")

    plt.tight_layout()
    path = out_dir / "2_lambda_critico.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


# ── Plot 3: Heatmap do pior caso ──────────────────────────────────────────────
# Pergunta: qual é a performance MÍNIMA garantida independente do cenário?
# Se o pior caso ainda é aceitável, a arquitetura é robusta.

def plot_worst_case_heatmap(df: pd.DataFrame, out_dir: Path) -> Path:
    # pior caso = mínimo de sat_pct entre todos os cenários
    worst = df.groupby(["speed", "lam"])["sat_pct"].min().reset_index()
    pivot = worst.pivot(index="speed", columns="lam", values="sat_pct")

    fig, ax = plt.subplots(figsize=(13, 4))
    im = ax.imshow(pivot.values, aspect="auto", cmap="RdYlGn",
                   vmin=0, vmax=100, origin="lower")

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f"{v} m/s" for v in pivot.index])
    ax.set_xlabel("Demanda λ (drones/h)")
    ax.set_ylabel("Velocidade")
    ax.set_title("Saturação — PIOR CASO entre todos os cenários (%)\n"
                 "(verde = sistema suporta · vermelho = saturação garantida)", fontsize=11)

    # anota células
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.0f}",
                        ha="center", va="center", fontsize=7,
                        color="black" if 30 < val < 80 else "white")

    cbar = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    cbar.ax.tick_params(labelsize=8)

    plt.tight_layout()
    path = out_dir / "3_pior_caso_heatmap.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


# ── Plot 4: Spillback — aviso antecipado ──────────────────────────────────────
# Pergunta: onde o congestionamento começa, antes mesmo da saturação?
# Spillback > 0 indica que a via está bloqueando, mesmo que sat_pct ainda seja alta.

def plot_spillback_onset(df: pd.DataFrame, out_dir: Path) -> Path:
    speeds  = sorted(df["speed"].unique())
    colors  = plt.cm.viridis(np.linspace(0, 1, len(speeds)))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Spillback — sinal antecipado de congestionamento", fontsize=12)

    for speed, color in zip(speeds, colors):
        sub = df[df["speed"] == speed]
        agg = sub.groupby("lam")["avg_spill"].agg(["mean", "max"]).reset_index()
        slots = df[df["speed"] == speed]["n_slots"].iloc[0]
        label = f"v={speed} m/s ({slots} slots)"

        ax1.plot(agg["lam"], agg["mean"],
                 color=color, linewidth=2, marker="o", markersize=3, label=label)
        ax2.plot(agg["lam"], agg["max"],
                 color=color, linewidth=2, marker="o", markersize=3, label=label)

    for ax, title in zip([ax1, ax2],
                         ["Spillback médio entre cenários",
                          "Spillback máximo (pior cenário)"]):
        ax.set_xlabel("Demanda λ (drones/h)", fontsize=10)
        ax.set_ylabel("Eventos de spillback por rodada", fontsize=10)
        ax.set_title(title, fontsize=11)
        ax.grid(True, alpha=0.3, linestyle="--")
        ax.legend(fontsize=8, loc="upper left")

    plt.tight_layout()
    path = out_dir / "4_spillback_onset.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return path


# ── Entry point ───────────────────────────────────────────────────────────────

def plot_results(csv_path: Path = CSV_PATH, out_dir: Path = OUT_DIR) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = load(csv_path)

    outputs = [
        plot_saturation_frontier(df, out_dir),
        plot_critical_lambda(df, out_dir),
        plot_worst_case_heatmap(df, out_dir),
        plot_spillback_onset(df, out_dir),
    ]

    return outputs


if __name__ == "__main__":
    paths = plot_results()
    print("Gráficos salvos em plots/:")
    for p in paths:
        print(f"  • {p}")