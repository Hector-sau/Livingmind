# -*- coding: utf-8 -*-
"""
plot_environment_overview.py

家庭能源管理强化学习环境概览图。

输出：
    demo_figures/home_energy_environment_overview.png

运行：
    python plot_environment_overview.py
"""

import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch

from environment import GYMEnv


OUTPUT_DIR = os.path.abspath("demo_figures")


plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.labelsize": 10,
    "legend.fontsize": 8.5,
    "figure.dpi": 600,
    "savefig.dpi": 600,
})


def get_scalar(value, default=0.0):
    """将 numpy 标量或普通数值转换为 float。"""
    try:
        return float(np.asarray(value).reshape(-1)[0])
    except (TypeError, ValueError, IndexError):
        return float(default)


def style_axis(ax):
    """统一图表样式。"""
    ax.set_xlim(-0.5, 23.5)
    ax.set_xticks(np.arange(0, 24, 2))
    ax.set_xlabel("Hour of day")
    ax.grid(True, axis="y", alpha=0.25)
    ax.grid(True, axis="x", alpha=0.08)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def add_text_box(
    ax,
    x,
    y,
    width,
    height,
    title,
    lines,
    facecolor,
    title_color="#1D3557",
    title_fontsize=11,
    body_fontsize=8.7,
    body_linespacing=1.45,
    body_top_ratio=0.38,
):
    """
    在坐标轴坐标中绘制文字框。

    x, y, width, height 使用 0 到 1 的轴坐标。
    """
    patch = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.012",
        transform=ax.transAxes,
        facecolor=facecolor,
        edgecolor="#58728D",
        linewidth=1.4,
    )
    ax.add_patch(patch)

    ax.text(
        x + width / 2,
        y + height - 0.18 * height,
        title,
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=title_fontsize,
        fontweight="bold",
        color=title_color,
    )

    ax.text(
        x + 0.06 * width,
        y + height - body_top_ratio * height,
        "\n".join(lines),
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=body_fontsize,
        linespacing=body_linespacing,
        color="#334E68",
    )



