import csv
from tesourinha import grid_search, geofence, h_cruise, h_merge, via_slots, SIM_CONFIG

if __name__ == "__main__":
    print(f"{'v':>6} | {'G(m)':>7} | {'slots':>5} | {'h_cruise':>8} | {'h_merge':>8}")
    for v in SIM_CONFIG["SPEEDS"]:
        print(f"{v:6.1f} | {geofence(v):7.2f} | {via_slots(v):5d} | {h_cruise(v):7.2f}s | {h_merge(v):7.2f}s")

    results = grid_search(verbose=True)

    fields = list(results[0].__dataclass_fields__.keys())
    with open("results.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow({k: getattr(r, k) for k in fields})
    print("\nSalvo em results.csv")

    from plot_results import plot_results
    for p in plot_results():
        print(f"  • {p}")