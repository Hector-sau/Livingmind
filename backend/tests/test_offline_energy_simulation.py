from app.energy.simulation import offline_energy_simulation


def test_supplied_energy_result_is_read_only_fixed_day_evidence():
    simulation = offline_energy_simulation()
    assert simulation.source == "provided_precomputed_offline_simulation"
    assert simulation.agent_count == 1
    assert len(simulation.profile) == 24
    assert [p.hour for p in simulation.profile] == list(range(24))
    assert len(simulation.assets) == 7
    metrics = {item.key: item for item in simulation.metrics}
    assert metrics["daily_cost"].rule == 1.87
    assert metrics["daily_cost"].matd3 == -0.02
    assert metrics["grid_import"].rule == 13.61
    assert metrics["grid_import"].matd3 == 0.76
    assert metrics["peak_import"].rule == 1.95
    assert metrics["peak_import"].matd3 == 0.37
    assert metrics["comfort_violation"].rule == metrics["comfort_violation"].matd3 == 0
    assert any("未接入 LivingMind 实时设备" in item for item in simulation.limits)


def test_energy_simulation_api_checks_space_context_and_returns_supplied_result(client):
    ok = client.get("/api/spaces/space-home-bedroom/energy/simulation", params={"accountId": "demo-account"})
    assert ok.status_code == 200
    assert ok.json()["source"] == "provided_precomputed_offline_simulation"
    denied = client.get("/api/spaces/unknown/energy/simulation", params={"accountId": "demo-account"})
    assert denied.status_code == 403