def plot_environment_overview(show=True):
    env = GYMEnv(enable_hvac=True)
    env.reset()

    hours = np.arange(env.episode_length)

    pv_data = np.asarray(env.pv_data, dtype=float)
    wind_data = np.asarray(env.wind_data, dtype=float)
    base_load = np.asarray(env.base_load_data, dtype=float)
    outdoor_temp_data = np.asarray(env.outdoor_temp_data, dtype=float)
    buy_price = np.asarray(env.buy_price, dtype=float)

    sell_price = get_scalar(
        getattr(env, "sell_price", 0.05),
        default=0.05,
    )

    battery_capacity = get_scalar(
        getattr(env, "battery_capacity_kwh", 13.5),
        default=13.5,
    )

    soc_min = get_scalar(
        getattr(env, "soc_min", 0.10),
        default=0.10,
    )

    soc_max = get_scalar(
        getattr(env, "soc_max", 0.95),
        default=0.95,
    )

    battery_charge_limit = get_scalar(
        getattr(env, "battery_max_charge_kw", 5.0),
        default=5.0,
    )

    battery_discharge_limit = get_scalar(
        getattr(env, "battery_max_discharge_kw", 5.0),
        default=5.0,
    )

    hvac_model = getattr(env, "hvac", None)

    hvac_limit = get_scalar(
        getattr(hvac_model, "max_hvac_kw", 5.0),
        default=5.0,
    )

    comfort_deadband = get_scalar(
        getattr(hvac_model, "comfort_deadband_f", 1.5),
        default=1.5,
    )

    fig = plt.figure(figsize=(13.5, 11.5))

    grid = fig.add_gridspec(
        4,
        2,
        height_ratios=[1.0, 1.25, 1.25, 1.15],
        hspace=0.72,
        wspace=0.28,
    )

    fig.suptitle(
        "Home Energy Management Reinforcement-Learning Environment",
        fontsize=18,
        fontweight="bold",
        y=0.985,
    )

    # --------------------------------------------------------
    # (a) 能源系统组成
    # --------------------------------------------------------
    ax_system = fig.add_subplot(grid[0, :])
    ax_system.axis("off")

    ax_system.set_title(
        "(a) Environment Components",
        loc="left",
        fontsize=13,
        fontweight="bold",
        pad=8,
    )

    component_boxes = [
        (
            0.02,
            "Energy supply",
            [
                "PV generation",
                "Wind generation",
                "Grid purchase / export",
            ],
            "#FFF1B8",
        ),
        (
            0.265,
            "Energy demand",
            [
                "Base household load",
                "HVAC electrical demand",
            ],
            "#DDEBF7",
        ),
        (
            0.51,
            "Flexible devices",
            [
                "Battery SOC",
                "Charge / discharge power",
                "Diesel generator",
            ],
            "#D9EAD3",
        ),
        (
            0.755,
            "Operating objective",
            [
                "Reduce energy cost",
                "Maintain comfort",
                "Respect device limits",
            ],
            "#FCE4D6",
        ),
    ]

    for x, title, lines, color in component_boxes:
        add_text_box(
            ax_system,
            x,
            0.12,
            0.22,
            0.65,
            title,
            lines,
            color,
        )

    ax_system.text(
        0.50,
        0.90,
        "The environment converts weather, demand, price, and device states into hourly control decisions.",
        transform=ax_system.transAxes,
        ha="center",
        va="center",
        fontsize=9.2,
        color="#334E68",
    )

    # --------------------------------------------------------
    # (b) 供给与负荷曲线
    # --------------------------------------------------------
    ax_power = fig.add_subplot(grid[1, 0])

    ax_power.plot(
        hours,
        pv_data,
        color="#F77F00",
        linewidth=2.3,
        label="PV generation",
    )

    ax_power.plot(
        hours,
        wind_data,
        color="#2A9D8F",
        linewidth=2.1,
        label="Wind generation",
    )

    ax_power.plot(
        hours,
        base_load,
        color="#495057",
        linewidth=2.1,
        linestyle="--",
        label="Base load",
    )

    ax_power.set_title(
        "(b) Energy Supply and Demand",
        fontweight="bold",
    )
    ax_power.set_ylabel("Power (kW)")
    style_axis(ax_power)
    ax_power.legend(loc="upper left", frameon=True)

    # --------------------------------------------------------
    # (c) 电价
    # --------------------------------------------------------
    ax_price = fig.add_subplot(grid[1, 1])

    ax_price.step(
        hours,
        buy_price,
        where="mid",
        color="#6C5CE7",
        linewidth=2.5,
        label="Purchase price",
    )

    ax_price.axhline(
        sell_price,
        color="#3D9970",
        linestyle="--",
        linewidth=1.8,
        label="Export price",
    )

    peak_start = 17
    peak_end = 20

    ax_price.axvspan(
        peak_start - 0.5,
        peak_end - 0.5,
        color="#F4A261",
        alpha=0.16,
        label="Peak-price period",
    )

    ax_price.set_title(
        "(c) Time-of-Use Electricity Price",
        fontweight="bold",
    )
    ax_price.set_ylabel("Price ($/kWh)")
    style_axis(ax_price)
    ax_price.legend(loc="upper left", frameon=True)

    # --------------------------------------------------------
    # (d) 室外温度
    # --------------------------------------------------------
    ax_temperature = fig.add_subplot(grid[2, 0])

    ax_temperature.plot(
        hours,
        outdoor_temp_data,
        color="#E63946",
        linewidth=2.4,
        marker="o",
        markersize=3.3,
        label="Outdoor temperature",
    )

    ax_temperature.set_title(
        "(d) Outdoor Thermal Condition",
        fontweight="bold",
    )
    ax_temperature.set_ylabel("Temperature (F)")
    style_axis(ax_temperature)
    ax_temperature.legend(loc="upper left", frameon=True)

    # --------------------------------------------------------
    # (e) 强化学习状态、动作、奖励
    # --------------------------------------------------------
    ax_rl = fig.add_subplot(grid[2:, 1])
    ax_rl.axis("off")

    ax_rl.set_title(
        "(e) Reinforcement-Learning Interface",
        loc="left",
        fontsize=13,
        fontweight="bold",
        pad=8,
    )

    add_text_box(
        ax_rl,
        0.04,
        0.57,
        0.92,
        0.30,
        "State: what the agent observes",
        [
            "PV, wind, base load",
            "Outdoor and indoor temperature",
            "Battery SOC and hour of day",
        ],
        "#DDEBF7",
    )

    add_text_box(
        ax_rl,
        0.04,
        0.23,
        0.92,
        0.25,
        "Action: what the agent controls",
        [
            "Battery dispatch",
            "Diesel generator command",
            "HVAC setpoint offset",
        ],
        "#D9EAD3",
    )

    add_text_box(
        ax_rl,
        0.04,
        0.02,
        0.92,
        0.14,
        "Reward: how performance is evaluated",
        [
            "Lower cost and lower comfort violation produce higher reward.",
        ],
        "#FCE4D6",
    )

    # --------------------------------------------------------
    # (f) 约束
    # --------------------------------------------------------
    ax_constraints = fig.add_subplot(grid[3, 0])
    ax_constraints.axis("off")

    ax_constraints.set_title(
        "(f) Current Demo Constraints",
        loc="left",
        fontsize=13,
        fontweight="bold",
        pad=8,
    )

    constraint_lines = [
        "Episode: 24 hourly decisions",
        "Battery capacity: {:.1f} kWh".format(battery_capacity),
        "SOC range: {:.0f}% to {:.0f}%".format(
            soc_min * 100.0,
            soc_max * 100.0,
        ),
        "Battery charge limit: {:.1f} kW".format(
            battery_charge_limit,
        ),
        "Battery discharge limit: {:.1f} kW".format(
            battery_discharge_limit,
        ),
        "HVAC power limit: {:.1f} kW".format(hvac_limit),
        "Comfort deadband: +/- {:.1f} F".format(
            comfort_deadband,
        ),
    ]

    add_text_box(
        ax_constraints,
        0.03,
        0.02,
        0.94,
        0.90,
        "Fixed-profile demonstration parameters",
        constraint_lines,
        "#F8F9FA",
        title_fontsize=9.4,
        body_fontsize=7.2,
        body_linespacing=1.20,
        body_top_ratio=0.34,
    )

    fig.text(
        0.50,
        0.012,
        "Current version uses fixed daily profiles. User-specific constraints can be added through a validated configuration layer.",
        ha="center",
        fontsize=8.5,
        color="#495057",
    )

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    output_path = os.path.join(
        OUTPUT_DIR,
        "home_energy_environment_overview.png",
    )

    fig.savefig(
        output_path,
        dpi=600,
        bbox_inches="tight",
        facecolor="white",
    )

    print("Figure saved to:")
    print(output_path)

    if show:
        try:
            plt.show(block=True)
        except TypeError:
            plt.show()

    plt.close(fig)


if __name__ == "__main__":
    plot_environment_overview(show=True)
