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

from yarl.utils.initializer import Initializer
from yarl.components.layers.nn.nn_layer import NNLayer
from yarl.components.layers.nn.activation_functions import get_activation_function

if get_backend() == "tf":
    import tensorflow as tf


class DenseLayer(NNLayer):
    """
    A dense (or "fully connected") NN-layer.
    """
    def __init__(self, units, *sub_components, **kwargs):
        """
        Args:
            units (int): The number of nodes in this layer.

        Keyword Args:
            activation (Optional[callable,str]): The activation function to use. Default: None (linear).
            weights_spec (any): A specifier for a weights initializer.
                If None, use the default initializer.
            biases_spec (any): A specifier for a biases initializer.
                If False, use no biases. If None, use the default initializer (0.0).
        """
        # Remove kwargs before calling super().
        self.weights_spec = kwargs.pop("weights_spec", None)
        self.biases_spec = kwargs.pop("biases_spec", None)

        super(DenseLayer, self).__init__(*sub_components, scope=kwargs.pop("scope", "dense-layer"), **kwargs)

        # At build time.
        self.weights_init = None
        self.biases_init = None

        # Number of nodes in this layer.
        self.units = units

    def create_variables(self, input_spaces, action_space):
        in_space = input_spaces["input"]

        # Create weights.
        weights_shape = (in_space.shape[0], self.units)  # [0] b/c Space.shape never includes batch-rank
        self.weights_init = Initializer.from_spec(shape=weights_shape, specification=self.weights_spec)
        # And maybe biases.
        biases_shape = (self.units,)
        self.biases_init = Initializer.from_spec(shape=biases_shape, specification=self.biases_spec)

        # Wrapper for backend.
        if get_backend() == "tf":
            self.layer = tf.layers.Dense(
                units=self.units,
                activation=get_activation_function(self.activation, *self.activation_params),
                kernel_initializer=self.weights_init.initializer,
                use_bias=(self.biases_spec is not False),
                bias_initializer=(self.biases_init.initializer or tf.zeros_initializer()),
            )

            # Now build the layer so that its variables get created.
            self.layer.build(in_space.get_shape(with_batch_rank=True))
            # Register the generated variables with our registry.
            self.register_variables(*self.layer.variables)
