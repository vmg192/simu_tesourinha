import simpy
import random
import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt

# ==========================================
# CONSTANTES GERAIS
# ==========================================
TES_LENGTH = 60.0         # m
DESCEND_TIME = 33.0       # s
ASCEND_TIME = 33.0        # s

CAPACITIES = {
    'descend': 21,
    'switch': 16,
    'buffer_in': 10,
    'buffer_out': 10,
    'vertistop': 50
}

PROB_CRUISE = 0.65
PROB_DESCEND = 0.12
PROB_SWITCH = 0.115
PROB_RETURN_OUT = 0.115

class DroneRoute:
    CRUISE = 'cruise'
    DESCEND = 'descend'
    SWITCH = 'switch'
    RETURN_OUT = 'return_out'
    RETURN_IN_TO_B = 'return_in_to_b'
    RETURN_IN_TO_A = 'return_in_to_a'
    RETURN_IN_TO_DESCEND = 'return_in_to_descend'
    TAKEOFF_TO_A = 'takeoff_to_a'
    TAKEOFF_TO_B = 'takeoff_to_b'
    TAKEOFF_TO_RETURN_OUT = 'takeoff_to_return_out'

class Config:
    def __init__(self, v):
        self.V_TES_BASE = v
        if v == 10.0:
            self.H_CRUISE = 2.8
            self.H_MERGE = 4.8
            self.BP_THRESHOLDS = [(0.50, 10.0, 1.0), (0.70, 8.0, 1.25), (0.90, 6.0, 1.66), (2.0, 4.0, 2.50)]
        elif v == 15.0:
            self.H_CRUISE = 3.9
            self.H_MERGE = 6.0
            self.BP_THRESHOLDS = [(0.50, 15.0, 1.0), (0.70, 12.0, 1.25), (0.90, 10.0, 1.66), (2.0, 8.0, 2.50)]

# ==========================================
# CLASSES DE DOMÍNIO
# ==========================================
class Drone:
    def __init__(self, env, config, drone_id, origin, route):
        self.env = env
        self.id = drone_id
        self.origin = origin
        self.route = route
        self.creation_time = env.now
        self.v_gen = config.V_TES_BASE
        
        self.t_buffer_enter = None
        self.t_buffer_exit = None
        self.t_exit = None

class AirTesourinha:
    def __init__(self, env, config):
        self.env = env
        self.config = config
        
        self.b_descend = simpy.Store(env, capacity=CAPACITIES['descend'])
        self.b_switch = simpy.Store(env, capacity=CAPACITIES['switch'])
        self.b_in = simpy.Store(env, capacity=CAPACITIES['buffer_in'])
        self.b_out = simpy.Store(env, capacity=CAPACITIES['buffer_out'])
        
        self.vertistop_count = 10
        self.vertistop_max = CAPACITIES['vertistop']
        
        self.via_A_merge_lock = simpy.Resource(env, capacity=1)
        self.via_B_merge_lock = simpy.Resource(env, capacity=1)

        self.via_A_blocked = False
        self.via_B_blocked = False
        
        self.completed_drones = 0
        self.spillback_events = 0
        self.blocked_time = 0.0
        self.last_block_time_A = 0
        self.last_block_time_B = 0
        
        self.max_occ_descend = 0
        self.max_occ_switch = 0
        self.max_occ_out = 0
        
        self.wait_descend_sum = 0.0
        self.wait_switch_sum = 0.0
        self.count_descend = 0
        self.count_switch = 0
        
        self.total_generated = 0
        self.bp_activated_count = 0
        self.drone_logs = []

    def record_wait(self, buffer_name, wait_time):
        if buffer_name == 'descend':
            self.wait_descend_sum += wait_time
            self.count_descend += 1
        elif buffer_name == 'switch':
            self.wait_switch_sum += wait_time
            self.count_switch += 1

    def update_occupancies(self):
        self.max_occ_descend = max(self.max_occ_descend, len(self.b_descend.items) + 1)
        self.max_occ_switch = max(self.max_occ_switch, len(self.b_switch.items) + 1)
        self.max_occ_out = max(self.max_occ_out, len(self.b_out.items) + 1)

    def mark_blocked(self, via_name):
        self.spillback_events += 1
        if via_name == 'A' and not self.via_A_blocked:
            self.via_A_blocked = True
            self.last_block_time_A = self.env.now
        elif via_name == 'B' and not self.via_B_blocked:
            self.via_B_blocked = True
            self.last_block_time_B = self.env.now

    def mark_unblocked(self, via_name):
        if via_name == 'A' and self.via_A_blocked:
            self.via_A_blocked = False
            self.blocked_time += (self.env.now - self.last_block_time_A)
        elif via_name == 'B' and self.via_B_blocked:
            self.via_B_blocked = False
            self.blocked_time += (self.env.now - self.last_block_time_B)

    def get_backpressure_state(self):
        occs = [
            len(self.b_descend.items) / self.b_descend.capacity,
            len(self.b_switch.items) / self.b_switch.capacity,
            len(self.b_in.items) / self.b_in.capacity,
            len(self.b_out.items) / self.b_out.capacity
        ]
        rho = max(occs) if occs else 0.0
        
        for limit, v, factor in self.config.BP_THRESHOLDS:
            if rho <= limit:
                return v, factor
        return self.config.BP_THRESHOLDS[-1][1], self.config.BP_THRESHOLDS[-1][2]

