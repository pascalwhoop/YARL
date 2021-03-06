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

from yarl.components.memories.replay_memory import ReplayMemory
from yarl.spaces import Dict, BoolBox
from yarl.tests import ComponentTest
from yarl.tests.test_util import non_terminal_records, terminal_records


class TestReplayMemory(unittest.TestCase):
    """
    Tests sampling and insertion behaviour of the replay_memory module.
    """
    record_space = Dict(
        states=dict(state1=float, state2=float),
        actions=dict(action1=float),
        reward=float,
        terminals=BoolBox(),
        add_batch_rank=True
    )
    memory_variables = ["size", "index"]
    capacity = 10

    def test_insert(self):
        """
        Simply tests insert op without checking internal logic.
        """
        memory = ReplayMemory(
            capacity=self.capacity,
            next_states=True
        )
        test = ComponentTest(component=memory, input_spaces=dict(
            records=self.record_space,
            num_records=int
        ))

        observation = self.record_space.sample(size=1)
        test.test(out_socket_names="insert_records", inputs=observation, expected_outputs=None)

        observation = self.record_space.sample(size=100)
        test.test(out_socket_names="insert_records", inputs=observation, expected_outputs=None)

    def test_capacity(self):
        """
        Tests if insert correctly manages capacity.
        """
        memory = ReplayMemory(
            capacity=self.capacity,
            next_states=True
        )
        test = ComponentTest(component=memory, input_spaces=dict(
            records=self.record_space,
            num_records=int
        ))
        # Internal state variables.
        memory_variables = memory.get_variables(self.memory_variables, global_scope=False)
        buffer_size = memory_variables['size']
        buffer_index = memory_variables['index']
        size_value, index_value = test.get_variable_values(buffer_size, buffer_index)

        # Assert indices 0 before insert.
        self.assertEqual(size_value, 0)
        self.assertEqual(index_value, 0)

        # Insert one more element than capacity
        observation = self.record_space.sample(size=self.capacity + 1)
        test.test(out_socket_names="insert_records", inputs=observation, expected_outputs=None)

        size_value, index_value = test.get_variable_values(buffer_size, buffer_index)
        # Size should be equivalent to capacity when full.
        self.assertEqual(size_value, self.capacity)

        # Index should be one over capacity due to modulo.
        self.assertEqual(index_value, 1)

    def test_batch_retrieve(self):
        """
        Tests if retrieval correctly manages capacity.
        """
        memory = ReplayMemory(
            capacity=self.capacity,
            next_states=True
        )
        test = ComponentTest(component=memory, input_spaces=dict(
            records=self.record_space,
            num_records=int
        ))

        # Insert 2 Elements.
        observation = non_terminal_records(self.record_space, 2)
        test.test(out_socket_names="insert_records", inputs=observation, expected_outputs=None)

        # Assert we can now fetch 2 elements.
        num_records = 2
        batch = test.test(out_socket_names="get_records", inputs=num_records, expected_outputs=None)
        print('Result batch = {}'.format(batch))
        self.assertEqual(2, len(batch['terminals']))
        # Assert next states key is there
        self.assertTrue('next_states' in batch)

        # Test duplicate sampling.
        num_records = 5
        batch = test.test(out_socket_names="get_records", inputs=num_records, expected_outputs=None)
        self.assertEqual(5, len(batch['terminals']))

        # Now insert over capacity.
        observation = non_terminal_records(self.record_space, self.capacity)
        test.test(out_socket_names="insert_records", inputs=observation, expected_outputs=None)

        # Assert we can fetch exactly capacity elements.
        num_records = self.capacity
        batch = test.test(out_socket_names="get_records", inputs=num_records, expected_outputs=None)
        self.assertEqual(self.capacity, len(batch['terminals']))

    def test_with_terminals_no_next_states(self):
        """
        Tests retrieval works if next state option is deactivated and
        that no next_states key is present.
        """
        memory = ReplayMemory(
            capacity=self.capacity,
            next_states=False
        )
        test = ComponentTest(component=memory, input_spaces=dict(
            records=self.record_space,
            num_records=int
        ))

        # Insert 2 terminal Elements.
        observation = terminal_records(self.record_space, 2)
        test.test(out_socket_names="insert_records", inputs=observation, expected_outputs=None)

        # Assert we can now fetch 2 elements.
        num_records = 2
        batch = test.test(out_socket_names="get_records", inputs=num_records, expected_outputs=None)

        # Sampled 2 elements
        self.assertEqual(num_records, len(batch['terminals']))
        # Both are terminal
        self.assertTrue(batch['terminals'][0] and batch['terminals'][1])
        # No next state key.
        self.assertTrue('next_states' not in batch)

    def test_without_next_state(self):
        """
        Tests retrieval works if next state option is deactivated and
        that no next_states key is present.
        """
        memory = ReplayMemory(
            capacity=self.capacity,
            next_states=False
        )
        test = ComponentTest(component=memory, input_spaces=dict(
            records=self.record_space,
            num_records=int
        ))

        # Insert 2 Elements.
        observation = non_terminal_records(self.record_space, 2)
        test.test(out_socket_names="insert_records", inputs=observation, expected_outputs=None)

        # Assert we can now fetch 2 elements.
        num_records = 2
        batch = test.test(out_socket_names="get_records", inputs=num_records, expected_outputs=None)
        self.assertTrue('next_states' not in batch)

