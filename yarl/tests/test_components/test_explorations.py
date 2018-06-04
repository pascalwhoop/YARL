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

from yarl.components import Component
from yarl.components.common.decay_components import LinearDecay
from yarl.components.explorations import Exploration, EpsilonExploration
from yarl.components.distributions import NNOutputCleanup, Categorical
from yarl.spaces import *
from yarl.tests import ComponentTest

import numpy as np


class TestExplorations(unittest.TestCase):

    def test_epsilon_exploration(self):
        # Decaying a value always without batch dimension (does not make sense for global time step).
        time_step_space = IntBox(add_batch_rank=False)

        # The Component(s) to test.
        decay_component = LinearDecay(from_=1.0, to_=0.0, start_timestep=0, num_timesteps=1000)
        epsilon_component = EpsilonExploration(decay_component=decay_component)
        test = ComponentTest(component=epsilon_component, input_spaces=dict(time_step=time_step_space))

        # Values to pass as single items.
        input_ = np.array([0, 1, 2, 25, 50, 100, 110, 112, 120, 130, 150, 180, 190, 195, 200, 201, 210, 250, 386,
                           670, 789, 900, 923, 465, 894, 91, 1000])
        expected = np.array([True, True, True, True, True, True, True, True, True, True, True, True, False, True, True,
                             True, True, True, False, False, False, False, False, False, False, True, False])
        for i, e in zip(input_, expected):
            test.test(out_socket_name="do_explore", inputs=i, expected_outputs=e)

    def test_exploration_with_discrete_action_space(self):
        # 2x2 action-pick, each action with 5 categories.
        space = IntBox(5, shape=(2, 2), add_batch_rank=True)
        # Our distribution to go into the Exploration object.
        distribution = Categorical()
        nn_output_cleanup = NNOutputCleanup(target_space=space)
        nn_output_space = FloatBox(shape=(space.flat_dim_with_categories,), add_batch_rank=True)
        exploration = Exploration(action_space=space)
        # The Component to test.
        component_to_test = Component(scope="categorical-plus-exploration")
        component_to_test.define_inputs("nn_output", "time_step")
        component_to_test.define_outputs("action")
        component_to_test.add_components(nn_output_cleanup, distribution, exploration)
        component_to_test.connect("nn_output", [nn_output_cleanup, "nn_output"])
        component_to_test.connect([nn_output_cleanup, "parameters"], [distribution, "parameters"])
        component_to_test.connect([distribution, "sample_deterministic"], [exploration, "sample_deterministic"])
        component_to_test.connect([distribution, "sample_stochastic"], [exploration, "sample_stochastic"])
        component_to_test.connect("time_step", [exploration, "time_step"])
        component_to_test.connect([exploration, "action"], "action")
        test = ComponentTest(component=component_to_test, input_spaces=dict(nn_output=nn_output_space,
                                                                            time_step=int))

        # Parameters for Categorical (batch-size=2, 2x2x5 action space).
        inputs = dict(nn_output=np.array([[100.0, 50.0, 25.0, 12.5, 6.25,
                                           200.0, 100.0, 50.0, 25.0, 12.5,
                                           1.0, 1.0, 1.0, 25.0, 1.0,
                                           1.0, 2.0, 2.0, 1.0, 0.5,
                                           ],
                                          [123.4, 34.7, 98.2, 1.2, 120.0,
                                           200.0, 200.0, 0.00009, 10.0, 300.0,
                                           0.567, 0.678, 0.789, 0.8910, 0.91011,
                                           0.1, 0.1, 0.2, 0.1, 0.5,
                                           ]
                                          ]),
                      time_step=10000)
        expected = np.array([[[0, 0], [3, 1]], [[0, 4], [4, 4]]])
        test.test(out_socket_name="action", inputs=inputs, expected_outputs=expected)

    def test_exploration_with_continuous_action_space(self):
        pass