# ==========================================
# PROCESSOS SIMPY
# ==========================================
def inpoint_generator(env, tes, via_name, lambda_rate_per_via):
    seq = 0
    while True:
        v_gen, f_t = tes.get_backpressure_state()
        rate_sec = lambda_rate_per_via / 3600.0
        if rate_sec == 0: break
            
        base_interval = max(random.expovariate(rate_sec), tes.config.H_CRUISE)
        interval = base_interval * f_t
        yield env.timeout(interval)
        
        if (via_name == 'A' and tes.via_A_blocked) or (via_name == 'B' and tes.via_B_blocked):
            continue

        r = random.random()
        if r <= PROB_CRUISE: route = DroneRoute.CRUISE
        elif r <= PROB_CRUISE + PROB_DESCEND: route = DroneRoute.DESCEND
        elif r <= PROB_CRUISE + PROB_DESCEND + PROB_SWITCH: route = DroneRoute.SWITCH
        else: route = DroneRoute.RETURN_OUT
                
        drone = Drone(env, tes.config, f"{via_name}-{seq}", via_name, route)
        drone.v_gen = v_gen
        
        tes.total_generated += 1
        if v_gen < tes.config.V_TES_BASE:
            tes.bp_activated_count += 1
            
        seq += 1
        env.process(drone_lifecycle(env, tes, drone))

def buffer_in_generator(env, tes, lambda_rate_in):
    seq = 0
    while True:
        v_gen, f_t = tes.get_backpressure_state()
        rate_sec = lambda_rate_in / 3600.0
        if rate_sec == 0: break
            
        base_interval = max(random.expovariate(rate_sec), tes.config.H_CRUISE)
        interval = base_interval * f_t
        yield env.timeout(interval)
        
        r = random.random()
        if r <= 0.333: route = DroneRoute.RETURN_IN_TO_B
        elif r <= 0.666: route = DroneRoute.RETURN_IN_TO_A
        else: route = DroneRoute.RETURN_IN_TO_DESCEND
                
        drone = Drone(env, tes.config, f"IN-{seq}", 'B', route)
        drone.v_gen = v_gen
        
        tes.total_generated += 1
        seq += 1
        env.process(drone_lifecycle(env, tes, drone))

def vertistop_manager(env, tes, takeoff_lambda):
    env.process(human_rotation(env, tes))
    
    seq = 0
    while True:
        rate_sec = takeoff_lambda / 3600.0
        if rate_sec == 0: break
        
        interval = random.expovariate(rate_sec)
        yield env.timeout(interval)
        
        if tes.vertistop_count > 0:
            tes.vertistop_count -= 1
            tes.update_occupancies()
            
            r = random.random()
            if r <= 0.333:
                route = DroneRoute.TAKEOFF_TO_A
                origin = 'A'
            elif r <= 0.666:
                route = DroneRoute.TAKEOFF_TO_B
                origin = 'B'
            else:
                route = DroneRoute.TAKEOFF_TO_RETURN_OUT
                origin = 'B'
                
            drone = Drone(env, tes.config, f"V-{seq}", origin, route)
            drone.v_gen = tes.config.V_TES_BASE
            
            seq += 1
            env.process(drone_lifecycle(env, tes, drone))

def human_rotation(env, tes):
    while True:
        yield env.timeout(1200) # 20 minutos
        if random.random() <= 0.5:
            if random.random() <= 0.5 and tes.vertistop_count < tes.vertistop_max:
                tes.vertistop_count += 1
            elif tes.vertistop_count > 0:
                tes.vertistop_count -= 1
            tes.update_occupancies()

