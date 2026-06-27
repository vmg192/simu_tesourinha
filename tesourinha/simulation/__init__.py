import random
import simpy
from ..constants import TESOURINHA_CONFIG as C, FLIGHT_PLAN_CONFIG, SOURCE_CONFIG
from ..models import Via, UAV_INTENTS


class Stats:
    def __init__(self):
        self.completed:        int   = 0
        self.spillback_events: int   = 0
        self.total_wait:       float = 0.0

    def record(self, wait: float):
        self.completed    += 1
        self.total_wait   += wait

    @property
    def avg_wait(self) -> float:
        return self.total_wait / max(1, self.completed)


class Tesourinha:
    """
    Simulação completa de uma Air Tesourinha.

    env    = simpy.Environment()
    t      = Tesourinha(env, speed=10.0, lam=200, seed=42)
    t.run(14400)
    env.run(until=14400)
    print(t.stats.completed, t.stats.spillback_events)
    """

    def __init__(self, env: simpy.Environment, speed: float, lam: float, seed: int = 0):
        self.env   = env
        self.speed = speed
        self.lam   = lam
        self.stats = Stats()
        self._rng  = random.Random(seed)

        self.via_A = Via(env, "A", speed)
        self.via_B = Via(env, "B", speed)

        self.bfr_descend    = simpy.Resource(env, capacity=C["BFR_DESCEND"])
        self.bfr_switch     = simpy.Resource(env, capacity=C["BFR_SWITCH"])
        self.bfr_return_out = simpy.Resource(env, capacity=C["BFR_RETURN_OUT"])
        self.bfr_takeoff    = simpy.Resource(env, capacity=C["BFR_TAKEOFF"])

    def run(self, duration: float):
        lam_A  = self.lam * SOURCE_CONFIG["HIGHWAY_A"] / 3600
        lam_B  = self.lam * SOURCE_CONFIG["HIGHWAY_B"] / 3600
        lam_bi = self.lam * SOURCE_CONFIG["BUFFER_IN"] / 3600
        lam_vs = self.lam * SOURCE_CONFIG["VERTISTOP"]  / 3600

        self.env.process(self._arrivals(lam_A,  duration, lambda: self._spawn_highway(self.via_A)))
        self.env.process(self._arrivals(lam_B,  duration, lambda: self._spawn_highway(self.via_B)))
        self.env.process(self._arrivals(lam_bi, duration, self._spawn_buffer_in))
        self.env.process(self._arrivals(lam_vs, duration, self._spawn_vertistop))

    # ── Geradores de chegada ──────────────────────────────────────────────────

    def _arrivals(self, lam: float, duration: float, spawn):
        while True:
            yield self.env.timeout(self._rng.expovariate(lam))
            if self.env.now >= duration:
                return
            spawn()

    def _spawn_highway(self, via: Via):
        self.env.process(self._drone(via, "INPOINT", C["INPOINT"], self._sample_intent()))

    def _spawn_buffer_in(self):
        self.env.process(self._drone(self.via_B, "RETURN_IN", C["RETURN_IN"], UAV_INTENTS.CRUISE))

    def _spawn_vertistop(self):
        self.env.process(self._takeoff())

    # ── Processos de drone ────────────────────────────────────────────────────

    def _drone(self, via: Via, entry: str, entry_x: float, intent: UAV_INTENTS):
        """
        Ciclo completo de um drone na via.

        Regra crítica em cada diverge:
            O drone pede o buffer ANTES de liberar o slot da via.
            Se o buffer estiver cheio, o drone SEGURA o slot — spillback real.
            Só libera o slot quando conseguir entrar no buffer.
        """
        t_born = self.env.now

        # 1. Espera gap no nó de entrada (fila FIFO via MergeNode)
        yield from via.nodes[entry].request()

        # 2. Ocupa slot físico na via
        via_req = via.slots.request()
        t_slot  = self.env.now
        yield via_req
        if self.env.now > t_slot + 0.001:
            self.stats.spillback_events += 1

        # 3. Executa plano de voo
        if intent == UAV_INTENTS.CRUISE:
            yield self.env.timeout(via.travel_time(entry_x, C["FINISH"]))
            via.slots.release(via_req)
            self.stats.record(self.env.now - t_born)

        elif intent == UAV_INTENTS.DESCEND:
            yield self.env.timeout(via.travel_time(entry_x, C["DESCEND"]))
            bfr = self.bfr_descend.request()
            t   = self.env.now
            yield bfr                              # bloqueia se buffer cheio
            if self.env.now > t + 0.001:
                self.stats.spillback_events += 1
            via.slots.release(via_req)             # só agora sai da via
            yield self.env.timeout(self._rng.uniform(30, 60))
            self.bfr_descend.release(bfr)
            self.stats.record(self.env.now - t_born)

        elif intent == UAV_INTENTS.SWITCH:
            yield self.env.timeout(via.travel_time(entry_x, C["SWITCH_OUT"]))
            bfr = self.bfr_switch.request()
            t   = self.env.now
            yield bfr
            if self.env.now > t + 0.001:
                self.stats.spillback_events += 1
            via.slots.release(via_req)
            target = self.via_B if via.name == "A" else self.via_A
            yield from target.nodes["SWITCH_IN"].request()
            tgt_req = target.slots.request()
            t2      = self.env.now
            yield tgt_req
            if self.env.now > t2 + 0.001:
                self.stats.spillback_events += 1
            self.bfr_switch.release(bfr)
            yield self.env.timeout(target.travel_time(C["SWITCH_IN"], C["FINISH"]))
            target.slots.release(tgt_req)
            self.stats.record(self.env.now - t_born)

        elif intent == UAV_INTENTS.RETURN_OUT:
            yield self.env.timeout(via.travel_time(entry_x, C["RETURN_OUT"]))
            bfr = self.bfr_return_out.request()
            t   = self.env.now
            yield bfr
            if self.env.now > t + 0.001:
                self.stats.spillback_events += 1
            via.slots.release(via_req)
            yield self.env.timeout(self._rng.uniform(5, 15))
            self.bfr_return_out.release(bfr)
            self.stats.record(self.env.now - t_born)

    def _takeoff(self):
        bfr = self.bfr_takeoff.request()
        yield bfr
        yield self.env.timeout(C["VERTICAL_TIME"])
        self.bfr_takeoff.release(bfr)
        target = self._rng.choice([self.via_A, self.via_B])
        self.env.process(self._drone(target, "ASCEND", C["ASCEND"], UAV_INTENTS.CRUISE))

    def _sample_intent(self) -> UAV_INTENTS:
        r, cum = self._rng.random(), 0.0
        for key, intent in [
            ("CRUISE",     UAV_INTENTS.CRUISE),
            ("DESCEND",    UAV_INTENTS.DESCEND),
            ("SWITCH",     UAV_INTENTS.SWITCH),
            ("RETURN_OUT", UAV_INTENTS.RETURN_OUT),
        ]:
            cum += FLIGHT_PLAN_CONFIG[key]
            if r < cum:
                return intent
        return UAV_INTENTS.CRUISE