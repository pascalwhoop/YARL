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
from cached_property import cached_property

from .space import Space


class BoxSpace(Space):
    """
    A box in R^n with a shape tuple of len n. Each dimension may be bounded.
    """

    def __init__(self, low, high, shape=None, add_batch_rank=False, dtype="float"):
        """
        Args:
            low (any): The lower bound (see Valid Inputs for more information).
            high (any): The upper bound (see Valid Inputs for more information).
            shape (tuple): The shape of this space.
            dtype (str): The data type (as string) for this Space.

        Valid inputs:
            BoxSpace(0.0, 1.0) # low and high are given as scalars and shape is assumed to be ()
                -> single scalar between low and high.
            BoxSpace(-1.0, 1.0, (3,4)) # low and high are scalars, and shape is provided -> nD array
                where all(!) elements are between low and high.
            BoxSpace(np.array([-1.0,-2.0]), np.array([2.0,4.0])) # low and high are arrays of the same shape
                (no shape given!) -> nD array where each dimension has different bounds.
        """
        super(BoxSpace, self).__init__(add_batch_rank=add_batch_rank)
        self._dtype = dtype

        # Determine the shape.
        if shape is None:
            if isinstance(low, (int, float, bool)):
                self._shape = ()
            else:
                self._shape = np.shape(low)
        else:
            assert isinstance(shape, tuple), "ERROR: `shape` must be None or a tuple."
            self._shape = shape

        # 0D Space.
        if self._shape == ():
            assert isinstance(low, (int, float, bool))
            self.low = low
            self.high = high
        # nD Space (n > 0). Bounds can be single number or individual bounds.
        else:
            # Low/high values are given individually per item.
            if isinstance(low, (list, tuple, np.ndarray)):
                self.low = np.array(low)
                self.high = np.array(high)
                assert self.low.shape == self.high.shape
            # Only one low/high value. Use these as generic bounds for all values.
            else:
                assert np.isscalar(low) and np.isscalar(high)
                self.low = low + np.zeros(self.shape)
                self.high = high + np.zeros(self.shape)

    @cached_property
    def shape(self):
        return self._shape

    @cached_property
    def shape_with_batch_rank(self):
        if self.shape == ():
            return self.batch_rank_tuple
        return tuple(self.batch_rank_tuple + self.shape)

    @cached_property
    def flat_dim(self):
        return int(np.prod(self.shape))  # also works for shape=()

    @cached_property
    def dtype(self):
        return self._dtype

    @cached_property
    def bounds(self):
        return self.low, self.high

    def __repr__(self):
        return "{}({}{})".format(type(self).__name__.title(), self.shape, "; +batch" if self.has_batch_rank else "")

    def __eq__(self, other):
        return isinstance(other, self.__class__) and \
               np.allclose(self.low, other.low) and np.allclose(self.high, other.high)

    def contains(self, sample):
        if self.shape == ():
            return self.low <= sample <= self.high
        else:
            if sample.shape != self.shape:
                return False
            return (sample >= self.low).all() and (sample <= self.high).all()
