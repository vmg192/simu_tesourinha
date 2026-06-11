from typing import Self
import simpy
import numpy as np
import random

from .constants import TESOURINHA_CONFIG, UAV_CONFIG

class UAV_STATUS(enumerate):
    BUFFERED = 1
    ON_COURSE = 2
    FINISHED = 3

class UAV_INTENTS(enumerate):
    TAKEOFF = 1
    CRUISE = 2
    DESCEND = 3
    SWITCH_IN = 4
    SWITCH_OUT = 5
    ASCEND = 6
    RETURN_OUT = 7
    RETURN_IN = 8
    FINISH = 9


class Tesourinha:
    def __init__(self, env, id):
        self.env = env
        self.id = id
        
        #VIAS
        self.via_A1_0 = simpy.Store(env, capacity=1)
        self.via_A1_1 = simpy.Store(env, capacity=1)
        self.via_A2_0 = simpy.Store(env, capacity=1)
        self.via_A2_1 = simpy.Store(env, capacity=1)

        self.via_B1_0 = simpy.Store(env, capacity=1)
        self.via_B1_1 = simpy.Store(env, capacity=1)
        self.via_B2_0 = simpy.Store(env, capacity=1)
        self.via_B2_1 = simpy.Store(env, capacity=1)

        #PONTOS
        self.return_in = TESOURINHA_CONFIG["RETURN_IN"]
        self.descend = TESOURINHA_CONFIG["DESCEND"]
        self.switch_out = TESOURINHA_CONFIG["SWITCH_OUT"]
        self.middle = TESOURINHA_CONFIG["MIDDLE"]
        self.switch_in = TESOURINHA_CONFIG["SWITCH_IN"]
        self.ascend = TESOURINHA_CONFIG["ASCEND"]
        self.return_out = TESOURINHA_CONFIG["RETURN_OUT"]
        self.finish = TESOURINHA_CONFIG["FINISH"]
 


        self.verde_1 = {
            "NAME": 'OESTE',
            "A": [self.via_A1_0, self.via_A1_1],
            "B": [self.via_B1_0, self.via_B1_1],
            "BFR_TAKEOFF":simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_TAKEOFF"]),
            "BFR_SWITCH":simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_SWITCH"]),
            "BFR_DESCEND":simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_DESCEND"]),
            "BFR_RETURN_IN":simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_RETURN"]),
            "BFR_RETURN_OUT":simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_RETURN"]),
        }
        self.verde_2 = {
            "NAME": 'LESTE',
            "A": [self.via_A2_0, self.via_A2_1],
            "B": [self.via_B2_0, self.via_B2_1],
            "BFR_TAKEOFF":simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_TAKEOFF"]),
            "BFR_SWITCH":simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_SWITCH"]),
            "BFR_DESCEND":simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_DESCEND"]),
            "BFR_RETURN_IN":simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_RETURN"]),
            "BFR_RETURN_OUT":simpy.Store(env, capacity=TESOURINHA_CONFIG["BFR_RETURN"]),
        }
    
    def block_via(self, store, uav):
        yield store.put(uav)
        print('drone ocupou')
    
    def unlock_via(self, store, delta):
        yield self.env.timeout(delta)
        req = yield store.get()
        print('drone liberou')
    
    def put_buffer(self, buffer, uav):
        yield buffer.put(uav)
        print(f'UAV {uav.name} foi colocado no buffer {buffer}')

    def get_buffer(self, buffer):
        uav = yield buffer.get()
        print(f'UAV {uav.name} foi retirado do buffer {buffer}')
        return uav

    def takeoff_to_via(self, verde_area, uav, side, via_index, label):
        yield from self.put_buffer(verde_area[side][via_index], uav)
        yield from self.get_buffer(verde_area["BFR_TAKEOFF"])
        print(f'UAV {uav.name} realizou {label} para o lado {side} em {verde_area["NAME"]}.')
    
    def drone_lifetime(self, uav):
        r = random.random()
        for intent in uav.route:
            match intent:
                case UAV_INTENTS.CRUISE:
                    uav.status = UAV_STATUS.FINISHED
                    pass
                case UAV_INTENTS.TAKEOFF:
                    verde_area = random.choice([self.verde_1, self.verde_2])
                    yield from self.put_buffer(verde_area["BFR_TAKEOFF"], uav)
                    yield self.env.timeout(TESOURINHA_CONFIG["TAKEOFF"])

                    if r <= 0.333:
                        yield from self.takeoff_to_via(verde_area, uav, "A", 0, "TAKEOFF")
                    elif r <= 0.666:
                        yield from self.takeoff_to_via(verde_area, uav, "B", 0, "TAKEOFF")
                    elif r <= 0.833:
                        yield from self.takeoff_to_via(verde_area, uav, "A", 1, "ASCEND")
                    else:
                        yield from self.takeoff_to_via(verde_area, uav, "B", 1, "ASCEND")
                case UAV_INTENTS.DESCEND:
                    # lógica para DESCEND
                    pass
                case UAV_INTENTS.SWITCH_OUT:
                    # lógica para SWITCH_OUT
                    pass
                case UAV_INTENTS.SWITCH_IN:
                    # lógica para SWITCH_IN
                    pass
                case UAV_INTENTS.ASCEND:
                    # lógica para ASCEND
                    pass
                case UAV_INTENTS.RETURN_OUT:
                    # lógica para RETURN_OUT
                    pass
                case UAV_INTENTS.RETURN_IN:
                    # lógica para RETURN_IN
                    pass
                case _:
                    # intent desconhecido
                    pass
    



class UAV:
    def __init__(self, env, name, route, origin):
        self.name = name
        self.route = route
        self.speed = UAV_CONFIG["SPEED"]
        self.origin = origin
        self.creation_time = env.now

        self.status = UAV_STATUS.BUFFERED      


        


#TESOURINHA_CONFIG = {
#    "NUM_SLOTS": 2,
#     "LENGTH":60.0,
#     "RETURN_IN":3.0,
#     "DESCEND": 12.0,
#     "SWITCH_OUT": 26.0,
#     "MIDDLE": 30.0,
#     "SWITCH_IN": 38.0,
#     "ASCEND": 50.0,
#     "RETURN_OUT": 56.0,
# }