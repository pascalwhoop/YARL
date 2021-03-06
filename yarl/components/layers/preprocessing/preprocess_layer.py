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
from __future__ import print_function
from __future__ import division

import tensorflow as tf

from yarl.components.layers import Layer


class PreprocessLayer(Layer):
    """
    A Layer that can serve as a preprocessing layer and also can act on complex container input
    spaces (Dict or Tuple).
    Do not override the `apply` graph_fn method. Instead, override the `preprocess` method, which
    gets called automatically by `apply` after taking care of container inputs.
    It is not required to implement the `reset` logic (or store any state information at all).
    """
    def __init__(self, scope="pre-process", **kwargs):
        super(PreprocessLayer, self).__init__(scope=scope, **kwargs)

        # Define the reset operation (no input sockets necessary).
        self.define_outputs("reset")
        self.add_graph_fn(None, "reset", self._graph_fn_reset)

    def _graph_fn_reset(self):
        """
        Returns:
            An op that resets this processor to some initial state.
            E.g. could be called whenever an episode ends.
            This could be useful if the preprocessor stores certain episode-sequence information
            to do the processing and this information has to be reset after the episode terminates.
        """
        return tf.no_op(name="reset-op")  # Not mandatory.

    def _graph_fn_apply(self, *inputs):
        """
        Args:
            inputs (any): The input to be "pre-processed".

        Returns:
            The op that pre-processes the input.
        """
        raise NotImplementedError

