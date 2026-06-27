TESOURINHA_CONFIG = {
    "LENGTH":        60.0,
    "INPOINT":        0.0,
    "RETURN_IN":      6.0,
    "DESCEND":       12.0,
    "SWITCH_OUT":    20.0,
    "SWITCH_IN":     40.0,
    "ASCEND":        48.0,
    "RETURN_OUT":    54.0,
    "FINISH":        60.0,
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

# ─── Cenários de rotas ────────────────────────────────────────────────────────
# Cada entry point tem uma lista de (peso, sequência de ações).
# Ações válidas por entry point dependem da geometria:
#   INPOINT (x=0)   : DESCEND, SWITCH, RETURN_OUT, FINISH
#   RETURN_IN (x=6) : DESCEND, SWITCH, RETURN_OUT, FINISH
#   SWITCH_IN (x=40): RETURN_OUT, FINISH   (DESCEND/SWITCH ficam para trás)
#   ASCEND (x=48)   : RETURN_OUT, FINISH
#
# Após SWITCH o drone entra na via oposta em SWITCH_IN (x=40)
# e continua a lista de ações restantes nessa nova via.

ROUTE_SCENARIOS = {
    "default": {
        "INPOINT": [
            (0.40, ["FINISH"]),
            (0.15, ["DESCEND"]),
            (0.10, ["RETURN_OUT"]),
            (0.20, ["SWITCH", "FINISH"]),
            (0.15, ["SWITCH", "RETURN_OUT"]),
        ],
        "RETURN_IN": [
            (0.50, ["FINISH"]),
            (0.20, ["DESCEND"]),
            (0.10, ["RETURN_OUT"]),
            (0.15, ["SWITCH", "FINISH"]),
            (0.05, ["SWITCH", "RETURN_OUT"]),
        ],
        "SWITCH_IN": [
            (0.70, ["FINISH"]),
            (0.30, ["RETURN_OUT"]),
        ],
        "ASCEND": [
            (0.80, ["FINISH"]),
            (0.20, ["RETURN_OUT"]),
        ],
    },
    "heavy_descend": {
        "INPOINT": [
            (0.25, ["FINISH"]),
            (0.35, ["DESCEND"]),
            (0.10, ["RETURN_OUT"]),
            (0.20, ["SWITCH", "FINISH"]),
            (0.10, ["SWITCH", "RETURN_OUT"]),
        ],
        "RETURN_IN": [
            (0.30, ["FINISH"]),
            (0.40, ["DESCEND"]),
            (0.10, ["RETURN_OUT"]),
            (0.15, ["SWITCH", "FINISH"]),
            (0.05, ["SWITCH", "RETURN_OUT"]),
        ],
        "SWITCH_IN": [
            (0.70, ["FINISH"]),
            (0.30, ["RETURN_OUT"]),
        ],
        "ASCEND": [
            (0.80, ["FINISH"]),
            (0.20, ["RETURN_OUT"]),
        ],
    },
    "heavy_switch": {
        "INPOINT": [
            (0.20, ["FINISH"]),
            (0.10, ["DESCEND"]),
            (0.05, ["RETURN_OUT"]),
            (0.40, ["SWITCH", "FINISH"]),
            (0.25, ["SWITCH", "RETURN_OUT"]),
        ],
        "RETURN_IN": [
            (0.25, ["FINISH"]),
            (0.10, ["DESCEND"]),
            (0.05, ["RETURN_OUT"]),
            (0.40, ["SWITCH", "FINISH"]),
            (0.20, ["SWITCH", "RETURN_OUT"]),
        ],
        "SWITCH_IN": [
            (0.70, ["FINISH"]),
            (0.30, ["RETURN_OUT"]),
        ],
        "ASCEND": [
            (0.80, ["FINISH"]),
            (0.20, ["RETURN_OUT"]),
        ],
    },
}

# ─── Cenários de fontes ───────────────────────────────────────────────────────
# Fração de cada fonte no λ total (drones/hora).
# Devem somar 1.0.

SOURCE_SCENARIOS = {
    "balanced": {
        "HIGHWAY_A": 0.45,
        "HIGHWAY_B": 0.45,
        "BUFFER_IN": 0.07,
        "VERTISTOP": 0.03,
    },
    "heavy_highway": {
        "HIGHWAY_A": 0.48,
        "HIGHWAY_B": 0.48,
        "BUFFER_IN": 0.02,
        "VERTISTOP": 0.02,
    },
    "heavy_vertistop": {
        "HIGHWAY_A": 0.35,
        "HIGHWAY_B": 0.35,
        "BUFFER_IN": 0.10,
        "VERTISTOP": 0.20,
    },
    "heavy_opposing": {
        "HIGHWAY_A": 0.35,
        "HIGHWAY_B": 0.35,
        "BUFFER_IN": 0.25,
        "VERTISTOP": 0.05,
    },
}

SIM_CONFIG = {
    "DURATION":         14_400,
    "REPLICATIONS":     10,
    "SPEEDS":           [4.0, 6.0, 8.0, 10.0, 15.0],
    "LAMBDAS":          list(range(50, 2001, 100)),
    "SOURCE_SCENARIOS": ["balanced", "heavy_highway", "heavy_vertistop", "heavy_opposing"],
    "ROUTE_SCENARIOS":  ["default", "heavy_descend", "heavy_switch"],
}