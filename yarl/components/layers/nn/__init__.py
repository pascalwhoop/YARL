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

from yarl.components.layers.nn.nn_layer import NNLayer
from yarl.components.layers.nn.concat_layer import ConcatLayer
from yarl.components.layers.nn.conv2d_layer import Conv2DLayer
from yarl.components.layers.nn.dense_layer import DenseLayer
from yarl.components.layers.nn.dueling_layer import DuelingLayer

NNLayer.__lookup_classes__ = dict(
    concat=ConcatLayer,
    conv2d=Conv2DLayer,
    dense=DenseLayer,
    fc=DenseLayer,  # alias
    dueling=DuelingLayer
)

__all__ = ["NNLayer", "ConcatLayer", "Conv2DLayer", "DenseLayer", "DuelingLayer"]
