import gym
import numpy as np
from gym import spaces


class HVACModel:
    """
    2R1C household HVAC thermal model.

    T_in(t+1) = T_in(t) + dt / C * (Q_hvac - (T_in - T_out) / R)

    Temperature unit: Fahrenheit
    Thermal power unit: kBtu/h
    Electrical power unit: kW
    """

    KW_TO_KBTU_H = 3.412

    def __init__(
        self,
        thermal_resistance_r=2.5,
        thermal_capacitance_c=8.0,
        cop_cooling=3.5,
        cop_heating=4.0,
        max_hvac_kw=5.0,
        comfort_deadband_f=1.5,
        setpoint_delta_min=-2.0,
        setpoint_delta_max=2.0,
        initial_temp_f=75.0,
    ):
        self.thermal_resistance_r = thermal_resistance_r
        self.thermal_capacitance_c = thermal_capacitance_c
        self.cop_cooling = cop_cooling
        self.cop_heating = cop_heating
        self.max_hvac_kw = max_hvac_kw
        self.comfort_deadband_f = comfort_deadband_f
        self.setpoint_delta_min = setpoint_delta_min
        self.setpoint_delta_max = setpoint_delta_max
        self.indoor_temp_f = initial_temp_f

        self.setpoint_schedule = {
            **{hour: 76.0 for hour in range(0, 7)},
            **{hour: 74.0 for hour in range(7, 19)},
            **{hour: 76.0 for hour in range(19, 24)},
        }

    def reset(self, initial_temp_f=75.0):
        self.indoor_temp_f = float(initial_temp_f)

    def step(self, setpoint_delta_f, outdoor_temp_f, current_hour, dt_hours=1.0):
        """
        Returns:
            hvac_kw: HVAC electrical consumption in kW
            indoor_temp_f: Updated indoor temperature
            comfort_violation: Temperature violation outside deadband
            effective_setpoint: Actual control setpoint
        """
        scheduled_setpoint = self.setpoint_schedule[current_hour]

        setpoint_delta_f = np.clip(
            setpoint_delta_f,
            self.setpoint_delta_min,
            self.setpoint_delta_max,
        )

        effective_setpoint = scheduled_setpoint + setpoint_delta_f

        envelope_loss = (
            self.indoor_temp_f - outdoor_temp_f
        ) / self.thermal_resistance_r

        temp_error = effective_setpoint - self.indoor_temp_f

        # Ideal HVAC thermal power for tracking the chosen setpoint.
        proportional_gain = self.thermal_capacitance_c / dt_hours
        q_hvac_kbtu_h = temp_error * proportional_gain + envelope_loss

        max_cooling_kbtu_h = (
            self.max_hvac_kw * self.cop_cooling * self.KW_TO_KBTU_H
        )
        max_heating_kbtu_h = (
            self.max_hvac_kw * self.cop_heating * self.KW_TO_KBTU_H
        )

        if q_hvac_kbtu_h < 0.0:
            q_hvac_kbtu_h = max(q_hvac_kbtu_h, -max_cooling_kbtu_h)
            hvac_kw = abs(q_hvac_kbtu_h) / (
                self.cop_cooling * self.KW_TO_KBTU_H
            )
        else:
            q_hvac_kbtu_h = min(q_hvac_kbtu_h, max_heating_kbtu_h)
            hvac_kw = q_hvac_kbtu_h / (
                self.cop_heating * self.KW_TO_KBTU_H
            )

        envelope_loss_actual = (
            self.indoor_temp_f - outdoor_temp_f
        ) / self.thermal_resistance_r

        d_temp = (
            dt_hours / self.thermal_capacitance_c
        ) * (q_hvac_kbtu_h - envelope_loss_actual)

        self.indoor_temp_f += d_temp

        comfort_violation = max(
            0.0,
            abs(self.indoor_temp_f - effective_setpoint)
            - self.comfort_deadband_f,
        )

        return (
            float(hvac_kw),
            float(self.indoor_temp_f),
            float(comfort_violation),
            float(effective_setpoint),
        )


