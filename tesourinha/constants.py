TESOURINHA_CONFIG = {
    "LENGTH":       60.0,
    "INPOINT":       0.0,
    "RETURN_IN":     6.0,
    "DESCEND":      12.0,
    "SWITCH_OUT":   20.0,
    "SWITCH_IN":    40.0,
    "ASCEND":       48.0,
    "RETURN_OUT":   54.0,
    "FINISH":       60.0,
    "VERTICAL_TIME": 33.0,
    "BFR_DESCEND":   21,
    "BFR_SWITCH":    16,
    "BFR_RETURN_OUT": 10,
    "BFR_TAKEOFF":   21,
}

UAV_CONFIG = {
    "LENGTH":      6.0,
    "DECEL":       3.0,
    "V2V_LATENCY": 0.5,
}

FLIGHT_PLAN_CONFIG = {
    "CRUISE":     0.65,
    "DESCEND":    0.12,
    "SWITCH":     0.08,
    "RETURN_OUT": 0.08,
}

SOURCE_CONFIG = {
    "HIGHWAY_A": 0.45,
    "HIGHWAY_B": 0.45,
    "BUFFER_IN": 0.07,
    "VERTISTOP": 0.03,
}

SIM_CONFIG = {
    "DURATION":     14_400,
    "REPLICATIONS": 10,
    "SPEEDS":       [4.0, 6.0, 8.0, 10.0, 15.0],
    "LAMBDAS":      list(range(50, 501, 50)),
}