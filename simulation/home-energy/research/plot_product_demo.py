# -*- coding: utf-8 -*-
"""
plot_product_demo.py

家庭能源管理 MATD3 产品 Demo 可视化。

输出文件：
1. home_energy_product_demo.png
   单日 MATD3 能源管理策略图（论文 Fig.6 风格）：
   (a) BESS operation
   (b) HVAC operation
   (c) Grid energy trading

2. rule_vs_agent_summary.png
   MATD3 与 Rule-based 策略的核心 KPI 对比图。

依赖：
    pip install numpy matplotlib torch gym

要求：
    environment.py, train.py, matd3.py 与本文件位于同一路径；
    已通过 train.py 完成训练，并保存 actor 模型。
"""

import random
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch
from matplotlib.patches import Patch

from environment import GYMEnv
from train import Arguments, get_device
from matd3 import MATD3


# ============================================================
# 1. 全局显示配置
# ============================================================

OUTPUT_DIR = "demo_figures"
MODEL_ENV_NAME = "HomeEnergy"
ALGORITHM_NAME = "MATD3"
ACTION_DIM = 3
RESEARCH_DIR = Path(__file__).resolve().parent
MODEL_PATH = RESEARCH_DIR.parent / "artifacts" / "model" / "MATD3_actor_number_3_epiosde_3000_agent_0.pth"

# 为保证不同电脑上的图片风格基本统一。
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.titlesize": 14,
    "axes.labelsize": 12,
    "legend.fontsize": 10,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.dpi": 120,
    "savefig.dpi": 300,
})

COLORS = {
    "agent": "#D62728",          # 红色：MATD3
    "rule": "#1F77B4",           # 蓝色：Rule baseline
    "charge": "#35A79C",         # 青绿色：电池充电
    "discharge": "#D65A5A",      # 红色：电池放电
    "soc": "#314E9E",            # 深蓝：SOC
    "grid_import": "#E07A5F",    # 橙红：购电
    "grid_export": "#3D9970",    # 绿色：售电
    "price": "#6C5CE7",          # 紫色：电价
    "hvac": "#2A9D8F",           # 蓝绿：HVAC
    "indoor": "#D62728",         # 红色：室内温度
    "outdoor": "#F77F00",        # 橙色：室外温度
    "setpoint": "#6A4C93",       # 紫色：设定温度
    "comfort": "#90BE6D",        # 绿色：舒适区
    "base_load": "#555555",
}


# ============================================================
# 2. 策略与模型加载
# ============================================================

def rule_based_policy(env):
    """用于展示对比的确定性规则控制策略。"""
    hour = env.t
    soc = env.soc
    price = float(env.buy_price[hour])
    pv_kw = float(env.pv_data[hour])
    indoor_temp_f = float(env.hvac.indoor_temp_f)
    outdoor_temp_f = float(env.outdoor_temp_data[hour])

    # 电池：中午利用光伏充电，晚高峰放电。
    battery_action = 0.0
    if pv_kw >= 2.0 and soc < 0.90:
        battery_action = 0.80
    elif price >= 0.35 and soc > 0.20:
        battery_action = -0.85

    # 家庭产品 Demo 中默认柴油机不使用。
    diesel_action = -1.0

    # HVAC：晚高峰提高设定温度以降低制冷负荷。
    hvac_action = 0.0
    if 15 <= hour <= 20:
        hvac_action = 0.75
    elif outdoor_temp_f > 85.0 and indoor_temp_f > 75.0:
        hvac_action = -0.25

    return np.array(
        [battery_action, diesel_action, hvac_action],
        dtype=np.float32,
    )


def load_trained_agent(args, device):
    """加载 main.py 训练并保存的 MATD3 actor 网络。"""
    agent = MATD3(args, agent_id=0, device=device)

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "\n找不到随 LivingMind 研究快照提供的模型：\n{}\n\n"
            "请确认 artifacts/model/ 中的给定权重没有被移动。\n"
            "本脚本仅用于读取既有结果，不会重新训练或改写模型。".format(MODEL_PATH)
        )

    agent.load_model(
        MODEL_ENV_NAME,
        ALGORITHM_NAME,
        ACTION_DIM,
        args.max_episodes,
        0,
        model_path=MODEL_PATH,
    )
    agent.actor.eval()
    return agent


