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

import numpy as np
import unittest

from yarl.components import Component, CONNECT_ALL, Synchronizable
from yarl.spaces import FloatBox
from yarl.tests import ComponentTest

VARIABLE_NAMES = ["variable_to_sync1", "variable_to_sync2"]


class MyCompWithVars(Component):
    """
    The Component with variables to test. Synchronizable can be added later as a drop-in via add_component.
    """
    def __init__(self, initializer1=0.0, initializer2=1.0, synchronizable=False, **kwargs):
        super(MyCompWithVars, self).__init__(**kwargs)
        self.space = FloatBox(shape=(4, 5))
        self.initializer1 = initializer1
        self.initializer2 = initializer2
        self.dummy_var_1 = None
        self.dummy_var_2 = None
        if synchronizable is True:
            self.add_component(Synchronizable(), connections=CONNECT_ALL)

    def create_variables(self, input_spaces, action_space):
        # create some dummy var to sync from/to.
        self.dummy_var_1 = self.get_variable(name=VARIABLE_NAMES[0], from_space=self.space,
                                             initializer=self.initializer1, trainable=True)
        self.dummy_var_2 = self.get_variable(name=VARIABLE_NAMES[1], from_space=self.space,
                                             initializer=self.initializer2, trainable=True)


class TestSynchronizableComponent(unittest.TestCase):

    def test_values_out_socket(self):
        # Proof that all Components can push out their variable values.
        component_to_test = MyCompWithVars(synchronizable=False)
        test = ComponentTest(component=component_to_test)

        # Test pulling the variable values from the sync_out socket.
        expected1 = np.zeros(shape=component_to_test.space.shape)
        expected2 = np.ones(shape=component_to_test.space.shape)
        expected = dict(variable_to_sync1=expected1, variable_to_sync2=expected2)
        test.test(out_socket_names="_variables", inputs=None, expected_outputs=expected)

    def test_sync_socket(self):
        # Two Components, one with Synchronizable dropped in:
        # A: Can only push out values.
        # B: To be synced by A's values.
        sync_from = MyCompWithVars(scope="sync-from")
        sync_to = MyCompWithVars(initializer1=8.0, initializer2=7.0, scope="sync-to")
        # Add the Synchronizable to sync_to.
        sync_to.add_component(Synchronizable(), connections=CONNECT_ALL)
        # Create a dummy test component that contains our two Synchronizables.
        component_to_test = Component(name="dummy-comp")
        component_to_test.define_outputs("do_the_sync")
        component_to_test.add_components(sync_from, sync_to)
        # connect everything correctly
        component_to_test.connect((sync_from, "_variables"), (sync_to, "_values"))
        component_to_test.connect((sync_to, "sync"), "do_the_sync")
        test = ComponentTest(component=component_to_test)

        # Test syncing the variable from->to and check them before and after the sync.

        # Before the sync.
        test.variable_test(sync_to.get_variables(VARIABLE_NAMES), {
            "sync-to/"+VARIABLE_NAMES[0]: np.full(shape=sync_from.space.shape, fill_value=8.0),
            "sync-to/"+VARIABLE_NAMES[1]: np.full(shape=sync_from.space.shape, fill_value=7.0)
        })

        # Now sync and re-check.
        test.test(out_socket_names="do_the_sync", inputs=None, expected_outputs=None)

        # After the sync.
        test.variable_test(sync_to.get_variables(VARIABLE_NAMES), {
            "sync-to/"+VARIABLE_NAMES[0]: np.zeros(shape=sync_from.space.shape),
            "sync-to/"+VARIABLE_NAMES[1]: np.ones(shape=sync_from.space.shape)
        })

    def test_sync_socket_between_2_identical_comps_that_have_vars_only_in_their_sub_comps(self):
        """
        Similar to the Policy scenario, where the Policy Component owns a NeuralNetwork (which has vars)
        and has to be synced with other Policies.
        """
        # Create 2x: A custom Component (with vars) that holds another Component (with vars).
        # Then sync between them.
        comp1 = MyCompWithVars(scope="comp1")
        comp1.add_component(MyCompWithVars(scope="sub-comp1-with-vars"), connections=CONNECT_ALL)
        comp2_writable = MyCompWithVars(initializer1=3.0, initializer2=4.2, scope="comp2")
        comp2_writable.add_components(MyCompWithVars(initializer1=5.0, initializer2=6.2, scope="sub-comp2-with-vars"),
                                      Synchronizable(),
                                      connections=CONNECT_ALL)
        container = Component(comp1, comp2_writable, scope="container")
        container.define_outputs("do_the_sync")
        container.connect((comp1, "_variables"), (comp2_writable, "_values"))
        container.connect((comp2_writable, "sync"), (container, "do_the_sync"))
        test = ComponentTest(component=container)

        # Before the sync.
        test.variable_test(comp2_writable.get_variables([
            "container/comp2/variable_to_sync1",
            "container/comp2/variable_to_sync2",
            "container/comp2/sub-comp2-with-vars/variable_to_sync1",
            "container/comp2/sub-comp2-with-vars/variable_to_sync2"
            ]), {
            "container/comp2/variable_to_sync1": np.full(shape=comp1.space.shape, fill_value=3.0, dtype=np.float32),
            "container/comp2/variable_to_sync2": np.full(shape=comp1.space.shape, fill_value=4.2, dtype=np.float32),
            "container/comp2/sub-comp2-with-vars/variable_to_sync1": np.full(shape=comp1.space.shape, fill_value=5.0,
                                                                             dtype=np.float32),
            "container/comp2/sub-comp2-with-vars/variable_to_sync2": np.full(shape=comp1.space.shape, fill_value=6.2,
                                                                             dtype=np.float32)
        })

        # Now sync and re-check.
        test.test(out_socket_names="do_the_sync", inputs=None, expected_outputs=None)

        # After the sync.
        test.variable_test(comp2_writable.get_variables([
            "container/comp2/variable_to_sync1",
            "container/comp2/variable_to_sync2",
            "container/comp2/sub-comp2-with-vars/variable_to_sync1",
            "container/comp2/sub-comp2-with-vars/variable_to_sync2"
            ]), {
            "container/comp2/variable_to_sync1": np.zeros(shape=comp1.space.shape, dtype=np.float32),
            "container/comp2/variable_to_sync2": np.ones(shape=comp1.space.shape, dtype=np.float32),
            "container/comp2/sub-comp2-with-vars/variable_to_sync1": np.zeros(shape=comp1.space.shape, dtype=np.float32),
            "container/comp2/sub-comp2-with-vars/variable_to_sync2": np.ones(shape=comp1.space.shape, dtype=np.float32)
        })




