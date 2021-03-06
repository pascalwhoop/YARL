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

from yarl.envs.environment import Environment
from yarl.envs.grid_world import GridWorld
from yarl.envs.openai_gym import OpenAIGymEnv
from yarl.envs.random_env import RandomEnv


Environment.__lookup_classes__ = dict(
    gridworld=GridWorld,
    openai=OpenAIGymEnv,
    openaigymenv=OpenAIGymEnv,
    openaigym=OpenAIGymEnv,
    randomenv=RandomEnv,
    random = RandomEnv,
)

__all__ = ["Environment", "GridWorld", "OpenAIGymEnv", "RandomEnv"]