def drone_lifecycle(env, tes, drone):
    if drone.route == DroneRoute.CRUISE:
        yield env.timeout(TES_LENGTH / drone.v_gen)
        tes.completed_drones += 1
        
    elif drone.route == DroneRoute.DESCEND:
        yield env.timeout(12.0 / drone.v_gen)
        
        if len(tes.b_descend.items) == tes.b_descend.capacity:
            tes.mark_blocked(drone.origin)
            
        tes.update_occupancies()
        drone.t_buffer_enter = env.now
        
        req = tes.b_descend.put(drone)
        yield req
        tes.mark_unblocked(drone.origin)
        
        yield env.timeout(DESCEND_TIME)
        yield env.timeout(random.uniform(3, 8)) 
        
        yield tes.b_descend.get() 
        drone.t_buffer_exit = env.now
        tes.record_wait('descend', drone.t_buffer_exit - drone.t_buffer_enter)
        
        if tes.vertistop_count < tes.vertistop_max:
            tes.vertistop_count += 1
        tes.update_occupancies()
        tes.completed_drones += 1
            
    elif drone.route == DroneRoute.SWITCH:
        yield env.timeout(26.0 / drone.v_gen)
        
        if len(tes.b_switch.items) == tes.b_switch.capacity:
            tes.mark_blocked(drone.origin)
            
        tes.update_occupancies()
        drone.t_buffer_enter = env.now
        
        req = tes.b_switch.put(drone)
        yield req
        tes.mark_unblocked(drone.origin)
        
        dest_lock = tes.via_B_merge_lock if drone.origin == 'A' else tes.via_A_merge_lock
        with dest_lock.request() as merge_req:
            yield merge_req
            yield env.timeout(tes.config.H_MERGE)
            
        yield tes.b_switch.get()
        drone.t_buffer_exit = env.now
        tes.record_wait('switch', drone.t_buffer_exit - drone.t_buffer_enter)
        
        yield env.timeout(22.0 / tes.config.V_TES_BASE)
        tes.completed_drones += 1
        
    elif drone.route == DroneRoute.RETURN_OUT:
        yield env.timeout(26.0 / drone.v_gen)
        
        if len(tes.b_switch.items) == tes.b_switch.capacity:
            tes.mark_blocked(drone.origin)
            
        tes.update_occupancies()
        t_enter_sw = env.now
        yield tes.b_switch.put(drone)
        tes.mark_unblocked(drone.origin)
        
        dest_via = 'B' if drone.origin == 'A' else 'A'
        dest_lock = tes.via_B_merge_lock if drone.origin == 'A' else tes.via_A_merge_lock
        
        with dest_lock.request() as merge_req:
            yield merge_req
            yield env.timeout(tes.config.H_MERGE)
            
        yield tes.b_switch.get()
        tes.record_wait('switch', env.now - t_enter_sw)
        
        yield env.timeout(18.0 / tes.config.V_TES_BASE)
        
        if len(tes.b_out.items) == tes.b_out.capacity:
            tes.mark_blocked(dest_via)
            
        tes.update_occupancies()
        yield tes.b_out.put(drone)
        tes.mark_unblocked(dest_via)
        
        yield env.timeout(random.uniform(2, 5))
        yield tes.b_out.get()
        tes.completed_drones += 1

    elif drone.route in [DroneRoute.RETURN_IN_TO_B, DroneRoute.RETURN_IN_TO_A, DroneRoute.RETURN_IN_TO_DESCEND]:
        tes.update_occupancies()
        yield tes.b_in.put(drone)
        
        with tes.via_B_merge_lock.request() as merge_req:
            yield merge_req
            yield env.timeout(tes.config.H_MERGE)
            
        yield tes.b_in.get()
        
        if drone.route == DroneRoute.RETURN_IN_TO_B:
            yield env.timeout(57.0 / drone.v_gen)
            tes.completed_drones += 1
            
        elif drone.route == DroneRoute.RETURN_IN_TO_A:
            yield env.timeout(23.0 / drone.v_gen)
            yield tes.b_switch.put(drone)
            with tes.via_A_merge_lock.request() as merge_req:
                yield merge_req
                yield env.timeout(tes.config.H_MERGE)
            yield tes.b_switch.get()
            yield env.timeout(22.0 / tes.config.V_TES_BASE)
            tes.completed_drones += 1
            
        elif drone.route == DroneRoute.RETURN_IN_TO_DESCEND:
            yield env.timeout(9.0 / drone.v_gen)
            yield tes.b_descend.put(drone)
            yield env.timeout(DESCEND_TIME)
            yield env.timeout(random.uniform(3, 8))
            yield tes.b_descend.get()
            
            if tes.vertistop_count < tes.vertistop_max:
                tes.vertistop_count += 1
            tes.update_occupancies()
            tes.completed_drones += 1

    elif drone.route in [DroneRoute.TAKEOFF_TO_A, DroneRoute.TAKEOFF_TO_B, DroneRoute.TAKEOFF_TO_RETURN_OUT]:
        yield env.timeout(ASCEND_TIME)
        
        dest_lock = tes.via_A_merge_lock if drone.origin == 'A' else tes.via_B_merge_lock
        with dest_lock.request() as merge_req:
            yield merge_req
            yield env.timeout(tes.config.H_MERGE)
            
        if drone.route == DroneRoute.TAKEOFF_TO_A:
            yield env.timeout(10.0 / tes.config.V_TES_BASE)
            tes.completed_drones += 1
            
        elif drone.route == DroneRoute.TAKEOFF_TO_B:
            yield env.timeout(10.0 / tes.config.V_TES_BASE)
            tes.completed_drones += 1
            
        elif drone.route == DroneRoute.TAKEOFF_TO_RETURN_OUT:
            yield env.timeout(6.0 / tes.config.V_TES_BASE)
            yield tes.b_out.put(drone)
            yield env.timeout(random.uniform(2, 5))
            yield tes.b_out.get()
            tes.completed_drones += 1

