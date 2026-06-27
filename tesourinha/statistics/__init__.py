import statistics as _stats
import simpy
from dataclasses import dataclass
from ..simulation import Tesourinha
from ..models import geofence, h_cruise, h_merge, via_slots
from ..constants import SIM_CONFIG


@dataclass
class ScenarioResult:
    speed:      float
    lam:        int
    n_slots:    int
    gfence_m:   float
    h_cruise_s: float
    h_merge_s:  float
    avg_done:   float
    avg_wait_s: float
    avg_spill:  float
    sat_pct:    float

    def __str__(self):
        tag = " ◄ SAT" if self.sat_pct < 95 else ""
        return (
            f"v={self.speed:4.0f} m/s | λ={self.lam:4d} D/h | "
            f"slots={self.n_slots} | done={self.avg_done:6.0f} | "
            f"wait={self.avg_wait_s:5.1f}s | spill={self.avg_spill:5.1f} | "
            f"sat={self.sat_pct:5.1f}%{tag}"
        )


def run_scenario(
    speed:        float,
    lam:          int,
    replications: int   = SIM_CONFIG["REPLICATIONS"],
    duration:     float = SIM_CONFIG["DURATION"],
) -> ScenarioResult:
    dones, waits, spills = [], [], []
    for rep in range(replications):
        env = simpy.Environment()
        t   = Tesourinha(env, speed=speed, lam=lam, seed=rep * 137 + int(speed * 10))
        t.run(duration)
        env.run(until=duration)
        dones.append(t.stats.completed)
        waits.append(t.stats.avg_wait)
        spills.append(t.stats.spillback_events)
    demanded = lam * (duration / 3600.0)
    return ScenarioResult(
        speed      = speed,
        lam        = lam,
        n_slots    = via_slots(speed),
        gfence_m   = round(geofence(speed), 2),
        h_cruise_s = round(h_cruise(speed), 2),
        h_merge_s  = round(h_merge(speed), 2),
        avg_done   = _stats.mean(dones),
        avg_wait_s = _stats.mean(waits),
        avg_spill  = _stats.mean(spills),
        sat_pct    = _stats.mean(dones) / max(1.0, demanded) * 100.0,
    )


def grid_search(
    speeds:       list  = SIM_CONFIG["SPEEDS"],
    lambdas:      list  = SIM_CONFIG["LAMBDAS"],
    replications: int   = SIM_CONFIG["REPLICATIONS"],
    duration:     float = SIM_CONFIG["DURATION"],
    verbose:      bool  = True,
) -> list:
    results, total, done = [], len(speeds) * len(lambdas), 0
    for speed in speeds:
        if verbose:
            print(f"\nv={speed} | G={geofence(speed):.1f}m | slots={via_slots(speed)} | h_c={h_cruise(speed):.2f}s | h_m={h_merge(speed):.2f}s")
        for lam in lambdas:
            r = run_scenario(speed, lam, replications, duration)
            results.append(r)
            done += 1
            if verbose:
                print(f"  [{done}/{total}] {r}")
    return results