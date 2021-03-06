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

import logging
import unittest

from yarl.agents import DQNAgent
import yarl.spaces as spaces
from yarl.envs import GridWorld, RandomEnv, OpenAIGymEnv
from yarl.execution.single_threaded_worker import SingleThreadedWorker
from yarl.utils import root_logger


class TestDQNAgentFunctionality(unittest.TestCase):
    """
    Tests the DQN Agent's assembly and functionality.
    """
    root_logger.setLevel(level=logging.DEBUG)

    def test_dqn_assembly(self):
        """
        Creates a DQNAgent and runs it for a few steps in the random Env.
        """
        env = RandomEnv(state_space=spaces.IntBox(2), action_space=spaces.IntBox(2), deterministic=True)
        agent = DQNAgent.from_spec(
            "configs/dqn_agent_for_random_env.json",
            double_q=False,
            dueling_q=False,
            state_space=env.state_space,
            action_space=env.action_space
        )

        worker = SingleThreadedWorker(environment=env, agent=agent)
        timesteps = 100
        results = worker.execute_timesteps(timesteps, deterministic=True)

        print(results)

        self.assertEqual(results["timesteps_executed"], timesteps)
        self.assertEqual(results["env_frames"], timesteps)
        # Assert deterministic execution of Env and Agent.
        self.assertAlmostEqual(results["mean_episode_reward"], 5.923551400230593)
        self.assertAlmostEqual(results["max_episode_reward"], 14.312868008192979)
        self.assertAlmostEqual(results["final_episode_reward"], 0.14325251090518198)

    def test_dqn_functionality(self):
        """
        Creates a DQNAgent and runs it for a few steps in a GridWorld to vigorously test
        all steps of the learning process.
        """
        env = GridWorld(save_mode=True)  # no holes, just fire
        agent = DQNAgent.from_spec(  # type: DQNAgent
            "configs/dqn_agent_for_functionality_test.json",
            double_q=True,
            dueling_q=True,
            state_space=env.state_space,
            action_space=env.action_space
        )
        #replay_memory = agent.memory

        worker = SingleThreadedWorker(environment=env, agent=agent)
        worker.execute_timesteps(1, deterministic=True)

        memory_content = agent.memory.variables


