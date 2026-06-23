#!/usr/bin/env python3
"""
Runner da biblioteca tesourinha.

Uso:
    python run_tesourinha.py
    python run_tesourinha.py --time 7200 --count 12 --interval 90 --seed 7
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field

import simpy

from tesourinha.models import Tesourinha, UAV, UAV_INTENTS, UAV_STATUS


@dataclass
class SimStats:
    started: int = 0
    finished: int = 0
    records: list[dict] = field(default_factory=list)


SCENARIOS: list[tuple[str, list[UAV_INTENTS], str]] = [
    ("takeoff-finish-A", [UAV_INTENTS.TAKEOFF, UAV_INTENTS.FINISH], "A"),
    ("takeoff-finish-B", [UAV_INTENTS.TAKEOFF, UAV_INTENTS.FINISH], "B"),
    ("takeoff-return-A", [UAV_INTENTS.TAKEOFF, UAV_INTENTS.RETURN_OUT], "A"),
    ("takeoff-return-B", [UAV_INTENTS.TAKEOFF, UAV_INTENTS.RETURN_OUT], "B"),
    (
        "takeoff-switch-finish-A",
        [UAV_INTENTS.TAKEOFF, UAV_INTENTS.SWITCH_OUT, UAV_INTENTS.SWITCH_IN, UAV_INTENTS.FINISH],
        "A",
    ),
    (
        "takeoff-switch-finish-B",
        [UAV_INTENTS.TAKEOFF, UAV_INTENTS.SWITCH_OUT, UAV_INTENTS.SWITCH_IN, UAV_INTENTS.FINISH],
        "B",
    ),
    ("return-in-finish", [UAV_INTENTS.RETURN_IN, UAV_INTENTS.FINISH], "A"),
    ("ascend-finish-A", [UAV_INTENTS.ASCEND, UAV_INTENTS.FINISH], "A"),
    ("ascend-finish-B", [UAV_INTENTS.ASCEND, UAV_INTENTS.FINISH], "B"),
    ("takeoff-descend", [UAV_INTENTS.TAKEOFF, UAV_INTENTS.DESCEND], "A"),
]


def route_label(route: list[UAV_INTENTS]) -> str:
    return " -> ".join(intent.name for intent in route)


def run_drone(env: simpy.Environment, tes: Tesourinha, uav: UAV, stats: SimStats):
    stats.started += 1
    started_at = env.now
    yield env.process(tes.drone_lifetime(uav))
    stats.finished += 1
    stats.records.append(
        {
            "name": uav.name,
            "route": route_label(uav.route),
            "side": uav.in_origin,
            "started_at": started_at,
            "finished_at": env.now,
            "duration_s": env.now - started_at,
            "status": uav.status.name,
        }
    )


def drone_generator(
    env: simpy.Environment,
    tes: Tesourinha,
    stats: SimStats,
    interval_s: float,
    count: int,
    scenarios: list[tuple[str, list[UAV_INTENTS], str]],
):
    for seq in range(count):
        label, route, in_origin = random.choice(scenarios)
        uav = UAV(env, f"{label}#{seq}", route, origin=None, in_origin=in_origin)
        env.process(run_drone(env, tes, uav, stats))
        yield env.timeout(interval_s)


def print_header(sim_time: float, interval_s: float, count: int, seed: int):
    print("=" * 72)
    print("TESOURINHA — simulação de demonstração")
    print("=" * 72)
    print(f"Tempo simulado : {sim_time:.0f}s ({sim_time / 3600:.1f}h)")
    print(f"Drones         : {count}")
    print(f"Intervalo      : {interval_s:.0f}s entre lançamentos")
    print(f"Seed           : {seed}")
    print(f"Cenários       : {len(SCENARIOS)} rotas pré-definidas")
    print("-" * 72)


def print_summary(env: simpy.Environment, stats: SimStats):
    print("-" * 72)
    print("RESUMO")
    print("-" * 72)
    print(f"Tempo final        : {env.now:.1f}s")
    print(f"Drones iniciados   : {stats.started}")
    print(f"Drones concluídos  : {stats.finished}")
    if stats.started:
        print(f"Taxa de conclusão  : {100 * stats.finished / stats.started:.1f}%")

    finished_ok = sum(1 for r in stats.records if r["status"] == UAV_STATUS.FINISHED.name)
    print(f"Status FINISHED    : {finished_ok}")

    if stats.records:
        durations = [r["duration_s"] for r in stats.records]
        print(f"Duração média      : {sum(durations) / len(durations):.1f}s")
        print(f"Duração mín/máx    : {min(durations):.1f}s / {max(durations):.1f}s")

    print("-" * 72)
    print("DETALHE POR DRONE")
    print("-" * 72)
    for record in sorted(stats.records, key=lambda r: r["started_at"]):
        print(
            f"[t={record['started_at']:7.1f}s] {record['name']:<22} "
            f"side={record['side']}  {record['duration_s']:6.1f}s  "
            f"{record['status']:<9}  {record['route']}"
        )
    print("=" * 72)


def main():
    parser = argparse.ArgumentParser(description="Executa a biblioteca tesourinha.")
    parser.add_argument("--time", type=float, default=3600, help="Duração da simulação em segundos.")
    parser.add_argument("--interval", type=float, default=120, help="Intervalo entre drones em segundos.")
    parser.add_argument("--count", type=int, default=8, help="Quantidade de drones a lançar.")
    parser.add_argument("--seed", type=int, default=42, help="Seed do gerador aleatório.")
    args = parser.parse_args()

    random.seed(args.seed)

    env = simpy.Environment()
    tes = Tesourinha(env, id=1)
    stats = SimStats()

    print_header(args.time, args.interval, args.count, args.seed)
    env.process(
        drone_generator(env, tes, stats, args.interval, args.count, SCENARIOS)
    )
    env.run(until=args.time)
    print_summary(env, stats)


if __name__ == "__main__":
    main()
