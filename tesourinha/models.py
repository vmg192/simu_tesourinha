import math
import simpy
from enum import IntEnum
from .constants import TESOURINHA_CONFIG, UAV_CONFIG


# ─── Física ───────────────────────────────────────────────────────────────────

def geofence(v: float) -> float:
    """G(v) = v²/2a + v·tr + L — tamanho da bolha de segurança em metros."""
    a, tr, L = UAV_CONFIG["DECEL"], UAV_CONFIG["V2V_LATENCY"], UAV_CONFIG["LENGTH"]
    return (v**2) / (2*a) + v*tr + L

def h_cruise(v: float) -> float:
    """Headway mínimo para entrada em fluxo contínuo (s)."""
    return geofence(v) / v

def h_merge(v: float) -> float:
    """Gap mínimo para merge seguro desde parada (s)."""
    return (geofence(v) + (v**2) / (2*UAV_CONFIG["DECEL"])) / v

def via_slots(v: float) -> int:
    """
    Máximo de drones simultâneos na via.
    Velocidade MENOR → geofence MENOR → MAIS slots.
    """
    return max(1, math.floor(TESOURINHA_CONFIG["LENGTH"] / geofence(v)))


# ─── Enums ────────────────────────────────────────────────────────────────────

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


# ─── MergeNode ────────────────────────────────────────────────────────────────

class MergeNode:
    """
    Enforça separação temporal em um ponto de entrada da via.

    A versão com while/loop é O(n²) quando muitos drones esperam juntos:
    todos acordam no mesmo instante e precisam re-verificar em cadeia.

    Esta versão usa Resource(capacity=1) como fila FIFO: cada drone
    espera sua vez, calcula o wait EXATAMENTE UMA VEZ e passa. O(1).
    """

    def __init__(self, env: simpy.Environment, h_min: float, name: str = ""):
        self.env   = env
        self.h_min = h_min
        self.name  = name
        self._lock = simpy.Resource(env, capacity=1)
        self._last: float = -9999.0
        self.total_wait: float = 0.0
        self.count:      int   = 0

    def request(self):
        """
        yield from node.request()

        Entra na fila, espera sua vez, calcula o gap uma vez, passa.
        """
        t0 = self.env.now
        with self._lock.request() as lock_req:
            yield lock_req
            wait = max(0.0, self._last + self.h_min - self.env.now)
            if wait > 0:
                yield self.env.timeout(wait)
            self._last         = self.env.now
            self.total_wait   += self.env.now - t0
            self.count        += 1

    @property
    def avg_wait(self) -> float:
        return self.total_wait / max(1, self.count)


# ─── Via ──────────────────────────────────────────────────────────────────────

class Via:
    """
    Lane aérea de 60m. Capacidade = floor(60 / G(v)).

    Um drone ocupa 1 slot da entrada até o diverge ou Finish.
    Se todos os slots estiverem ocupados, o próximo drone bloqueia
    (segurando o slot da via anterior) — esse é o spillback.
    """

    def __init__(self, env: simpy.Environment, name: str, speed: float):
        self.env   = env
        self.name  = name
        self.speed = speed
        self.slots   = simpy.Resource(env, capacity=via_slots(speed))
        self.n_slots = via_slots(speed)
        self.nodes = {
            "INPOINT":   MergeNode(env, h_cruise(speed), f"{name}_INPOINT"),
            "RETURN_IN": MergeNode(env, h_merge(speed),  f"{name}_RETURN_IN"),
            "SWITCH_IN": MergeNode(env, h_merge(speed),  f"{name}_SWITCH_IN"),
            "ASCEND":    MergeNode(env, h_merge(speed),  f"{name}_ASCEND"),
        }

    def travel_time(self, x_from: float, x_to: float) -> float:
        return abs(x_to - x_from) / self.speed