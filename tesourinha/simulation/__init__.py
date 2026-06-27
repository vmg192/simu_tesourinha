import random
import simpy
from ..constants import TESOURINHA_CONFIG as C, ROUTE_SCENARIOS, SOURCE_SCENARIOS
from ..models import Via, h_cruise, h_merge

# Mapeia cada ação para o waypoint de saída correspondente
_ACTION_WP = {
    "FINISH":     "FINISH",
    "DESCEND":    "DESCEND",
    "SWITCH":     "SWITCH_OUT",
    "RETURN_OUT": "RETURN_OUT",
}


class Stats:
    def __init__(self):
        self.completed:        int   = 0
        self.spillback_events: int   = 0
        self.total_wait:       float = 0.0

    def record(self, wait: float):
        self.completed  += 1
        self.total_wait += wait

    @property
    def avg_wait(self) -> float:
        return self.total_wait / max(1, self.completed)


class Tesourinha:
    """
    Uso:
        env = simpy.Environment()
        t   = Tesourinha(
                env, speed=10.0, lam=200,
                source_scenario="balanced",
                route_scenario="default",
                seed=42,
              )
        t.run(14400)
        env.run(until=14400)
    """

    def __init__(
        self,
        env:             simpy.Environment,
        speed:           float,
        lam:             float,
        source_scenario: str = "balanced",
        route_scenario:  str = "default",
        seed:            int = 0,
    ):
        self.env    = env
        self.speed  = speed
        self.lam    = lam
        self.stats  = Stats()
        self._rng   = random.Random(seed)
        self._src   = SOURCE_SCENARIOS[source_scenario]
        self._routes = ROUTE_SCENARIOS[route_scenario]

        self.via_A = Via(env, "A", speed)
        self.via_B = Via(env, "B", speed)

        self.bfr_descend    = simpy.Resource(env, capacity=C["BFR_DESCEND"])
        self.bfr_switch     = simpy.Resource(env, capacity=C["BFR_SWITCH"])
        self.bfr_return_out = simpy.Resource(env, capacity=C["BFR_RETURN_OUT"])
        self.bfr_takeoff    = simpy.Resource(env, capacity=C["BFR_TAKEOFF"])

    # ── Interface pública ─────────────────────────────────────────────────────

    def run(self, duration: float):
        s = self._src
        self.env.process(self._arrivals(self.lam * s["HIGHWAY_A"] / 3600, duration,
                                        lambda: self._spawn_highway(self.via_A)))
        self.env.process(self._arrivals(self.lam * s["HIGHWAY_B"] / 3600, duration,
                                        lambda: self._spawn_highway(self.via_B)))
        self.env.process(self._arrivals(self.lam * s["BUFFER_IN"] / 3600, duration,
                                        self._spawn_buffer_in))
        self.env.process(self._arrivals(self.lam * s["VERTISTOP"]  / 3600, duration,
                                        self._spawn_vertistop))

    # ── Geradores de chegada ──────────────────────────────────────────────────

    def _arrivals(self, lam: float, duration: float, spawn):
        while True:
            yield self.env.timeout(self._rng.expovariate(lam))
            if self.env.now >= duration:
                return
            spawn()

    def _spawn_highway(self, via: Via):
        actions = self._sample_route("INPOINT")
        self.env.process(self._drone(via, "INPOINT", C["INPOINT"], actions))

    def _spawn_buffer_in(self):
        actions = self._sample_route("RETURN_IN")
        self.env.process(self._drone(self.via_B, "RETURN_IN", C["RETURN_IN"], actions))

    def _spawn_vertistop(self):
        self.env.process(self._takeoff())

    # ── Processo principal do drone ───────────────────────────────────────────

    def _drone(self, via: Via, entry: str, entry_x: float, actions: list):
        """
        Processa uma sequência de ações em ordem.
        Ações suportadas: FINISH, DESCEND, RETURN_OUT, SWITCH.

        SWITCH é a única ação que não encerra o processo:
        o drone muda de via e continua processando as ações restantes.
        Todas as outras encerram com return.
        """
        t_born = self.env.now
        current_via = via
        current_x   = entry_x
        remaining   = list(actions)

        # Merge inicial: exit_x é onde o drone vai sair da via pela primeira vez
        exit_x = self._exit_x(current_x, remaining)
        h_min  = h_cruise(via.speed) if entry == "INPOINT" else h_merge(via.speed)
        yield from current_via.merge(entry, h_min, exit_x)

        via_req = current_via.slots.request()
        t_slot  = self.env.now
        yield via_req
        if self.env.now > t_slot + 0.001:
            self.stats.spillback_events += 1

        while remaining:
            action = remaining.pop(0)

            if action == "FINISH":
                yield self.env.timeout(current_via.travel_time(current_x, C["FINISH"]))
                current_via.slots.release(via_req)
                self.stats.record(self.env.now - t_born)
                return

            elif action == "DESCEND":
                yield self.env.timeout(current_via.travel_time(current_x, C["DESCEND"]))
                bfr = self.bfr_descend.request()
                t   = self.env.now
                yield bfr
                if self.env.now > t + 0.001:
                    self.stats.spillback_events += 1
                current_via.slots.release(via_req)
                yield self.env.timeout(self._rng.uniform(30, 60))
                self.bfr_descend.release(bfr)
                self.stats.record(self.env.now - t_born)
                return

            elif action == "RETURN_OUT":
                yield self.env.timeout(current_via.travel_time(current_x, C["RETURN_OUT"]))
                bfr = self.bfr_return_out.request()
                t   = self.env.now
                yield bfr
                if self.env.now > t + 0.001:
                    self.stats.spillback_events += 1
                current_via.slots.release(via_req)
                yield self.env.timeout(self._rng.uniform(5, 15))
                self.bfr_return_out.release(bfr)
                self.stats.record(self.env.now - t_born)
                return

            elif action == "SWITCH":
                yield self.env.timeout(current_via.travel_time(current_x, C["SWITCH_OUT"]))
                bfr = self.bfr_switch.request()
                t   = self.env.now
                yield bfr
                if self.env.now > t + 0.001:
                    self.stats.spillback_events += 1
                current_via.slots.release(via_req)

                # Muda para via oposta — continua com as ações restantes
                target      = self.via_B if current_via.name == "A" else self.via_A
                next_exit_x = self._exit_x(C["SWITCH_IN"], remaining)
                yield from target.merge("SWITCH_IN", h_merge(target.speed), next_exit_x)

                via_req = target.slots.request()
                t2      = self.env.now
                yield via_req
                if self.env.now > t2 + 0.001:
                    self.stats.spillback_events += 1

                self.bfr_switch.release(bfr)
                current_via = target
                current_x   = C["SWITCH_IN"]

                # Guarda: se não sobrou nada após o switch, vai para FINISH
                if not remaining:
                    remaining.append("FINISH")

    # ── Decolagem ─────────────────────────────────────────────────────────────

    def _takeoff(self):
        bfr = self.bfr_takeoff.request()
        yield bfr
        yield self.env.timeout(C["VERTICAL_TIME"])
        self.bfr_takeoff.release(bfr)
        target  = self._rng.choice([self.via_A, self.via_B])
        actions = self._sample_route("ASCEND")
        self.env.process(self._drone(target, "ASCEND", C["ASCEND"], actions))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _exit_x(self, current_x: float, actions: list) -> float:
        """Posição de saída da via para a próxima ação, respeitando geometria."""
        if not actions:
            return C["FINISH"]
        wp_name = _ACTION_WP.get(actions[0], "FINISH")
        x = C[wp_name]
        # Se o waypoint ficou para trás (geometricamente inválido), vai até o fim
        return x if x > current_x else C["FINISH"]

    def _sample_route(self, entry: str) -> list:
        """Sorteia uma sequência de ações para o entry point dado."""
        options = self._routes[entry]
        total   = sum(w for w, _ in options)
        r       = self._rng.random() * total
        cum     = 0.0
        for weight, actions in options:
            cum += weight
            if r < cum:
                return list(actions)
        return ["FINISH"]