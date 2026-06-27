import statistics as _stats
import simpy
from dataclasses import dataclass
from ..simulation import Tesourinha
from ..models import geofence, h_cruise, h_merge, via_slots
from ..constants import SIM_CONFIG


@dataclass
class ScenarioResult:
    speed:           float
    lam:             int
    source_scenario: str
    route_scenario:  str
    n_slots:         int
    gfence_m:        float
    h_cruise_s:      float
    h_merge_s:       float
    avg_done:        float
    avg_wait_s:      float
    avg_spill:       float
    sat_pct:         float

    def __str__(self):
        tag = " ◄ SAT" if self.sat_pct < 95 else ""
        return (
            f"v={self.speed:4.0f} m/s | λ={self.lam:4d} | "
            f"src={self.source_scenario:<16} rte={self.route_scenario:<14} | "
            f"done={self.avg_done:6.0f} wait={self.avg_wait_s:5.1f}s "
            f"spill={self.avg_spill:5.1f} sat={self.sat_pct:5.1f}%{tag}"
        )


def run_scenario(
    speed:           float,
    lam:             int,
    source_scenario: str  = "balanced",
    route_scenario:  str  = "default",
    replications:    int  = SIM_CONFIG["REPLICATIONS"],
    duration:        float = SIM_CONFIG["DURATION"],
) -> ScenarioResult:
    dones, waits, spills = [], [], []
    for rep in range(replications):
        env = simpy.Environment()
        t   = Tesourinha(
            env,
            speed           = speed,
            lam             = lam,
            source_scenario = source_scenario,
            route_scenario  = route_scenario,
            seed            = rep * 137 + int(speed * 10),
        )
        t.run(duration)
        env.run(until=duration)
        dones.append(t.stats.completed)
        waits.append(t.stats.avg_wait)
        spills.append(t.stats.spillback_events)

    demanded = lam * (duration / 3600.0)
    return ScenarioResult(
        speed           = speed,
        lam             = lam,
        source_scenario = source_scenario,
        route_scenario  = route_scenario,
        n_slots         = via_slots(speed),
        gfence_m        = round(geofence(speed), 2),
        h_cruise_s      = round(h_cruise(speed), 2),
        h_merge_s       = round(h_merge(speed), 2),
        avg_done        = _stats.mean(dones),
        avg_wait_s      = _stats.mean(waits),
        avg_spill       = _stats.mean(spills),
        sat_pct         = _stats.mean(dones) / max(1.0, demanded) * 100.0,
    )


def grid_search(
    speeds:           list  = SIM_CONFIG["SPEEDS"],
    lambdas:          list  = SIM_CONFIG["LAMBDAS"],
    source_scenarios: list  = SIM_CONFIG["SOURCE_SCENARIOS"],
    route_scenarios:  list  = SIM_CONFIG["ROUTE_SCENARIOS"],
    replications:     int   = SIM_CONFIG["REPLICATIONS"],
    duration:         float = SIM_CONFIG["DURATION"],
    verbose:          bool  = True,
) -> list:
    results = []
    total   = len(speeds) * len(lambdas) * len(source_scenarios) * len(route_scenarios)
    done    = 0

    for src_sc in source_scenarios:
        for rte_sc in route_scenarios:
            for speed in speeds:
                if verbose:
                    print(f"\nsrc={src_sc}  rte={rte_sc}  "
                          f"v={speed} m/s  G={geofence(speed):.1f}m  "
                          f"slots={via_slots(speed)}")
                for lam in lambdas:
                    r = run_scenario(speed, lam, src_sc, rte_sc, replications, duration)
                    results.append(r)
                    done += 1
                    if verbose:
                        print(f"  [{done}/{total}] {r}")

    return results