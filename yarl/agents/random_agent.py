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

from yarl.agents import Agent


class RandomAgent(Agent):
    """
    An Agent that picks random actions from the action Space.
    """
    def __init__(self, states_spec, actions_spec):
        super(RandomAgent, self).__init__(states_spec, actions_spec)

    def build_graph(self, core):
        pass

    def get_action(self, states, deterministic=False):
        return self.action_space.sample()

    def observe(self, states, actions, internals, reward, terminal):
        pass

    def update(self):
        pass