def agent_policy(agent, observation):
    """评估阶段：不加入探索噪声。"""
    with torch.no_grad():
        action = agent.choose_action(observation, noise_std=0.0)
    return np.asarray(action, dtype=np.float32).reshape(-1)


# ============================================================
# 3. 运行单日策略，并补齐适合画图的记录量
# ============================================================

def run_episode(policy_name, agent=None):
    """
    运行一个完整的 24 小时 episode。

    policy_name: "agent" 或 "rule"
    返回：history, total_reward, env
    """
    env = GYMEnv(enable_hvac=True)
    obs_n = env.reset()

    initial_soc = float(env.soc)
    actions = np.zeros((env.episode_length, 3), dtype=np.float32)
    total_reward = 0.0

    for step in range(env.episode_length):
        if policy_name == "agent":
            action = agent_policy(agent, obs_n[0])
        elif policy_name == "rule":
            action = rule_based_policy(env)
        else:
            raise ValueError("policy_name 只能是 'agent' 或 'rule'.")

        actions[step] = action
        obs_n, reward_n, done_n, _ = env.step([action])
        total_reward += float(reward_n[0])

        if bool(done_n[0]):
            break

    # history 的 ndarray 已经是独立数组；copy 保证后续处理不会影响 env。
    history = {key: np.array(value, copy=True) for key, value in env.history.items()}
    history["battery_action"] = actions[:, 0]
    history["diesel_action"] = actions[:, 1]
    history["hvac_action"] = actions[:, 2]
    history["initial_soc"] = initial_soc

    # SOC 记录在动作执行后。补初始 SOC 后，得到 t=0...24 的 25 个节点。
    history["soc_curve"] = np.concatenate(
        ([initial_soc], history["soc"])
    )

    # 环境中 HVAC action [-1, 1] 对应 setpoint offset [-2F, 2F]。
    history["setpoint_offset_f"] = 2.0 * history["hvac_action"]

    return history, total_reward, env


# ============================================================
# 4. 指标计算
# ============================================================

def calculate_metrics(history, total_reward, dt_hours=1.0):
    """计算展示用 KPI。"""
    grid_kw = history["grid_kw"]
    battery_kw = history["battery_kw"]
    hvac_kw = history["hvac_kw"]
    price = history.get("buy_price", None)

    # 本环境 dt=1 h；仍保留 dt 以便以后改为 15 min 等分辨率。
    grid_import = np.maximum(grid_kw, 0.0)
    grid_export = np.maximum(-grid_kw, 0.0)

    electricity_cost = 0.0
    for hour, value in enumerate(grid_kw):
        if value >= 0.0:
            electricity_cost += value * 0.0  # 占位；以下由环境价格重新计算。

    # env.history 当前没有保存 buy_price，直接从时间索引取值并由外部调用时补充。
    return {
        "total_reward": float(total_reward),
        "grid_import_kwh": float(np.sum(grid_import) * dt_hours),
        "grid_export_kwh": float(np.sum(grid_export) * dt_hours),
        "hvac_energy_kwh": float(np.sum(hvac_kw) * dt_hours),
        "battery_charge_kwh": float(np.sum(np.maximum(battery_kw, 0.0)) * dt_hours),
        "battery_discharge_kwh": float(np.sum(np.maximum(-battery_kw, 0.0)) * dt_hours),
        "diesel_energy_kwh": float(np.sum(history["diesel_kw"]) * dt_hours),
        "peak_grid_import_kw": float(np.max(grid_import)),
        "max_grid_export_kw": float(np.max(grid_export)),
        "comfort_violation_fh": float(np.sum(history["comfort_violation_f"]) * dt_hours),
        "max_comfort_violation_f": float(np.max(history["comfort_violation_f"])),
        "min_indoor_temp_f": float(np.min(history["indoor_temp_f"])),
        "max_indoor_temp_f": float(np.max(history["indoor_temp_f"])),
    }


