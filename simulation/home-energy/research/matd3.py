import torch
import torch.nn.functional as F
import numpy as np
import copy
from networks import Actor, Critic_MATD3
import os


class MATD3(object):
    def __init__(self, args, agent_id, device):
        self.device = device
        self.N = args.N
        self.agent_id = agent_id
        self.max_action = args.max_action
        self.action_dim = args.action_dim_n[agent_id]
        self.lr_a = args.lr_a
        self.lr_c = args.lr_c
        self.gamma = args.gamma
        self.tau = args.tau
        self.use_grad_clip = args.use_grad_clip
        # Create an individual actor and critic for each agent according to the 'agent_id'
        self.actor = Actor(args, agent_id, device).to(self.device)
        self.critic1 = Critic_MATD3(args, device).to(self.device)
        self.critic2 = Critic_MATD3(args, device).to(self.device)
        self.actor_target = copy.deepcopy(self.actor)
        self.critic1_target = copy.deepcopy(self.critic1)
        self.critic2_target = copy.deepcopy(self.critic2)

        self.actor_optimizer = torch.optim.Adam(self.actor.parameters(), lr=self.lr_a)
        self.critic1_optimizer = torch.optim.Adam(self.critic1.parameters(), lr=self.lr_c)
        self.critic2_optimizer = torch.optim.Adam(self.critic2.parameters(), lr=self.lr_c)

    # Each agent selects actions based on its own local observations(add noise for exploration)
    def choose_action(self, obs, noise_std):
        obs = torch.unsqueeze(torch.tensor(obs, dtype=torch.float), 0).to(self.device)
        a = self.actor(obs).data.cpu().numpy().flatten()
        a = (a + np.random.normal(0, noise_std, size=self.action_dim)).clip(-self.max_action, self.max_action)
        return a

    def train(self, replay_buffer, agent_n):
        batch_obs_n, batch_a_n, batch_r_n, batch_obs_next_n, batch_done_n = replay_buffer.sample()

        # Compute target_Q
        with torch.no_grad():  # target_Q has no gradient
            # Select next actions according to the actor_target
            batch_a_next_n = [agent.actor_target(batch_obs_next).to(self.device) for agent, batch_obs_next in
                              zip(agent_n, batch_obs_next_n)]
            Q1_next = self.critic1_target(batch_obs_next_n, batch_a_next_n)
            Q2_next = self.critic2_target(batch_obs_next_n, batch_a_next_n)
            target_Q=torch.min(Q1_next,Q2_next)
            target_Q = batch_r_n[self.agent_id] + self.gamma * (
                    1 - batch_done_n[self.agent_id]) * target_Q  # shape:(batch_size,1)

        current_Q1 = self.critic1(batch_obs_n, batch_a_n)  # shape:(batch_size,1)
        current_Q2 = self.critic2(batch_obs_n, batch_a_n)
        critic_loss = F.mse_loss(current_Q1, target_Q) + F.mse_loss(current_Q2, target_Q)
        # Optimize the critic
        self.critic1_optimizer.zero_grad()
        self.critic2_optimizer.zero_grad()
        critic_loss.backward()
        if self.use_grad_clip:
            torch.nn.utils.clip_grad_norm_(self.critic1.parameters(), 10.0)
            torch.nn.utils.clip_grad_norm_(self.critic2.parameters(), 10.0)
        self.critic1_optimizer.step()
        self.critic2_optimizer.step()

        # Reselect the actions of the agent corresponding to 'agent_id'，the actions of other agents remain unchanged
        batch_a_n[self.agent_id] = self.actor(batch_obs_n[self.agent_id])
        actor_loss = -self.critic1(batch_obs_n, batch_a_n).mean()
        # Optimize the actor
        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        if self.use_grad_clip:
            torch.nn.utils.clip_grad_norm_(self.actor.parameters(), 10.0)
        self.actor_optimizer.step()

        # Softly update the target networks
        for param, target_param in zip(self.critic1.parameters(), self.critic1_target.parameters()):
            target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)

        for param, target_param in zip(self.critic2.parameters(), self.critic2_target.parameters()):
            target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)

        for param, target_param in zip(self.actor.parameters(), self.actor_target.parameters()):
            target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)


    def save_model(self, env_name, algorithm, number, total_episodes, agent_id):
        directory = "./model/{}/".format(env_name)
        if not os.path.exists(directory):
            os.makedirs(directory)
        torch.save(self.actor.state_dict(),
                   "./model/{}/{}_actor_number_{}_epiosde_{}_agent_{}.pth".format(env_name, algorithm, number,
                                                                                int(total_episodes), agent_id))
        #torch.save(self.critic.state_dict(),
        #           "./model/{}/{}_critic_number_{}_episode_{}_agent_{}.pth".format(env_name, algorithm, number,
        #                                                                         int(total_episodes), agent_id))

    def load_model(self, env_name, algorithm, number, total_episodes, agent_id):
        self.actor.load_state_dict(torch.load(
            "./model/{}/{}_actor_number_{}_epiosde_{}_agent_{}.pth".format(env_name, algorithm, number,
                                                                         int(total_episodes), agent_id)))
        self.actor_target = copy.deepcopy(self.actor)
        #self.critic.load_state_dict(torch.load(
        #    "./model/{}/{}_critic_number_{}_episode_{}_agent_{}.pth".format(env_name, algorithm, number,
        #                                                                  int(total_episodes), agent_id)))
        #self.critic_target = copy.deepcopy(self.critic)


