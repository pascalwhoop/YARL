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

from yarl import get_backend, YARLError
from yarl.utils.util import dtype
from yarl.components import Component
from yarl.spaces import IntBox, FloatBox
from yarl.components.explorations.epsilon_exploration import EpsilonExploration
from yarl.components.common import NoiseComponent

if get_backend() == "tf":
    import tensorflow as tf


class Exploration(Component):
    """
    A Component that can be plugged on top of a Policy's output to produce action choices.
    It includes noise and/or epsilon-based exploration options as well as an out-Socket to draw actions from
    the Policy's distribution - either by sampling or by deterministically choosing the max-likelihood value.

    API:
    ins:
        time_step (int): The current global time step (used to determine the extend of the exploration).
        sample_deterministic (any): The Policy's deterministic (max-likelihood) sampling output.
        sample_stochastic (any): The Policy's stochastic sampling output.
    outs:
        do_explore (bool): Whether we chose to explore (act randomly) or not (act according to `non_explore_behavior`).
        action (any): A single action choice according to our exploration settings and Policy's distribution.
        # TODO: actions (any): A batch of actions taken from a batch of NN-outputs without any exploration.
    """
    def __init__(self, non_explore_behavior="max-likelihood", epsilon_spec=None, noise_spec=None,
                 scope="exploration", **kwargs):
        """
        Args:
            non_explore_behavior (str): One of:
                max-likelihood: When not exploring, pick an action deterministically (max-likelihood) from the
                    Policy's distribution.
                sample: When not exploring, pick an action stochastically according to the Policy's distribution.
                random: When not exploring, pick an action randomly.
            epsilon_spec (any): The spec or Component object itself to construct an EpsilonExploration Component.
            noise_spec (dict): The specification dict for a noise generator that adds noise to the NN's output.
        """
        super(Exploration, self).__init__(scope=scope, **kwargs)

        self.action_space = None
        self.non_explore_behavior = non_explore_behavior

        # Define our interface.
        self.define_inputs("sample_deterministic", "sample_stochastic", "time_step")
        self.define_outputs("action", "do_explore", "noise")

        self.epsilon_exploration = None
        self.noise_component = None

        # Don't allow both epsilon and noise component
        if epsilon_spec and noise_spec:
            raise YARLError("Cannot use both epsilon exploration and a noise component at the same time.")

        # Add epsilon component
        if epsilon_spec:
            self.epsilon_exploration = EpsilonExploration.from_spec(epsilon_spec)
            self.add_component(self.epsilon_exploration)
            self.connect("time_step", (self.epsilon_exploration, "time_step"))
            self.connect((self.epsilon_exploration, "do_explore"), "do_explore")

            # Add our own graph_fn and connect its output to the "action" Socket.
            self.add_graph_fn(inputs=[(self.epsilon_exploration, "do_explore"),
                                      "sample_deterministic", "sample_stochastic"],
                              outputs="action",
                              method=self._graph_fn_pick)

        # Add noise component
        elif noise_spec:
            # Currently no noise component uses the time_step variable
            self.unconnected_sockets_in_meta_graph.add("time_step")

            self.noise_component = NoiseComponent.from_spec(noise_spec)
            self.add_component(self.noise_component)
            self.connect((self.noise_component, "noise"), "noise")
            self.add_graph_fn(inputs=[(self.noise_component, "noise"),
                                      "sample_deterministic", "sample_stochastic"],
                              outputs="action",
                              method=self._graph_fn_add_noise)

        # Don't explore at all
        else:
            if self.non_explore_behavior == "max-likelihood":
                self.connect("sample_deterministic", "action")
            else:
                self.connect("sample_stochastic", "action")

    def check_input_spaces(self, input_spaces, action_space):
        self.action_space = action_space.with_batch_rank()
        assert self.action_space.has_batch_rank, "ERROR: `self.action_space` does not have batch rank!"

        if self.epsilon_exploration and self.noise_component:
            # Check again at graph creation? This is currently redundant to the check in __init__
            raise YARLError("Cannot use both epsilon exploration and a noise component at the same time.")

        if self.epsilon_exploration:
            # Currently only IntBox is allowed for discrete action spaces
            assert isinstance(self.action_space, IntBox), "Only IntBox Spaces are currently supported " \
                                                          "for exploration components."
            assert self.action_space.num_categories is not None and self.action_space.num_categories > 0, \
                "ERROR: `action_space` must have `num_categories` defined and > 0!"

        elif self.noise_component:
            assert isinstance(self.action_space, FloatBox), "Only FloatBox spaces are currently supported " \
                                                            "for noise components."

    def _graph_fn_pick(self, do_explore, sample_deterministic, sample_stochastic):
        """
        Exploration for discrete action spaces.
        Either pick random daction (if `do_explore` is True), or return non-explorative action.

        Args:
            do_explore (DataOp): The bool coming from the epsilon-exploration component specifying
                whether to use exploration or not.
            sample_deterministic (DataOp): The output from our distribution's "sample_deterministic" Socket.
            sample_stochastic (DataOp): The output from our distribution's "sample_stochastic" Socket.

        Returns:
            DataOp: The DataOp representing the action. This will match the shape of self.action_space.
        """
        if get_backend() == "tf":
            return tf.cond(do_explore,
                           # (1,) = Adding artificial batch rank.
                           true_fn=lambda: tf.random_uniform(shape=(1,) + self.action_space.shape,
                                                             maxval=self.action_space.num_categories,
                                                             dtype=dtype("int")),
                           false_fn=lambda: sample_deterministic if self.non_explore_behavior == "max-likelihood"
                           else sample_stochastic)

    def _graph_fn_add_noise(self, noise, sample_deterministic, sample_stochastic):
        """
        Noise for continuous action spaces.
        Return the action with added noise.

        Args:
            noise (DataOp): The noise coming from the noise component.
            sample_deterministic (DataOp): The output from our distribution's "sample_deterministic" Socket.
            sample_stochastic (DataOp): The output from our distribution's "sample_stochastic" Socket.

        Returns:
            DataOp: The DataOp representing the action. This will match the shape of self.action_space.

        """
        if get_backend() == "tf":
            if self.non_explore_behavior == 'max-likelihood':
                return sample_deterministic + noise
            else:
                return sample_stochastic + noise


"""        
        ActionHeadComponent
    __init__(action-space, epsilon-comp=epsilon-component if None, no epsilon;
        alternatively: noise-component to be added to continuous action output?
        epsilon-strategy=[greedy|sample|random])
    in: network-output (q-values or probs), time-step
    out: "act"
    _graph_act: use sub-exploration-component with connected  time-step to calculate epsilon:
        if explore: pick random action from some distribution (needs to be specified in c'tor?).
        else: pick greedy action (or some other strategy) according to network-output.


Possibilities:
    - discrete output (q-values (Q-Learning) or (softmaxed) discrete-action probs (PG))
        makes sense to use epsilon-style exploration (if epsilon: random, else greedy or prob-based-sample).
    - continuous output (params for a distribution to pick actions from)
        makes sense to use noise-style exploration (add some noise to the output and sample from that: always sample, there is no random or maybe uniform sampling, but that's probably stupid)
        - what about epsilon for continuous actions? if epsilon: uniform sample? else: normal sample according to the nn-generated distribution.
"""