def calculate_operating_cost(env, history):
    """按环境中的奖励定义，拆分日运行成本。"""
    grid_kw = history["grid_kw"]
    diesel_kw = history["diesel_kw"]
    battery_kw = history["battery_kw"]
    violation = history["comfort_violation_f"]

    electricity_cost = 0.0
    for hour, grid in enumerate(grid_kw):
        if grid >= 0.0:
            electricity_cost += grid * float(env.buy_price[hour])
        else:
            # grid 为负，所以这会形成售电收益（负成本）。
            electricity_cost += grid * float(env.sell_price)

    diesel_cost = np.sum(
        env.diesel_fuel_a * diesel_kw ** 2
        + env.diesel_fuel_b * diesel_kw
        + env.diesel_fuel_c * (diesel_kw > 0.0)
    )
    battery_cost = np.sum(0.02 * np.abs(battery_kw))
    comfort_cost = np.sum(2.0 * violation ** 2)

    return {
        "electricity_cost": float(electricity_cost),
        "diesel_cost": float(diesel_cost),
        "battery_cost": float(battery_cost),
        "comfort_cost": float(comfort_cost),
        "total_cost": float(
            electricity_cost + diesel_cost + battery_cost + comfort_cost
        ),
    }


# ============================================================
# 5. 公共绘图工具
# ============================================================

def style_axis(ax, show_x=True):
    """统一论文/产品演示风格。"""
    ax.grid(True, axis="y", alpha=0.24, linewidth=0.8)
    ax.grid(True, axis="x", alpha=0.10, linewidth=0.6)
    ax.set_xlim(-0.5, 23.5)
    ax.set_xticks(np.arange(0, 24, 2))
    if show_x:
        ax.set_xlabel("Hour of day")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def add_peak_period_shading(ax):
    """标示当前环境定义的峰电价时段 17:00–19:59。"""
    ax.axvspan(
        16.5, 19.5,
        color="#F4A261",
        alpha=0.12,
        zorder=0,
    )
    ymin, ymax = ax.get_ylim()
    ax.text(
        18.0,
        ymax - 0.04 * (ymax - ymin),
        "Peak-price period",
        ha="center",
        va="top",
        fontsize=9,
        color="#9C4F1D",
    )


def save_figure(fig, filename):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(path, dpi=600, bbox_inches="tight", facecolor="white")
    print("Figure saved:", path)


# ============================================================
# 6. 核心产品 Demo 图：Fig.6 风格
# ============================================================

def place_legend_outside(ax, handles, labels, ncol=1):
    """
    Place a subplot legend immediately to the right of the axes.
    """
    return ax.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=(1.08, 1.0),  # 原为 1.18，向左靠近图表
        borderaxespad=0.0,
        frameon=True,
        framealpha=0.97,
        fontsize=10,                  # 原为 8.5，增大字体
        ncol=ncol,
        handlelength=2.2,
        labelspacing=0.6,
        borderpad=0.65,
    )