class GYMEnv:
    """
    Household energy management environment.

    Action:
        action[0]: battery power in [-1, 1]
                   positive = charge, negative = discharge
        action[1]: diesel generator command in [-1, 1]
                   mapped to [0, max_diesel_kw]
        action[2]: HVAC setpoint offset in [-1, 1]
                   mapped to [-2 F, 2 F]

    Observation:
        [PV, wind, base_load, outdoor_temp, indoor_temp, SOC, hour]
        All observations are normalized.
    """

    def __init__(self, enable_hvac=True):
        self.episode_length = 24
        self.dt_hours = 1.0
        self.enable_hvac = enable_hvac

        # Battery parameters for a household battery system.
        self.battery_capacity_kwh = 13.5
        self.battery_max_charge_kw = 5.0
        self.battery_max_discharge_kw = 5.0
        self.battery_charge_efficiency = 0.95
        self.battery_discharge_efficiency = 0.95
        self.soc_min = 0.10
        self.soc_max = 0.95
        self.initial_soc = 0.50

        # Backup generator parameters.
        self.max_diesel_kw = 6.0
        self.diesel_fuel_a = 0.02
        self.diesel_fuel_b = 0.25
        self.diesel_fuel_c = 0.10

        # Electricity prices in $/kWh.
        self.buy_price = np.array([
            0.12, 0.12, 0.12, 0.12, 0.12, 0.12,
            0.15, 0.18, 0.18, 0.18, 0.18, 0.18,
            0.18, 0.18, 0.18, 0.22, 0.35, 0.45,
            0.45, 0.45, 0.35, 0.22, 0.18, 0.15,
        ], dtype=np.float32)

        self.sell_price = 0.05

        # Household renewable generation profiles in kW.
        self.pv_data = np.array([
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.2, 0.8, 1.8, 3.0, 4.2, 5.0,
            5.5, 5.2, 4.6, 3.5, 2.0, 0.8,
            0.2, 0.0, 0.0, 0.0, 0.0, 0.0,
        ], dtype=np.float32)

        # Optional small home wind turbine profile in kW.
        self.wind_data = np.array([
            0.4, 0.4, 0.3, 0.3, 0.2, 0.2,
            0.2, 0.3, 0.3, 0.4, 0.3, 0.3,
            0.4, 0.4, 0.5, 0.5, 0.4, 0.4,
            0.3, 0.3, 0.3, 0.3, 0.3, 0.3,
        ], dtype=np.float32)

        # Base household electrical load excluding HVAC in kW.
        self.base_load_data = np.array([
            0.55, 0.50, 0.45, 0.45, 0.45, 0.55,
            0.80, 1.20, 1.00, 0.85, 0.80, 0.90,
            1.00, 0.90, 0.85, 1.00, 1.40, 2.20,
            2.80, 2.50, 2.00, 1.50, 1.00, 0.70,
        ], dtype=np.float32)

        # Summer outdoor temperature profile in Fahrenheit.
        self.outdoor_temp_data = np.array([
            66.0, 65.0, 64.0, 64.0, 63.0, 64.0,
            66.0, 69.0, 73.0, 77.0, 81.0, 85.0,
            88.0, 90.0, 91.0, 90.0, 87.0, 83.0,
            79.0, 75.0, 72.0, 70.0, 68.0, 67.0,
        ], dtype=np.float32)

        # Three continuous actions:
        # battery, diesel generator, HVAC setpoint adjustment.
        self.action_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(3,),
            dtype=np.float32,
        )

        # Seven normalized observations.
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(7,),
            dtype=np.float32,
        )

        self.hvac = HVACModel()
        self.t = 0
        self.soc = self.initial_soc
        self.state = None
        self.history = {}

        self.reset()

    def reset(self):
        self.t = 0
        self.soc = self.initial_soc
        self.hvac.reset(initial_temp_f=75.0)

        self.history = {
            "hour": np.zeros(self.episode_length),
            "pv_kw": np.zeros(self.episode_length),
            "wind_kw": np.zeros(self.episode_length),
            "base_load_kw": np.zeros(self.episode_length),
            "hvac_kw": np.zeros(self.episode_length),
            "total_load_kw": np.zeros(self.episode_length),
            "battery_kw": np.zeros(self.episode_length),
            "diesel_kw": np.zeros(self.episode_length),
            "grid_kw": np.zeros(self.episode_length),
            "soc": np.zeros(self.episode_length),
            "outdoor_temp_f": np.zeros(self.episode_length),
            "indoor_temp_f": np.zeros(self.episode_length),
            "setpoint_f": np.zeros(self.episode_length),
            "comfort_violation_f": np.zeros(self.episode_length),
            "reward": np.zeros(self.episode_length),
        }

        observation = self._get_observation(hour=0)
        self.state = [observation]
        return self.state

    def step(self, action):
        action = self._parse_action(action)
        hour = self.t

        battery_action = action[0]
        diesel_action = action[1]
        hvac_action = action[2]

        battery_kw = self._apply_battery_action(battery_action)
        diesel_kw = self._get_diesel_power(diesel_action)

        outdoor_temp_f = float(self.outdoor_temp_data[hour])

        if self.enable_hvac:
            setpoint_delta_f = hvac_action * 2.0
            (
                hvac_kw,
                indoor_temp_f,
                comfort_violation,
                effective_setpoint,
            ) = self.hvac.step(
                setpoint_delta_f=setpoint_delta_f,
                outdoor_temp_f=outdoor_temp_f,
                current_hour=hour,
                dt_hours=self.dt_hours,
            )
        else:
            (
                hvac_kw,
                indoor_temp_f,
                comfort_violation,
                effective_setpoint,
            ) = self._step_without_hvac(
                outdoor_temp_f=outdoor_temp_f,
                current_hour=hour,
            )

        pv_kw = float(self.pv_data[hour])
        wind_kw = float(self.wind_data[hour])
        base_load_kw = float(self.base_load_data[hour])
        total_load_kw = base_load_kw + hvac_kw

        # Positive grid_kw: buying electricity.
        # Negative grid_kw: exporting electricity.
        grid_kw = total_load_kw + battery_kw - pv_kw - wind_kw - diesel_kw

        reward, electricity_cost, diesel_cost, battery_cost, comfort_cost = (
            self._calculate_reward(
                hour=hour,
                grid_kw=grid_kw,
                diesel_kw=diesel_kw,
                battery_kw=battery_kw,
                comfort_violation=comfort_violation,
            )
        )

        self._save_history(
            hour=hour,
            pv_kw=pv_kw,
            wind_kw=wind_kw,
            base_load_kw=base_load_kw,
            hvac_kw=hvac_kw,
            total_load_kw=total_load_kw,
            battery_kw=battery_kw,
            diesel_kw=diesel_kw,
            grid_kw=grid_kw,
            outdoor_temp_f=outdoor_temp_f,
            indoor_temp_f=indoor_temp_f,
            setpoint_f=effective_setpoint,
            comfort_violation=comfort_violation,
            reward=reward,
        )

        self.t += 1
        done = self.t >= self.episode_length

        # At the terminal state, keep hour at 23 to avoid indexing beyond data.
        next_hour = min(self.t, self.episode_length - 1)
        observation = self._get_observation(hour=next_hour)
        self.state = [observation]

        info = {
            "hour": hour,
            "grid_kw": grid_kw,
            "electricity_cost": electricity_cost,
            "diesel_cost": diesel_cost,
            "battery_cost": battery_cost,
            "comfort_cost": comfort_cost,
            "hvac_kw": hvac_kw,
            "indoor_temp_f": indoor_temp_f,
            "soc": self.soc,
        }

        return [observation], [float(reward)], [done], info

    def _parse_action(self, action):
        """
        Supports both:
            action = np.array([a1, a2, a3])
        and MATD3 multi-agent format:
            action = [np.array([a1, a2, a3])]
        """
        action = np.asarray(action, dtype=np.float32)

        if action.ndim == 2:
            action = action[0]

        action = action.reshape(-1)

        if action.size != 3:
            raise ValueError(
                "Action dimension must be 3: "
                "[battery, diesel, hvac_setpoint_delta]."
            )

        return np.clip(action, -1.0, 1.0)

    def _apply_battery_action(self, normalized_action):
        """
        Positive power means charging.
        Negative power means discharging.
        """
        desired_kw = normalized_action * self.battery_max_charge_kw

        if desired_kw >= 0.0:
            max_charge_by_soc = (
                (self.soc_max - self.soc)
                * self.battery_capacity_kwh
                / (self.battery_charge_efficiency * self.dt_hours)
            )

            battery_kw = min(
                desired_kw,
                self.battery_max_charge_kw,
                max_charge_by_soc,
            )

            self.soc += (
                self.battery_charge_efficiency
                * battery_kw
                * self.dt_hours
                / self.battery_capacity_kwh
            )
        else:
            desired_discharge_kw = abs(desired_kw)

            max_discharge_by_soc = (
                (self.soc - self.soc_min)
                * self.battery_capacity_kwh
                * self.battery_discharge_efficiency
                / self.dt_hours
            )

            discharge_kw = min(
                desired_discharge_kw,
                self.battery_max_discharge_kw,
                max_discharge_by_soc,
            )

            battery_kw = -discharge_kw

            self.soc -= (
                discharge_kw
                * self.dt_hours
                / (
                    self.battery_discharge_efficiency
                    * self.battery_capacity_kwh
                )
            )

        self.soc = float(np.clip(self.soc, self.soc_min, self.soc_max))
        return float(battery_kw)

    def _get_diesel_power(self, normalized_action):
        """
        Map normalized diesel action [-1, 1] to [0, max_diesel_kw].
        """
        diesel_kw = (normalized_action + 1.0) * 0.5 * self.max_diesel_kw
        return float(np.clip(diesel_kw, 0.0, self.max_diesel_kw))

    def _step_without_hvac(self, outdoor_temp_f, current_hour):
        """
        Natural indoor-temperature evolution for the no-HVAC comparison case.
        """
        envelope_loss = (
            self.hvac.indoor_temp_f - outdoor_temp_f
        ) / self.hvac.thermal_resistance_r

        d_temp = (
            self.dt_hours / self.hvac.thermal_capacitance_c
        ) * (-envelope_loss)

        self.hvac.indoor_temp_f += d_temp

        effective_setpoint = self.hvac.setpoint_schedule[current_hour]

        comfort_violation = max(
            0.0,
            abs(self.hvac.indoor_temp_f - effective_setpoint)
            - self.hvac.comfort_deadband_f,
        )

        return (
            0.0,
            float(self.hvac.indoor_temp_f),
            float(comfort_violation),
            float(effective_setpoint),
        )

    def _calculate_reward(
        self,
        hour,
        grid_kw,
        diesel_kw,
        battery_kw,
        comfort_violation,
    ):
        if grid_kw >= 0.0:
            electricity_cost = (
                grid_kw * self.buy_price[hour] * self.dt_hours
            )
        else:
            electricity_cost = (
                grid_kw * self.sell_price * self.dt_hours
            )

        diesel_cost = (
            self.diesel_fuel_a * diesel_kw ** 2
            + self.diesel_fuel_b * diesel_kw
            + self.diesel_fuel_c * (diesel_kw > 0.0)
        ) * self.dt_hours

        battery_cost = (
            0.02 * abs(battery_kw) * self.dt_hours
        )

        comfort_cost = (
            2.0 * comfort_violation ** 2
        )

        total_cost = (
            electricity_cost
            + diesel_cost
            + battery_cost
            + comfort_cost
        )

        reward = -total_cost

        return (
            float(reward),
            float(electricity_cost),
            float(diesel_cost),
            float(battery_cost),
            float(comfort_cost),
        )

    def _get_observation(self, hour):
        """
        Return normalized observation vector.
        """
        observation = np.array([
            self.pv_data[hour] / 6.0,
            self.wind_data[hour] / 1.0,
            self.base_load_data[hour] / 4.0,
            (self.outdoor_temp_data[hour] - 40.0) / 70.0,
            (self.hvac.indoor_temp_f - 40.0) / 70.0,
            self.soc,
            hour / 23.0,
        ], dtype=np.float32)

        return observation

    def _save_history(
        self,
        hour,
        pv_kw,
        wind_kw,
        base_load_kw,
        hvac_kw,
        total_load_kw,
        battery_kw,
        diesel_kw,
        grid_kw,
        outdoor_temp_f,
        indoor_temp_f,
        setpoint_f,
        comfort_violation,
        reward,
    ):
        self.history["hour"][hour] = hour
        self.history["pv_kw"][hour] = pv_kw
        self.history["wind_kw"][hour] = wind_kw
        self.history["base_load_kw"][hour] = base_load_kw
        self.history["hvac_kw"][hour] = hvac_kw
        self.history["total_load_kw"][hour] = total_load_kw
        self.history["battery_kw"][hour] = battery_kw
        self.history["diesel_kw"][hour] = diesel_kw
        self.history["grid_kw"][hour] = grid_kw
        self.history["soc"][hour] = self.soc
        self.history["outdoor_temp_f"][hour] = outdoor_temp_f
        self.history["indoor_temp_f"][hour] = indoor_temp_f
        self.history["setpoint_f"][hour] = setpoint_f
        self.history["comfort_violation_f"][hour] = comfort_violation
        self.history["reward"][hour] = reward

    def render(self, mode="human"):
        if mode == "human":
            print(
                "hour={}, SOC={:.3f}, indoor_temp={:.2f} F".format(
                    min(self.t, 23),
                    self.soc,
                    self.hvac.indoor_temp_f,
                )
            )
        return self.history


HomeEnergyEnv = GYMEnv
