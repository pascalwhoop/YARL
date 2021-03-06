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

from yarl import get_backend
from yarl.components.optimizers.optimizer import Optimizer
from yarl.utils.ops import DataOpTuple

if get_backend() == "tf":
    import tensorflow as tf


class LocalOptimizer(Optimizer):
    """
    A local optimizer performs optimization irrespective of any distributed semantics, i.e.
    it has no knowledge of other machines and does not implement any communications with them.
    """
    def __init__(self, learning_rate, **kwargs):
        super(LocalOptimizer, self).__init__(
            learning_rate=learning_rate,
            scope=kwargs.pop("scope", "local-optimizer"),
            **kwargs
        )
        self.optimizer = None

    def _graph_fn_calculate_gradients(self, variables, loss, *inputs):
        if get_backend() == "tf":
            grads_and_vars = DataOpTuple(self.optimizer.compute_gradients(
                loss=loss,
                var_list=list(variables.values()) if isinstance(variables, dict) else variables
            ))

            return grads_and_vars

    def _graph_fn_apply_gradients(self, grads_and_vars):
        if get_backend() == "tf":
            return self.optimizer.apply_gradients(
                grads_and_vars=grads_and_vars
            )


class GradientDescentOptimizer(LocalOptimizer):
    """
    Classic gradient descent optimizer:
    "Stochastic Estimation of the Maximum of a Regression Function." - Kiefer and Wolfowitz, 1952
    """
    def __init__(self, learning_rate, **kwargs):
        super(GradientDescentOptimizer, self).__init__(
            learning_rate=learning_rate,
            scope=kwargs.pop("scope", "gradient-descent-optimizer"),
            **kwargs
        )

        if get_backend() == "tf":
            self.optimizer = tf.train.GradientDescentOptimizer(learning_rate=self.learning_rate)


class AdamOptimizer(LocalOptimizer):
    """
    Adaptive momentum optimizer:
    https://arxiv.org/abs/1412.6980
    """
    def __init__(self, learning_rate, **kwargs):
        super(AdamOptimizer, self).__init__(
            learning_rate=learning_rate, scope=kwargs.pop("scope", "adam-optimizer"), **kwargs
        )

        if get_backend() == "tf":
            self.optimizer = tf.train.AdamOptimizer(
                learning_rate=self.learning_rate,
                beta1=kwargs.pop("beta_1", kwargs.pop("beta1", 0.9)),
                beta2=kwargs.pop("beta_2", kwargs.pop("beta2", 0.999))
            )


class NadamOptimizer(LocalOptimizer):
    """
    Nesterov-adaptive momentum optimizer which applies Nesterov's accelerated gradient to Adam:
    http://cs229.stanford.edu/proj2015/054_report.pdf
    """
    def __init__(self, learning_rate, **kwargs):
        super(NadamOptimizer, self).__init__(
            learning_rate=learning_rate, scope=kwargs.pop("scope", "nadam-optimizer"), **kwargs
        )

        if get_backend() == "tf":
            self.optimizer = tf.keras.optimizers.Nadam(
                lr=self.learning_rate,
                beta_1=kwargs.pop("beta_1", kwargs.pop("beta1", 0.9)),
                beta_2=kwargs.pop("beta_2", kwargs.pop("beta2", 0.999)),
                schedule_decay=kwargs.pop("schedule_decay", 0.004)
            )


class AdagradOptimizer(LocalOptimizer):
    """
    Adaptive gradient optimizer which sets small learning rates for frequently appearing features
    and large learning rates for rare features:
    http://www.jmlr.org/papers/volume12/duchi11a/duchi11a.pdf
    """
    def __init__(self, learning_rate, **kwargs):
        super(AdagradOptimizer, self).__init__(
            learning_rate=learning_rate,
            scope=kwargs.pop("scope", "adagrad-optimizer"),
            **kwargs
        )

        if get_backend() == "tf":
            self.optimizer = tf.train.AdagradOptimizer(
                learning_rate=self.learning_rate,
                initial_accumulator_value=kwargs.pop("initial_accumulator_value", 0.1)
            )


class AdadeltaOptimizer(LocalOptimizer):
    """
    Adadelta optimizer which adapts learning rate over time:
    https://arxiv.org/abs/1212.5701
    """
    def __init__(self, learning_rate, **kwargs):
        super(AdadeltaOptimizer, self).__init__(
            learning_rate=learning_rate, scope=kwargs.pop("scope", "adadelta-optimizer"), **kwargs
        )

        if get_backend() == "tf":
            self.optimizer = tf.train.AdadeltaOptimizer(learning_rate=self.learning_rate, rho=kwargs.pop("rho", 0.95))


class SGDOptimizer(LocalOptimizer):
    """
    Stochastic gradient descent optimizer from tf.keras including support for momentum, learning-rate-decay and
    Nesterov momentum.
    """
    def __init__(self, learning_rate, **kwargs):
        super(SGDOptimizer, self).__init__(
            learning_rate=learning_rate, scope=kwargs.pop("scope", "sgd-optimizer"), **kwargs
        )

        if get_backend() == "tf":
            self.optimizer = tf.keras.optimizers.SGD(
                lr=self.learning_rate, momentum=kwargs.pop("momentum", 0.0), decay=kwargs.pop("decay", 0.0),
                nesterov=kwargs.pop("nesterov", False))


class RMSPropOptimizer(LocalOptimizer):
    """
    RMSPRop Optimizer as discussed by Hinton:
    https://www.cs.toronto.edu/~tijmen/csc321/slides/lecture_slides_lec6.pdf
    """
    def __init__(self, learning_rate, **kwargs):
        super(RMSPropOptimizer, self).__init__(
            learning_rate=learning_rate, scope=kwargs.pop("scope", "rmsprop-optimizer"), **kwargs
        )

        if get_backend() == "tf":
            self.optimizer = tf.train.AdadeltaOptimizer(learning_rate=self.learning_rate, rho=kwargs.pop("rho", 0.95))