def plot_energy_management_demo(
    agent_history,
    agent_env,
    agent_metrics,
    agent_costs,
):
    """
    Create a Fig.6-style one-day MATD3 operating strategy figure.

    Legend boxes are placed outside the plotting area on the right,
    so they do not cover curves, bars, or comfort bands.
    """
    hours = np.arange(24)
    soc_hours = np.arange(25)

    battery_kw = agent_history["battery_kw"]
    grid_kw = agent_history["grid_kw"]
    hvac_kw = agent_history["hvac_kw"]
    indoor_temp = agent_history["indoor_temp_f"]
    outdoor_temp = agent_history["outdoor_temp_f"]
    setpoint = agent_history["setpoint_f"]
    soc_curve = agent_history["soc_curve"]
    buy_price = np.asarray(agent_env.buy_price, dtype=float)

    comfort_low = setpoint - agent_env.hvac.comfort_deadband_f
    comfort_high = setpoint + agent_env.hvac.comfort_deadband_f

    # Leave the right 32% of the figure for external legends.
    fig, axes = plt.subplots(
        3,
        1,
        figsize=(13.5, 11.5),
        sharex=True,
    )

    # 右侧保留图例区域；相比原来的 0.68，适度扩大主图宽度。
    fig.subplots_adjust(
        left=0.09,
        right=0.74,
        top=0.84,
        bottom=0.09,
        hspace=0.45,
    )

    fig.suptitle(
    "LivingMind Household Energy Simulation",
        fontsize=18,
        fontweight="bold",
        x=0.415,  # 与三个主子图的中心对齐，避免视觉右偏
        y=0.975,
    )

    kpi_line_1 = (
        "Net daily cost: ${:.2f}    |    Grid import: {:.2f} kWh"
        "    |    Grid export: {:.2f} kWh"
    ).format(
        agent_costs["total_cost"],
        agent_metrics["grid_import_kwh"],
        agent_metrics["grid_export_kwh"],
    )

    kpi_line_2 = (
        "HVAC energy: {:.2f} kWh    |    Peak import: {:.2f} kW"
        "    |    Comfort violation: {:.2f} F*h"
    ).format(
        agent_metrics["hvac_energy_kwh"],
        agent_metrics["peak_grid_import_kw"],
        agent_metrics["comfort_violation_fh"],
    )

    fig.text(
        0.415,
        0.925,
        kpi_line_1 + "\n" + kpi_line_2,
        ha="center",
        va="center",
        fontsize=10,
        color="#243447",
        linespacing=1.6,
        bbox={
            "boxstyle": "round,pad=0.55",
            "facecolor": "#F4F8FB",
            "edgecolor": "#B8D2E1",
        },
    )

    # --------------------------------------------------------
    # (a) BESS operation
    # --------------------------------------------------------
    ax = axes[0]

    charge_kw = np.maximum(battery_kw, 0.0)
    discharge_kw = np.minimum(battery_kw, 0.0)

    charge_bar = ax.bar(
        hours,
        charge_kw,
        width=0.72,
        color="#35A79C",
        alpha=0.90,
        label="Charging power (+)",
        zorder=3,
    )

    discharge_bar = ax.bar(
        hours,
        discharge_kw,
        width=0.72,
        color="#D65A5A",
        alpha=0.90,
        label="Discharging power (-)",
        zorder=3,
    )

    ax.axhline(0.0, color="#333333", linewidth=0.9)
    ax.set_ylabel("Battery power (kW)")
    ax.set_title(
        "(a) Battery Energy Storage System Operation",
        loc="left",
        fontsize=13,
        fontweight="bold",
    )
    style_axis(ax, show_x=False)
    add_peak_period_shading(ax)

    ax_soc = ax.twinx()

    soc_line = ax_soc.step(
        soc_hours,
        soc_curve,
        where="post",
        color="#314E9E",
        linewidth=2.4,
        label="Battery SOC",
        zorder=4,
    )[0]

    soc_limit = ax_soc.axhline(
        agent_env.soc_min,
        color="#777777",
        linestyle=":",
        linewidth=1.3,
        label="SOC limits",
    )

    ax_soc.axhline(
        agent_env.soc_max,
        color="#777777",
        linestyle=":",
        linewidth=1.3,
    )

    ax_soc.fill_between(
        [0, 24],
        agent_env.soc_min,
        agent_env.soc_max,
        color="#8ECAE6",
        alpha=0.08,
    )

    ax_soc.set_ylabel("State of charge", color="#314E9E")
    ax_soc.tick_params(axis="y", colors="#314E9E")
    ax_soc.set_ylim(0.0, 1.05)
    ax_soc.set_xlim(-0.5, 23.5)

    place_legend_outside(
        ax,
        [
            charge_bar,
            discharge_bar,
            soc_line,
            soc_limit,
        ],
        [
            "Charging power (+)",
            "Discharging power (-)",
            "Battery SOC",
            "SOC limits",
        ],
    )

    # --------------------------------------------------------
    # (b) HVAC management
    # --------------------------------------------------------
    ax = axes[1]

    hvac_bar = ax.bar(
        hours,
        hvac_kw,
        width=0.68,
        color="#2A9D8F",
        alpha=0.82,
        label="HVAC electrical power",
        zorder=3,
    )

    ax.set_ylabel("HVAC power (kW)")
    ax.set_title(
        "(b) HVAC Thermal Comfort Management",
        loc="left",
        fontsize=13,
        fontweight="bold",
    )
    style_axis(ax, show_x=False)
    add_peak_period_shading(ax)

    ax_temp = ax.twinx()

    comfort_band = ax_temp.fill_between(
        hours,
        comfort_low,
        comfort_high,
        color="#90BE6D",
        alpha=0.18,
        label="Comfort band",
        zorder=1,
    )

    outdoor_line = ax_temp.plot(
        hours,
        outdoor_temp,
        color="#F77F00",
        linewidth=2.1,
        label="Outdoor temperature",
        zorder=4,
    )[0]

    indoor_line = ax_temp.plot(
        hours,
        indoor_temp,
        color="#D62728",
        linewidth=2.5,
        marker="o",
        markersize=3.5,
        label="Indoor temperature",
        zorder=5,
    )[0]

    setpoint_line = ax_temp.step(
        hours,
        setpoint,
        where="mid",
        color="#6A4C93",
        linewidth=2.0,
        linestyle="--",
        label="Agent setpoint",
        zorder=5,
    )[0]

    ax_temp.set_ylabel("Temperature (F)")
    ax_temp.set_xlim(-0.5, 23.5)

    place_legend_outside(
        ax,
        [
            hvac_bar,
            comfort_band,
            outdoor_line,
            indoor_line,
            setpoint_line,
        ],
        [
            "HVAC electrical power",
            "Comfort band",
            "Outdoor temperature",
            "Indoor temperature",
            "Agent setpoint",
        ],
    )

    # --------------------------------------------------------
    # (c) Grid trading
    # --------------------------------------------------------
    ax = axes[2]

    grid_import_kw = np.maximum(grid_kw, 0.0)
    grid_export_kw = np.minimum(grid_kw, 0.0)

    import_bar = ax.bar(
        hours,
        grid_import_kw,
        width=0.70,
        color="#E07A5F",
        alpha=0.88,
        label="Grid import (purchase)",
        zorder=3,
    )

    export_bar = ax.bar(
        hours,
        grid_export_kw,
        width=0.70,
        color="#3D9970",
        alpha=0.88,
        label="Grid export (sell)",
        zorder=3,
    )

    ax.axhline(0.0, color="#333333", linewidth=0.9)
    ax.set_ylabel("Grid power (kW)")
    ax.set_title(
        "(c) Energy Trading with the Grid",
        loc="left",
        fontsize=13,
        fontweight="bold",
    )
    style_axis(ax, show_x=True)
    add_peak_period_shading(ax)

    ax_price = ax.twinx()

    price_line = ax_price.step(
        hours,
        buy_price,
        where="mid",
        color="#6C5CE7",
        linewidth=2.3,
        label="Retail electricity price",
        zorder=4,
    )[0]

    ax_price.set_ylabel("Price ($/kWh)", color="#6C5CE7")
    ax_price.tick_params(axis="y", colors="#6C5CE7")
    ax_price.set_ylim(0.0, max(buy_price) * 1.25)
    ax_price.set_xlim(-0.5, 23.5)

    place_legend_outside(
        ax,
        [
            import_bar,
            export_bar,
            price_line,
        ],
        [
            "Grid import (purchase)",
            "Grid export (sell)",
            "Retail electricity price",
        ],
    )

    fig.text(
        0.415,
        0.025,
        "Positive battery power = charging; negative battery power = discharging. "
        "Positive grid power = purchase; negative grid power = export. "
        "Orange shading marks the peak-price period.",
        ha="center",
        fontsize=8.8,
        color="#444444",
    )

    save_figure(fig, "home_energy_product_demo.png")
    plt.show()
    plt.close(fig)