# ==========================================
# GRID SEARCH & PLOTTING
# ==========================================
def run_comparative_grid_search():
    os.makedirs('logs', exist_ok=True)
    
    densities = [500, 800, 1100, 1400, 1700, 2000]
    replications = 10
    sim_time = 4 * 3600
    
    all_results = []
    
    for v in [10.0, 15.0]:
        print(f"\n--- Iniciando Simulação para V = {v} m/s ---")
        config = Config(v)
        
        for d in densities:
            d_throughput = []
            d_spillbacks = []
            
            for rep in range(replications):
                random.seed(42 + rep + int(v*100)) 
                
                env = simpy.Environment()
                tes = AirTesourinha(env, config)
                
                env.process(inpoint_generator(env, tes, 'A', d / 2))
                env.process(inpoint_generator(env, tes, 'B', d / 2))
                env.process(buffer_in_generator(env, tes, d * 0.07))
                env.process(vertistop_manager(env, tes, d * 0.14))
                
                env.run(until=sim_time)
                
                d_throughput.append(tes.completed_drones / 4.0)
                d_spillbacks.append(tes.spillback_events)
                
            avg_t = np.mean(d_throughput)
            avg_s = np.mean(d_spillbacks)
            
            all_results.append({
                'Velocidade': v,
                'Densidade_Input': d,
                'Throughput': avg_t,
                'Spillbacks': avg_s
            })
            print(f"Densidade: {d:<5} | Throughput: {avg_t:<7.1f} | Spillbacks: {avg_s:<6.1f}")

    df = pd.DataFrame(all_results)
    
    # Gerando os gráficos
    plt.figure(figsize=(14, 6))
    
    # Subplot 1: Throughput vs Densidade
    plt.subplot(1, 2, 1)
    df_10 = df[df['Velocidade'] == 10.0]
    df_15 = df[df['Velocidade'] == 15.0]
    
    plt.plot(df_10['Densidade_Input'], df_10['Throughput'], marker='o', label='V = 10 m/s', color='green')
    plt.plot(df_15['Densidade_Input'], df_15['Throughput'], marker='x', label='V = 15 m/s', color='red')
    ideal_throughputs = [d * 1.21 for d in densities]
    plt.plot(densities, ideal_throughputs, '--', color='gray', alpha=0.5, label='Throughput Ideal (Total Demand)')
    
    plt.title('Capacidade de Escoamento (Throughput) por Via')
    plt.xlabel('Densidade Exigida no Inpoint (Drones/hora)')
    plt.ylabel('Throughput Efetivo Processado (Drones/hora)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Subplot 2: Eventos de Spillback (Travamento Físico)
    plt.subplot(1, 2, 2)
    plt.plot(df_10['Densidade_Input'], df_10['Spillbacks'], marker='o', label='V = 10 m/s', color='green')
    plt.plot(df_15['Densidade_Input'], df_15['Spillbacks'], marker='x', label='V = 15 m/s', color='red')
    
    plt.title('Eventos de Colapso por Superlotação (Spillbacks)')
    plt.xlabel('Densidade Exigida no Inpoint (Drones/hora)')
    plt.ylabel('Média de Ocorrências (Falhas)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('logs/comparacao_velocidades.png', dpi=300)
    plt.close()
    
    print("\nSimulação concluída! Gráfico salvo em 'logs/comparacao_velocidades.png'")

if __name__ == "__main__":
    run_comparative_grid_search()
