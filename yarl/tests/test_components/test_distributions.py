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

from yarl.components.distributions import *
from yarl.spaces import *
from yarl.tests import ComponentTest

import numpy as np


class TestDistributions(unittest.TestCase):

    def test_bernoulli(self):
        # Create 5 bernoulli distributions (or a multiple thereof if we use batch-size > 1).
        param_space = FloatBox(shape=(5,), add_batch_rank=True)

        # The Component to test.
        bernoulli = Bernoulli()  # add the "draw" Socket
        test = ComponentTest(component=bernoulli, input_spaces=dict(
            parameters=param_space,
            max_likelihood=BoolBox(),
            values=FloatBox(),
            other_distribution=0
        ))

        # Batch of size=1 and deterministic.
        input_ = {
            "parameters": np.array([[0.5, 0.99, 0.0, 0.2, 0.3]]),
            "max_likelihood": True
        }
        expected = np.array([[True, True, False, False, False]])
        test.test(out_socket_names="draw", inputs=input_, expected_outputs=expected)
        # Try the same on the sample_deterministic out-Socket without the max_likelihood input..
        test.test(out_socket_names="sample_deterministic", inputs=input_["parameters"], expected_outputs=expected)

        # Batch of size=2 and non-deterministic -> expect always the same result when we seed tf (done automatically
        # by the ComponentTest object).
        input_ = {
            "parameters": np.array([[0.1, 0.3, 0.6, 0.71, 0.001], [0.9, 0.998, 0.9999, 0.0001, 0.345678]]),
            "max_likelihood": False
        }
        expected = np.array([[False, False, True, False, False], [True, True, True, False, False]])
        test.test(out_socket_names="draw", inputs=input_, expected_outputs=expected)
        # Try the same on the sample_stochastic out-Socket without the max_likelihood input..
        expected = np.array([[False, False, True, True, False], [True, True, True, False, False]])
        test.test(out_socket_names="sample_stochastic", inputs=input_["parameters"], expected_outputs=expected)

    def test_categorical(self):
        # Create 5 categorical distributions of 3 categories each.
        param_space = FloatBox(shape=(5, 3), add_batch_rank=True)

        # The Component to test.
        categorical = Categorical()  # add the "draw" Socket
        test = ComponentTest(component=categorical, input_spaces=dict(
            parameters=param_space,
            max_likelihood=BoolBox(),
            values=FloatBox(),
            other_distribution=0
          ))

        # Batch of size=1 and deterministic.
        input_ = {
            "parameters": np.array([[[0.5, 0.25, 0.25],
                                     [0.98, 0.01, 0.01],
                                     [0.0, 0.6, 0.4],
                                     [0.2, 0.25, 0.55],
                                     [0.3, 0.3, 0.4]
                                     ]]),
            "max_likelihood": True
        }
        expected = np.array([[0, 0, 1, 2, 2]])
        test.test(out_socket_names="draw", inputs=input_, expected_outputs=expected)
        test.test(out_socket_names="sample_deterministic", inputs=input_["parameters"], expected_outputs=expected)

        # Batch of size=2 and non-deterministic -> expect always the same result when we seed tf (done automatically
        # by the ComponentTest object).
        input_ = {
            "parameters": np.array([[[0.3, 0.25, 0.45],
                                     [0.96, 0.02, 0.02],
                                     [0.0, 0.5, 0.5],
                                     [0.1, 0.85, 0.05],
                                     [0.6, 0.1, 0.3]
                                     ],
                                    [[0.65, 0.05, 0.3],
                                     [0.0001, 0.0001, 0.9998],
                                     [0.82, 0.12, 0.06],
                                     [0.5, 0.0001, 0.4999],
                                     [0.333, 0.333, 0.334]
                                     ]
                                    ]),
            "max_likelihood": False
        }
        expected = np.array([[0, 0, 2, 1, 2], [0, 2, 0, 2, 2]])
        test.test(out_socket_names="draw", inputs=input_, expected_outputs=expected)
        expected = np.array([[2, 0, 1, 1, 2], [2, 2, 1, 0, 0]])
        test.test(out_socket_names="sample_stochastic", inputs=input_["parameters"], expected_outputs=expected)

    def test_categorical_on_different_space(self):
        # Create 5 categorical distributions of 2 categories each.
        param_space = FloatBox(shape=(5, 2), add_batch_rank=True)

        # The Component to test.
        categorical = Categorical()  # no "draw" Socket
        test = ComponentTest(component=categorical,
                             input_spaces=dict(
                                 parameters=param_space,
                                 max_likelihood=BoolBox(),
                                 values=FloatBox(),
                                 other_distribution=0
                             ))

        # Batch of size=1 and deterministic.
        input_ = np.array([[[0.5, 0.5],
                            [0.98, 0.02],
                            [0.0, 1.0],
                            [0.2, 0.8],
                            [0.3, 0.6]
                            ]])
        expected = np.array([[0, 0, 1, 1, 1]])
        test.test(out_socket_names="sample_deterministic", inputs=input_, expected_outputs=expected)

        # Batch of size=2 and non-deterministic -> expect always the same result when we seed tf (done automatically
        # by the ComponentTest object).
        input_ = np.array([[[0.25, 0.75],
                            [0.96, 0.04],
                            [0.5, 0.5],
                            [0.05, 0.95],
                            [0.6, 0.4]
                            ],
                           [[0.65, 0.35],
                            [0.0002, 0.9998],
                            [0.82, 0.18],
                            [0.5001, 0.4999],
                            [0.333, 0.667]
                            ]
                           ])
        expected = np.array([[1, 0, 0, 1, 1], [1, 1, 1, 0, 0]])
        test.test(out_socket_names="sample_stochastic", inputs=input_, expected_outputs=expected)

    def test_normal(self):
        # Create 5 normal distributions (2 parameters (mean and stddev) each).
        param_space = Tuple(FloatBox(shape=(5,)), FloatBox(shape=(5,)), add_batch_rank=True)

        # The Component to test.
        normal = Normal()  # add the "draw" Socket
        test = ComponentTest(component=normal, input_spaces=dict(
            parameters=param_space,
            max_likelihood=BoolBox(),
            values=FloatBox(),
            other_distribution=0
        ))

        # Batch of size=2 and deterministic.
        input_ = {
            "parameters": (np.array([[1.0, 0.0001, 2.25632, 100, 30.0], [1000.65, 999.0001, 23.2, 45.5, 1.233434545]]),
                           np.array([[1.0, 0.01, 0.6, 0.25, 0.3], [5, 100.1, 0.12, 0.0001, 30.2]])),
            "max_likelihood": True
        }
        expected = np.array([[1.0, 0.000099999997, 2.25632, 100.0, 30.0],
                             [1000.65, 999.00012, 23.200001, 45.5, 1.2334346]], dtype=np.float32)
        test.test(out_socket_names="draw", inputs=input_, expected_outputs=expected)
        test.test(out_socket_names="sample_deterministic", inputs=input_["parameters"], expected_outputs=expected)

        # Batch of size=1 and non-deterministic -> expect always the same result when we seed tf (done automatically
        # by the ComponentTest object).
        input_ = {
            "parameters": (np.array([[2.0, 1.0001, 45.252, 150.5, 33.0]]),
                           np.array([[2.0, 0.01, 0.698, 0.2, 33.00]])),
            "max_likelihood": False
        }
        expected = np.array([[-0.1694195, 1.0074502, 44.38831, 150.9867, 51.451096]], dtype=np.float32)
        test.test(out_socket_names="draw", inputs=input_, expected_outputs=expected)
        expected = np.array([[1.6836157, 1.0118003, 45.752514, 150.26578, 71.332825]], dtype=np.float32)
        test.test(out_socket_names="sample_stochastic", inputs=input_["parameters"], expected_outputs=expected)
