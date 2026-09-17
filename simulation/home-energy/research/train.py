import os
import random

import matplotlib.pyplot as plt
import numpy as np
import torch

from environment import GYMEnv
from matd3 import MATD3
from replay_buffer import ReplayBuffer


class Arguments:
    def __init__(self):
        # One episode is exactly one day: 24 steps x 1 hour.
        self.max_episodes = 3000
        self.episode_limit = 24
        self.max_train_steps = self.max_episodes * self.episode_limit * 0.8

        self.max_action = 1.0

        # Environment has one agent.
        self.N = 1

        # Observation: PV, wind, base load, outdoor temp,
        # indoor temp, SOC, hour.
        self.obs_dim_total = 7
        self.obs_dim_n = [7]

        # Action: battery, diesel generator, HVAC setpoint delta.
        self.action_dim_n = [3]

        # Replay buffer.
        self.buffer_size = 50000
        self.batch_size = 256

        # Neural network.
        self.hidden_dim = 512
        self.lr_a = 0.001
        self.lr_c = 0.001

        # Exploration noise.
        self.noise_std_init = 0.20
        self.noise_std_min = 0.01
        self.noise_decay_steps = self.max_train_steps
        self.use_noise_decay = True

        # MATD3 / TD3.
        self.gamma = 0.98
        self.tau = 0.001
        self.use_orthogonal_init = True
        self.use_grad_clip = True
        self.policy_noise = 0.2
        self.noise_clip = 0.5
        self.policy_freq = 2

        # Training schedule.
        self.train_freq = 4
        self.model_dir = "model"
        self.reward_figure_path = "demo_figures/training_reward.png"


def get_device():
    if torch.cuda.is_available():
        device = torch.device("cuda:0")
        torch.cuda.set_device(0)
    else:
        device = torch.device("cpu")

    return device


def set_seed(seed, device):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if device.type == "cuda":
        torch.cuda.manual_seed_all(seed)


def plot_training_rewards(rewards_history, output_path):
    plt.figure(figsize=(11, 6))
    x = np.arange(1, len(rewards_history) + 1)

    plt.plot(
        x,
        rewards_history,
        color="tab:blue",
        alpha=0.40,
        linewidth=1,
        label="Episode reward",
    )

    moving_average_window = 50

    if len(rewards_history) >= moving_average_window:
        moving_average = np.convolve(
            rewards_history,
            np.ones(moving_average_window) / moving_average_window,
            mode="valid",
        )

        plt.plot(
            np.arange(
                moving_average_window,
                len(rewards_history) + 1,
            ),
            moving_average,
            color="tab:red",
            linewidth=2,
            label="50-episode moving average",
        )

    plt.xlabel("Episode")
    plt.ylabel("Total daily reward")
    plt.title("MATD3 Training Reward for Home Energy Management")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.show()
    plt.close()


if __name__ == "__main__":
    args = Arguments()
    device = get_device()

    print("Using device:", device)
    print("Episode steps:", args.episode_limit)
    print("Total training steps:", args.max_train_steps)
    print("Observation dimension:", args.obs_dim_n)
    print("Action dimension:", args.action_dim_n)

    args.noise_std_decay = (
        args.noise_std_init - args.noise_std_min
    ) / args.noise_decay_steps

    seed = 42
    set_seed(seed, device)
    print("Random seed:", seed)

    # Research environment only. The interactive LivingMind App does not execute this file.
    env = GYMEnv(enable_hvac=True)
    env_evaluate = GYMEnv(enable_hvac=True)

    agent_n = [
        MATD3(args, agent_id, device)
        for agent_id in range(args.N)
    ]

    replay_buffer = ReplayBuffer(args, device)

    noise_std = args.noise_std_init
    total_steps = 0
    rewards_history = []

    os.makedirs(args.model_dir, exist_ok=True)

    for episode in range(args.max_episodes):
        obs_n = env.reset()

        episode_reward = 0.0
        episode_steps = 0
        daily_grid_energy = 0.0
        daily_hvac_energy = 0.0

        # Each episode always runs exactly 24 steps.
        for step in range(args.episode_limit):
            a_n = [
                agent.choose_action(obs, noise_std)
                for agent, obs in zip(agent_n, obs_n)
            ]

            obs_next_n, reward_n, env_done_n, info = env.step(a_n)

            # env.py returns reward in multi-agent list form: [reward].
            r_n = np.asarray(reward_n, dtype=np.float32)

            # The 24th transition is the terminal transition.
            episode_done = step == args.episode_limit - 1
            done_n = np.array(
                [float(episode_done)],
                dtype=np.float32,
            )

            obs_n_array = np.asarray(obs_n, dtype=np.float32)
            action_n_array = np.asarray(a_n, dtype=np.float32)
            obs_next_n_array = np.asarray(
                obs_next_n,
                dtype=np.float32,
            )

            replay_buffer.store_transition(
                obs_n_array,
                action_n_array,
                r_n,
                obs_next_n_array,
                done_n,
            )

            obs_n = obs_next_n
            episode_reward += float(r_n[0])
            daily_grid_energy += max(info["grid_kw"], 0.0)
            daily_hvac_energy += info["hvac_kw"]

            total_steps += 1
            episode_steps += 1

            if args.use_noise_decay:
                noise_std = max(
                    args.noise_std_min,
                    noise_std - args.noise_std_decay,
                )

            if (
                replay_buffer.current_size >= args.batch_size
                and total_steps % args.train_freq == 0
            ):
                for agent_id in range(args.N):
                    agent_n[agent_id].train(
                        replay_buffer,
                        agent_n,
                    )

        rewards_history.append(episode_reward)

        print(
            "Episode: {:4d} | steps: {:2d} | total_steps: {:6d} | "
            "noise: {:.4f} | reward: {:8.3f} | "
            "grid import: {:6.2f} kWh | HVAC: {:6.2f} kWh".format(
                episode + 1,
                episode_steps,
                total_steps,
                noise_std,
                episode_reward,
                daily_grid_energy,
                daily_hvac_energy,
            )
        )

    plot_training_rewards(
        rewards_history,
        args.reward_figure_path,
    )

    for agent_id in range(args.N):
        agent_n[agent_id].save_model(
            "HomeEnergy",
            "MATD3",
            3,
            args.max_episodes,
            agent_id,
        )

    print("Training over.")
    print("Reward figure saved to:", args.reward_figure_path)
