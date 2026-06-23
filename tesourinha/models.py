from enum import IntEnum
import random

import simpy

from .constants import TESOURINHA_CONFIG, UAV_CONFIG


class UAV_STATUS(IntEnum):
    BUFFERED = 1
    ON_COURSE = 2
    FINISHED = 3


class UAV_INTENTS(IntEnum):
    TAKEOFF = 1
    CRUISE = 2
    DESCEND = 3
    SWITCH_IN = 4
    SWITCH_OUT = 5
    ASCEND = 6
    RETURN_OUT = 7
    RETURN_IN = 8
    FINISH = 9
    MIDDLE_OUT = 10


class Tesourinha:
    def __init__(self, env, id):
        self.env = env
        self.id = id

        # VIAS
        self.via_A1_0 = simpy.Store(env, capacity=1)
        self.via_A1_1 = simpy.Store(env, capacity=1)
        self.via_A_MIDDLE = simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_MIDDLE"])

        self.via_B1_0 = simpy.Store(env, capacity=1)
        self.via_B1_1 = simpy.Store(env, capacity=1)
        self.via_B_MIDDLE = simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_MIDDLE"])

        # PONTOS
        self.return_in = TESOURINHA_CONFIG["RETURN_IN"]
        self.descend = TESOURINHA_CONFIG["DESCEND"]
        self.switch_out = TESOURINHA_CONFIG["SWITCH_OUT"]
        self.middle_in = TESOURINHA_CONFIG["MIDDLE_IN"]
        self.middle_out = TESOURINHA_CONFIG["MIDDLE_OUT"]
        self.switch_in = TESOURINHA_CONFIG["SWITCH_IN"]
        self.ascend = TESOURINHA_CONFIG["ASCEND"]
        self.return_out = TESOURINHA_CONFIG["RETURN_OUT"]
        self.finish = TESOURINHA_CONFIG["FINISH"]

        self.verde_1 = {
            "NAME": "OESTE",
            "A": [self.via_A1_0, self.via_A_MIDDLE, self.via_A1_1],
            "B": [self.via_B1_0, self.via_B_MIDDLE, self.via_B1_1],
            "BFR_TAKEOFF": simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_TAKEOFF"]),
            "BFR_ASCEND": simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_ASCEND"]),
            "BFR_SWITCH": simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_SWITCH"]),
            "BFR_DESCEND": simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_DESCEND"]),
            "BFR_RETURN_IN": simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_RETURN"]),
            "BFR_RETURN_OUT": simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_RETURN"]),
            "BFR_MIDDLE": self.via_A_MIDDLE,
        }

    def block_via(self, store, uav):
        yield store.put(uav)
        uav.status = UAV_STATUS.ON_COURSE
        print(f"UAV {uav.name} foi colocado na via {store}")

    def unlock_via(self, store):
        uav = yield store.get()
        print(f"UAV {uav.name} liberou a via {store}")

    def put_buffer(self, buffer, uav):
        yield buffer.put(uav)
        uav.origin = buffer
        uav.status = UAV_STATUS.BUFFERED
        print(f"UAV {uav.name} foi colocado no buffer {buffer}")

    def get_buffer(self, buffer):
        uav = yield buffer.get()
        print(f"UAV {uav.name} foi retirado do buffer {buffer}")
        return uav

    def takeoff_to_via(self, verde_area, uav, side, via_index, label, origin):
        yield from self.block_via(verde_area[side][via_index], uav)
        uav.origin = verde_area[side][via_index]
        yield from self.get_buffer(verde_area[origin])
        print(f'UAV {uav.name} realizou {label} para o lado {side} em {verde_area["NAME"]}.')

    def initial_pos(self, origin):
        if origin == UAV_INTENTS.TAKEOFF:
            return TESOURINHA_CONFIG["INPOINT"]
        elif origin == UAV_INTENTS.ASCEND:
            return TESOURINHA_CONFIG["ASCEND"]
        elif origin == UAV_INTENTS.RETURN_IN:
            return TESOURINHA_CONFIG["RETURN_IN"]
        elif origin == UAV_INTENTS.SWITCH_IN:
            return TESOURINHA_CONFIG["SWITCH_IN"]
        elif origin == UAV_INTENTS.MIDDLE_OUT:
            return TESOURINHA_CONFIG["MIDDLE_OUT"]

        return TESOURINHA_CONFIG["INPOINT"]

    def get_via_side(self, via_obj, switch=False):
        """
        Dado um objeto de via, determina se ele está no lado 'A' ou 'B' da verde_1.
        Retorna 'A' se está em verde_1["A"], 'B' se está em verde_1["B"], ou None se não pertence a nenhum lado.
        """
        if via_obj in self.verde_1.get("A", []):
            return "B" if switch else "A"
        elif via_obj in self.verde_1.get("B", []):
            return "A" if switch else "B"

        return None

    def drone_lifetime(self, uav):
        last = None
        for intent in uav.route:
            if last:
                initial_pos = self.initial_pos(last)
            match intent:
                case UAV_INTENTS.CRUISE:
                    pass

                case UAV_INTENTS.TAKEOFF:
                    last = UAV_INTENTS.TAKEOFF
                    yield from self.put_buffer(self.verde_1["BFR_TAKEOFF"], uav)
                    yield from self.takeoff_to_via(
                        self.verde_1, uav, uav.in_origin, 0, "TAKEOFF", "BFR_TAKEOFF"
                    )
                    yield self.env.timeout(TESOURINHA_CONFIG["TAKEOFF"])

                case UAV_INTENTS.DESCEND:
                    delta = abs(TESOURINHA_CONFIG["DESCEND"] - initial_pos) / uav.speed
                    yield self.env.timeout(delta)
                    temp_origin = uav.origin
                    yield self.env.timeout(TESOURINHA_CONFIG["BUFFER_DIST"] / uav.speed)
                    yield from self.put_buffer(self.verde_1["BFR_DESCEND"], uav)
                    yield from self.unlock_via(temp_origin)

                    yield self.env.timeout(random.uniform(30, 60))
                    yield from self.get_buffer(self.verde_1["BFR_DESCEND"])

                    uav.status = UAV_STATUS.FINISHED

                case UAV_INTENTS.SWITCH_OUT:
                    delta = abs(TESOURINHA_CONFIG["SWITCH_OUT"] - initial_pos) / uav.speed
                    yield self.env.timeout(delta)
                    yield self.env.timeout(TESOURINHA_CONFIG["BUFFER_DIST"] / uav.speed)
                    temp_origin = uav.origin
                    uav.switch_from_side = self.get_via_side(temp_origin)
                    yield from self.put_buffer(self.verde_1["BFR_SWITCH"], uav)
                    yield from self.unlock_via(temp_origin)

                case UAV_INTENTS.SWITCH_IN:
                    last = UAV_INTENTS.SWITCH_IN
                    side = "B" if uav.switch_from_side == "A" else "A"
                    yield from self.takeoff_to_via(
                        self.verde_1, uav, side, 2, "SWITCH", "BFR_SWITCH"
                    )

                case UAV_INTENTS.ASCEND:
                    last = UAV_INTENTS.ASCEND
                    yield from self.put_buffer(self.verde_1["BFR_ASCEND"], uav)
                    yield from self.takeoff_to_via(
                        self.verde_1, uav, uav.in_origin, 0, "ASCEND", "BFR_ASCEND"
                    )
                    yield self.env.timeout(TESOURINHA_CONFIG["TAKEOFF"])

                case UAV_INTENTS.RETURN_OUT:
                    if last == UAV_INTENTS.TAKEOFF and self.get_via_side(uav.origin) == "A":
                        delta = abs(TESOURINHA_CONFIG["MIDDLE_IN"] - initial_pos) / uav.speed
                        yield self.env.timeout(delta)

                        temp_origin = uav.origin
                        yield from self.put_buffer(self.verde_1["BFR_MIDDLE"], uav)
                        yield from self.takeoff_to_via(
                            self.verde_1, uav, "A", 2, "MIDDLE", "BFR_MIDDLE"
                        )
                        yield from self.unlock_via(temp_origin)
                        initial_pos = self.initial_pos(UAV_INTENTS.MIDDLE_OUT)

                    delta = abs(TESOURINHA_CONFIG["RETURN_OUT"] - initial_pos) / uav.speed
                    yield self.env.timeout(delta)
                    yield self.env.timeout(TESOURINHA_CONFIG["BUFFER_DIST"] / uav.speed)
                    temp_origin = uav.origin
                    yield from self.put_buffer(self.verde_1["BFR_RETURN_OUT"], uav)
                    yield from self.unlock_via(temp_origin)
                    yield self.env.timeout(random.uniform(30, 60))
                    yield from self.get_buffer(uav.origin)
                    uav.status = UAV_STATUS.FINISHED

                case UAV_INTENTS.RETURN_IN:
                    last = UAV_INTENTS.RETURN_IN
                    yield from self.put_buffer(self.verde_1["BFR_RETURN_IN"], uav)
                    yield from self.takeoff_to_via(
                        self.verde_1, uav, "A", 0, "RETURN_IN", "BFR_RETURN_IN"
                    )
                    yield self.env.timeout(TESOURINHA_CONFIG["TAKEOFF"])

                case UAV_INTENTS.FINISH:
                    delta = abs(TESOURINHA_CONFIG["FINISH"] - initial_pos) / uav.speed
                    yield self.env.timeout(delta)
                    yield from self.unlock_via(uav.origin)


class UAV:
    def __init__(self, env, name, route, origin, in_origin):
        self.name = name
        self.route = route
        self.speed = UAV_CONFIG["SPEED"]
        self.origin = origin
        self.creation_time = env.now
        self.in_origin = in_origin
        self.status = UAV_STATUS.BUFFERED
        self.switch_from_side = None
