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

from yarl.components.neural_networks import NeuralNetwork
from yarl.spaces import FloatBox
from yarl.tests import ComponentTest

import numpy as np


class TestNeuralNetworks(unittest.TestCase):
    """
    Tests for assembling from json and running different NeuralNetworks.
    """
    def test_nn_assembly_from_file(self):
        # Space must contain batch dimension (otherwise, NNlayer will complain).
        space = FloatBox(shape=(3,), add_batch_rank=True)

        # Create a simple neural net from json.
        neural_net = NeuralNetwork.from_file("configs/test_simple_nn.json")  # type: NeuralNetwork

        # Do not seed, we calculate expectations manually.
        test = ComponentTest(component=neural_net, input_spaces=dict(input=space), seed=None)

        # Batch of size=3.
        input_ = np.array([[0.1, 0.2, 0.3], [1.0, 2.0, 3.0], [10.0, 20.0, 30.0]])
        # Calculate output manually.
        var_dict = neural_net.get_variables("hidden-layer/dense/kernel", "hidden-layer/dense/bias", global_scope=False)
        w1_value = test.get_variable_values(var_dict["hidden-layer/dense/kernel"])
        b1_value = test.get_variable_values(var_dict["hidden-layer/dense/bias"])
        expected = np.matmul(input_, w1_value) + b1_value
        test.test(out_socket_names="output", inputs=input_, expected_outputs=expected, decimals=5)

    def test_complex_nn_assembly_from_file(self):
        pass

