# Copyright 2018 The YARL-Project, All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest

from yarl.agents.dqn_agent import DQNAgent
from yarl.envs import OpenAIGymEnv
from yarl.execution.single_threaded_worker import SingleThreadedWorker


class TestSingleThreadedDQN(unittest.TestCase):

    # TODO test on the relevant Atari environments.
    env = OpenAIGymEnv(gym_env='Pong-v0')

    # TODO define classic atari dqn network.
    network = list()

    def test_replay_memory_atari_throughput(self):
        """
        Tests throughput on standard Atari envs using the replay memory.
        """
        agent = DQNAgent(
            states_spec=self.env.state_space,
            action_spec=self.env.action_space,
            network_spec=self.network,
            memory_spec=dict(
                type='replay_memory',
                capacity=100000,
                next_states=True
            )
        )
        worker = SingleThreadedWorker(
            environment=self.env,
            agent=agent,
            repeat_actions=1
        )

        result = worker.execute_timesteps(num_timesteps=1000000, deterministic=False)
        print('Agent throughput = {} ops/s'.format(result['ops_per_second']))
        print('Environment throughput = {} frames/s'.format(result['env_frames_per_second']))

    def test_prioritized_replay_atari_throughput(self):
        """
        Tests throughput on standard Atari envs using the prioritized replay memory.
        """
        agent = DQNAgent(
            states_spec=self.env.state_space,
            action_spec=self.env.action_space,
            network_spec=self.network,
            memory_spec=dict(
                type='prioritized',
                capacity=100000,
                next_states=True
            )
        )
        worker = SingleThreadedWorker(
            environment=self.env,
            agent=agent,
            repeat_actions=1
        )

        result = worker.execute_timesteps(num_timesteps=1000000, deterministic=False)
        print('Agent throughput = {} ops/s'.format(result['ops_per_second']))
        print('Environment throughput = {} frames/s'.format(result['env_frames_per_second']))
