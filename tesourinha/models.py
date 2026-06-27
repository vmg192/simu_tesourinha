import math
import simpy
from enum import IntEnum
from .constants import TESOURINHA_CONFIG, UAV_CONFIG


def geofence(v: float) -> float:
    a, tr, L = UAV_CONFIG["DECEL"], UAV_CONFIG["V2V_LATENCY"], UAV_CONFIG["LENGTH"]
    return (v**2) / (2*a) + v*tr + L

def h_cruise(v: float) -> float:
    return geofence(v) / v

def h_merge(v: float) -> float:
    return (geofence(v) + (v**2) / (2*UAV_CONFIG["DECEL"])) / v

def via_slots(v: float) -> int:
    return max(1, math.floor(TESOURINHA_CONFIG["LENGTH"] / geofence(v)))


class UAV_STATUS(IntEnum):
    WAITING   = 0
    IN_BUFFER = 1
    ON_VIA    = 2
    FINISHED  = 3


class UAV_INTENTS(IntEnum):
    CRUISE     = 1
    DESCEND    = 2
    SWITCH     = 3
    RETURN_OUT = 4
    TAKEOFF    = 5


class Via:
    ENTRY_WP = {
        "INPOINT":   0.0,
        "RETURN_IN": 6.0,
        "SWITCH_IN": 40.0,
        "ASCEND":    48.0,
    }

    def __init__(self, env: simpy.Environment, name: str, speed: float):
        self.env     = env
        self.name    = name
        self.speed   = speed
        self.slots   = simpy.Resource(env, capacity=via_slots(speed))
        self.n_slots = via_slots(speed)
        self._last_at = {ep: -9999.0 for ep in self.ENTRY_WP}
        self._locks   = {ep: simpy.Resource(env, capacity=1) for ep in self.ENTRY_WP}
        self._wait_total = {ep: 0.0 for ep in self.ENTRY_WP}
        self._wait_count = {ep: 0   for ep in self.ENTRY_WP}

    def merge(self, entry_point: str, h_min: float, exit_x: float):
        entry_x = self.ENTRY_WP[entry_point]
        t0 = self.env.now

        with self._locks[entry_point].request() as lock:
            yield lock
            wait = max(0.0, self._last_at[entry_point] + h_min - self.env.now)
            if wait > 0:
                yield self.env.timeout(wait)

            t_now = self.env.now
            for ep_name, ep_x in self.ENTRY_WP.items():
                if entry_x <= ep_x <= exit_x:
                    t_pass = t_now + (ep_x - entry_x) / self.speed
                    if t_pass > self._last_at[ep_name]:
                        self._last_at[ep_name] = t_pass

            self._wait_total[entry_point] += self.env.now - t0
            self._wait_count[entry_point] += 1

    def travel_time(self, x_from: float, x_to: float) -> float:
        return abs(x_to - x_from) / self.speed

    def avg_merge_wait(self, entry_point: str) -> float:
        return self._wait_total[entry_point] / max(1, self._wait_count[entry_point])