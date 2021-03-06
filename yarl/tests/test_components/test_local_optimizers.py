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
import tensorflow as tf

from yarl.components.optimizers import GradientDescentOptimizer
from yarl.spaces import Tuple
from yarl.tests import ComponentTest


class TestLocalOptimizers(unittest.TestCase):

    optimizer = GradientDescentOptimizer(learning_rate=0.01)

    space = dict(
        variables=Tuple(float),
        loss=float,
        grads_and_vars=Tuple(float, float)
    )

    def test_calculate_gradients(self):
        x = tf.Variable(2, name='x', dtype=tf.float32)
        log_x = tf.log(x)
        loss = tf.square(log_x)

        grads_and_vars = self.optimizer._graph_fn_calculate_gradients(variables=[x], loss=loss)
        print(grads_and_vars)

    def test_apply_gradients(self):
        x = tf.Variable(2, name='x', dtype=tf.float32)
        log_x = tf.log(x)
        loss = tf.square(log_x)

        grads_and_vars = self.optimizer._graph_fn_calculate_gradients(variables=[x], loss=loss)
        step = self.optimizer._graph_fn_apply_gradients(grads_and_vars)
        print(step)