def plot_rule_vs_agent_summary(
    rule_history,
    agent_history,
    rule_metrics,
    agent_metrics,
    rule_costs,
    agent_costs,
):
    """
    Create a compact and readable benchmark summary.

    A single shared legend is placed at the top of the figure.
    """
    hours = np.arange(24)

    fig, axes = plt.subplots(
        2,
        2,
        figsize=(13.5, 8.5),
    )

    fig.subplots_adjust(
        left=0.08,
        right=0.98,
        top=0.82,
        bottom=0.10,
        hspace=0.42,
        wspace=0.25,
    )

    fig.suptitle(
        "LivingMind MATD3 versus Rule-Based Controller",
        fontsize=17,
        fontweight="bold",
        y=0.975,
    )

    shared_handles = [
        Patch(facecolor="#1F77B4", label="Rule-based controller"),
        Patch(facecolor="#D62728", label="LivingMind MATD3 controller"),
    ]

    fig.legend(
        handles=shared_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.915),
        ncol=2,
        frameon=True,
        fontsize=10,
    )

    # --------------------------------------------------------
    # (a) Daily cost breakdown
    # --------------------------------------------------------
    ax = axes[0, 0]

    categories = ["Electricity", "Battery", "Comfort", "Total"]
    rule_cost_values = np.array([
        rule_costs["electricity_cost"],
        rule_costs["battery_cost"],
        rule_costs["comfort_cost"],
        rule_costs["total_cost"],
    ])

    agent_cost_values = np.array([
        agent_costs["electricity_cost"],
        agent_costs["battery_cost"],
        agent_costs["comfort_cost"],
        agent_costs["total_cost"],
    ])

    x = np.arange(len(categories))
    width = 0.34

    rule_bars = ax.bar(
        x - width / 2,
        rule_cost_values,
        width,
        color="#1F77B4",
        alpha=0.78,
        label="Rule-based",
    )

    agent_bars = ax.bar(
        x + width / 2,
        agent_cost_values,
        width,
        color="#D62728",
        alpha=0.82,
        label="MATD3",
    )

    ax.axhline(0.0, color="#333333", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.set_ylabel("Daily cost ($)")
    ax.set_title(
        "(a) Daily Cost Breakdown",
        fontsize=13,
        fontweight="bold",
    )
    ax.grid(True, axis="y", alpha=0.25)

    # 支持负的净成本，并为数值标签留出空间。
    all_cost_values = np.concatenate(
        (rule_cost_values, agent_cost_values)
    )
    min_cost = float(np.min(all_cost_values))
    max_cost = float(np.max(all_cost_values))
    cost_range = max(max_cost - min_cost, 1.0)

    ax.set_ylim(
        min_cost - 0.15 * cost_range,
        max_cost + 0.18 * cost_range,
    )

    # 每根柱子标注实际金额。
    # Comfort 项如果两个策略均为 0，只在中央显示一次提示，避免文字重叠。
    for bars, values in (
        (rule_bars, rule_cost_values),
        (agent_bars, agent_cost_values),
    ):
        for category, bar, value in zip(categories, bars, values):
            # Comfort=0 的文字单独统一处理，此处跳过。
            if category == "Comfort" and abs(value) < 1e-6:
                continue

            label = "${:.2f}".format(value)

            if value >= 0.0:
                y_position = value + 0.025 * cost_range
                vertical_alignment = "bottom"
            else:
                y_position = value - 0.025 * cost_range
                vertical_alignment = "top"

            ax.text(
                bar.get_x() + bar.get_width() / 2,
                y_position,
                label,
                ha="center",
                va=vertical_alignment,
                fontsize=7.5,
            )

    # Comfort 分项只有在两个控制器均无舒适度违规时，才显示一次。
    if (
        abs(rule_cost_values[2]) < 1e-6
        and abs(agent_cost_values[2]) < 1e-6
    ):
        ax.text(
            x[2],
            0.06 * cost_range,
            "No comfort violation",
            ha="center",
            va="bottom",
            fontsize=7.2,
            color="#2A9D8F",
            fontweight="bold",
        )

    # --------------------------------------------------------
    # (b) Peak shaving
    # --------------------------------------------------------
    ax = axes[0, 1]

    ax.plot(
        hours,
        np.maximum(rule_history["grid_kw"], 0.0),
        color="#1F77B4",
        linestyle="--",
        linewidth=2.3,
    )

    ax.plot(
        hours,
        np.maximum(agent_history["grid_kw"], 0.0),
        color="#D62728",
        linewidth=2.5,
    )

    ax.fill_between(
        hours,
        0.0,
        np.maximum(agent_history["grid_kw"], 0.0),
        color="#D62728",
        alpha=0.10,
    )

    ax.axvspan(16.5, 19.5, color="#F4A261", alpha=0.13)
    ax.set_ylabel("Imported power (kW)")
    ax.set_title(
        "(b) Grid Import and Peak Shaving",
        fontsize=13,
        fontweight="bold",
    )
    style_axis(ax, show_x=True)

    # --------------------------------------------------------
    # (c) SOC scheduling
    # --------------------------------------------------------
    ax = axes[1, 0]
    soc_hours = np.arange(25)

    ax.step(
        soc_hours,
        rule_history["soc_curve"],
        where="post",
        color="#1F77B4",
        linestyle="--",
        linewidth=2.3,
        label="Rule-based SOC",
    )

    ax.step(
        soc_hours,
        agent_history["soc_curve"],
        where="post",
        color="#D62728",
        linewidth=2.5,
        label="LivingMind MATD3 SOC",
    )

    ax.axhline(
        0.10,
        color="#555555",
        linestyle=":",
        linewidth=1.2,
    )

    ax.axhline(
        0.95,
        color="#555555",
        linestyle=":",
        linewidth=1.2,
        label="SOC limits",
    )

    ax.fill_between(
        [0, 24],
        0.10,
        0.95,
        color="#8ECAE6",
        alpha=0.10,
    )

    ax.set_xlim(0, 24)
    ax.set_ylim(0.0, 1.05)
    ax.set_xticks(np.arange(0, 25, 2))
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("SOC")
    ax.set_title(
        "(c) Battery Scheduling",
        fontsize=13,
        fontweight="bold",
    )
    ax.grid(True, alpha=0.25)

    # 图例由左下角改到图内左上角。
    ax.legend(
        loc="upper left",
        fontsize=8.5,
        frameon=True,
        framealpha=0.90,
    )

    # --------------------------------------------------------
    # (d) MATD3 performance comparison
    # --------------------------------------------------------
    ax = axes[1, 1]

    metric_names = [
        "Daily cost\n($)",
        "Grid import\n(kWh)",
        "Peak import\n(kW)",
        "Comfort violation\n(F*h)",
    ]

    rule_metric_values = np.array([
        rule_costs["total_cost"],
        rule_metrics["grid_import_kwh"],
        rule_metrics["peak_grid_import_kw"],
        rule_metrics["comfort_violation_fh"],
    ])

    agent_metric_values = np.array([
        agent_costs["total_cost"],
        agent_metrics["grid_import_kwh"],
        agent_metrics["peak_grid_import_kw"],
        agent_metrics["comfort_violation_fh"],
    ])

    x = np.arange(len(metric_names))
    width = 0.34

    rule_bars = ax.bar(
        x - width / 2,
        rule_metric_values,
        width,
        color="#1F77B4",
        alpha=0.76,
        label="Rule-based controller",
        zorder=3,
    )

    agent_bars = ax.bar(
        x + width / 2,
        agent_metric_values,
        width,
        color="#D62728",
        alpha=0.85,
        label="MATD3 controller",
        zorder=3,
    )

    ax.axhline(0.0, color="#333333", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(metric_names)
    ax.set_ylabel("Metric value")
    ax.set_title(
        "(d) LivingMind MATD3 Performance vs Rule-Based Control",
        fontsize=13,
        fontweight="bold",
    )
    ax.grid(True, axis="y", alpha=0.25, zorder=0)

    ax.legend(
        loc="upper right",
        fontsize=8,
        frameon=True,
    )

    # 支持负的净成本，并为柱顶文字及改善量文字预留空间。
    all_metric_values = np.concatenate(
        (rule_metric_values, agent_metric_values)
    )
    min_value = float(np.min(all_metric_values))
    max_value = float(np.max(all_metric_values))
    value_range = max(max_value - min_value, 1.0)

    ax.set_ylim(
        min_value - 0.12 * value_range,
        max_value + 0.35 * value_range,
    )

    # 标注两种策略的绝对指标值。
    for bar in list(rule_bars) + list(agent_bars):
        height = bar.get_height()

        if height >= 0.0:
            y_position = height + 0.025 * value_range
            vertical_alignment = "bottom"
        else:
            y_position = height - 0.025 * value_range
            vertical_alignment = "top"

        ax.text(
            bar.get_x() + bar.get_width() / 2,
            y_position,
            "{:.2f}".format(height),
            ha="center",
            va=vertical_alignment,
            fontsize=7.8,
        )

    # Rule-based - MATD3；正值代表 MATD3 更低、更优。
    differences = rule_metric_values - agent_metric_values

    comparison_labels = [
        (
            "${:.2f}/day lower".format(abs(differences[0]))
            if differences[0] > 1e-6
            else "${:.2f}/day higher".format(abs(differences[0]))
            if differences[0] < -1e-6
            else "No change"
        ),
        (
            "{:.2f} kWh/day lower".format(abs(differences[1]))
            if differences[1] > 1e-6
            else "{:.2f} kWh/day higher".format(abs(differences[1]))
            if differences[1] < -1e-6
            else "No change"
        ),
        (
            "{:.2f} kW lower".format(abs(differences[2]))
            if differences[2] > 1e-6
            else "{:.2f} kW higher".format(abs(differences[2]))
            if differences[2] < -1e-6
            else "No change"
        ),
        (
            "{:.2f} F*h lower".format(abs(differences[3]))
            if differences[3] > 1e-6
            else "{:.2f} F*h higher".format(abs(differences[3]))
            if differences[3] < -1e-6
            else "No change"
        ),
    ]

    for index, label in enumerate(comparison_labels):
        top_value = max(
            rule_metric_values[index],
            agent_metric_values[index],
        )

        ax.text(
            x[index],
            top_value + 0.12 * value_range,
            label,
            ha="center",
            va="bottom",
            fontsize=7.5,
            fontweight="bold",
            color=(
                "#2A9D8F"
                if differences[index] > 1e-6
                else "#D65A5A"
                if differences[index] < -1e-6
                else "#555555"
            ),
        )

    save_figure(fig, "rule_vs_agent_summary.png")
    plt.show()
    plt.close(fig)



# ============================================================
# 8. 控制台结果
# ============================================================

def print_report(name, metrics, costs):
    print("\n" + "=" * 72)
    print(name)
    print("=" * 72)
    print("Total reward:              {:9.3f}".format(metrics["total_reward"]))
    print("Daily operating cost:       ${:8.3f}".format(costs["total_cost"]))
    print("  Electricity cost:         ${:8.3f}".format(costs["electricity_cost"]))
    print("  Battery degradation cost: ${:8.3f}".format(costs["battery_cost"]))
    print("  Comfort penalty:          ${:8.3f}".format(costs["comfort_cost"]))
    print("Grid import:                {:8.3f} kWh".format(metrics["grid_import_kwh"]))
    print("Grid export:                {:8.3f} kWh".format(metrics["grid_export_kwh"]))
    print("Peak grid import:           {:8.3f} kW".format(metrics["peak_grid_import_kw"]))
    print("HVAC electricity use:       {:8.3f} kWh".format(metrics["hvac_energy_kwh"]))
    print("Battery charge/discharge:   {:8.3f} / {:8.3f} kWh".format(
        metrics["battery_charge_kwh"], metrics["battery_discharge_kwh"]
    ))
    print("Comfort violation:          {:8.3f} °F·h".format(metrics["comfort_violation_fh"]))
    print("Indoor temperature range:   {:8.2f} – {:8.2f} °F".format(
        metrics["min_indoor_temp_f"], metrics["max_indoor_temp_f"]
    ))


# ============================================================
# 9. 主函数
# ============================================================

def main():
    # 固定随机种子仅用于保证涉及 torch 的推理可复现。
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)

    args = Arguments()
    device = get_device()

    # 必须与训练时的网络输入/输出维度一致。
    args.N = 1
    args.obs_dim_total = 7
    args.obs_dim_n = [7]
    args.action_dim_n = [3]
    args.max_action = 1.0

    print("Using device:", device)
    print("Loading trained MATD3 actor ...")
    agent = load_trained_agent(args, device)

    print("Running MATD3 one-day evaluation ...")
    agent_history, agent_reward, agent_env = run_episode("agent", agent=agent)

    print("Running rule-based baseline ...")
    rule_history, rule_reward, rule_env = run_episode("rule")

    agent_metrics = calculate_metrics(agent_history, agent_reward, agent_env.dt_hours)
    rule_metrics = calculate_metrics(rule_history, rule_reward, rule_env.dt_hours)
    agent_costs = calculate_operating_cost(agent_env, agent_history)
    rule_costs = calculate_operating_cost(rule_env, rule_history)

    print_report("MATD3 Agent", agent_metrics, agent_costs)
    print_report("Rule-Based Baseline", rule_metrics, rule_costs)

    print("\n" + "=" * 72)
    print("MATD3 relative to Rule-Based Baseline")
    print("=" * 72)
    print("Operating cost difference:  ${:+.3f}".format(
        agent_costs["total_cost"] - rule_costs["total_cost"]
    ))
    print("Grid import difference:     {:+.3f} kWh".format(
        agent_metrics["grid_import_kwh"] - rule_metrics["grid_import_kwh"]
    ))
    print("Peak import difference:     {:+.3f} kW".format(
        agent_metrics["peak_grid_import_kw"] - rule_metrics["peak_grid_import_kw"]
    ))
    print("Comfort violation difference:{:+.3f} °F·h".format(
        agent_metrics["comfort_violation_fh"] - rule_metrics["comfort_violation_fh"]
    ))

    # 核心产品展示图：只展示 MATD3 的一天运行策略。
    plot_energy_management_demo(
        agent_history,
        agent_env,
        agent_metrics,
        agent_costs,
    )

    # 解释性补充图：与规则策略作比较。
    plot_rule_vs_agent_summary(
        rule_history,
        agent_history,
        rule_metrics,
        agent_metrics,
        rule_costs,
        agent_costs,
    )

    print("\nAll figures are saved in:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
