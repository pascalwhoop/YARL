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

from collections import OrderedDict
import copy

from yarl import Specifiable


class Space(Specifiable):
    """
    Space class (based and compatible with openAI).
    Provides a classification for state-, action- and reward spaces.
    """
    def __init__(self, add_batch_rank=False):
        """
        Args:
            add_batch_rank (bool): Whether to always add a batch rank at the 0th position when creating
                variables from this Space.
        """
        self._shape = None
        self.has_batch_rank = None
        self._add_batch_rank(add_batch_rank)

    def _add_batch_rank(self, add_batch_rank=False):
        """
        Recursively changes the add_batch_rank property of all child Spaces in this ContainerSpace.

        Args:
            add_batch_rank (bool): Whether this ContainerSpace and all it's children should have a batch rank.
        """
        self.has_batch_rank = add_batch_rank

    def with_batch_rank(self, add_batch_rank=True):
        """
        Returns a deepcopy of this Space, but with `has_batch_rank` set to True. This is useful for using
        an Env's (state|action)-Space for constructing Agent objects.

        Returns:
            Space: The deepcopy of this Space, but with `has_batch_rank` set to True.
        """
        ret = copy.deepcopy(self)
        ret._add_batch_rank(add_batch_rank)
        return ret

    def batched(self, samples):
        """
        Makes sure that `samples` is always returned with a batch rank no matter whether
        it already has one or not (in which case this method returns a batch of 1) or
        whether this Space has a batch rank or not.

        Args:
            samples (any): The samples to be batched. If already batched, return as-is.

        Returns:
            any: The batched sample.
        """
        return NotImplementedError

    @property
    def shape(self):
        """
        Returns:
            tuple: The shape of this Space as a tuple. Without batch (or other) ranks.
        """
        raise NotImplementedError

    def get_shape(self, with_batch_rank=False, **kwargs):
        """
        Returns the shape of this Space as a tuple with certain additional ranks at the front (batch) or the back
        (e.g. categories).

        Args:
            with_batch_rank (Union[bool,int]): Whether to include a possible batch-rank as `None` at 0th position.
                If `with_batch_rank` is -1, the possible batch-rank is returned as -1 (instead of None) at the 0th
                position.
                Default: False.

        Returns:
            tuple: The shape of this Space as a tuple.
        """
        raise NotImplementedError

    @property
    def rank(self):
        """
        Returns:
            int: The rank of the Space (e.g. 3 for a space with shape=(10, 7, 5)).
        """
        return len(self.shape)

    @property
    def flat_dim(self):
        """
        Returns:
            int: The dimension of the flattened vector of the tensor representation.
        """
        raise NotImplementedError

    @property
    def dtype(self):
        """
        Returns:
            str: The dtype (as string) of this Space.
                Can be converted to tf/np/python dtypes via the utils.dtype function. Tf seems to understand
                strings as well, though.
        """
        raise NotImplementedError

    def get_tensor_variable(self, name, is_input_feed=False, add_batch_rank=None, **kwargs):
        """
        Returns a backend-specific variable/placeholder that matches the space's shape.

        Args:
            name (str): The name for the variable.
            is_input_feed (bool): Whether the returned object should be an input placeholder,
                instead of a full variable.
            add_batch_rank (Optional[bool,int]): If True, will add a 0th rank (None) to
                the created variable. If it is an int, will add that int (-1 means None).
                If None, will use the Space's default value: `self.add_batch_rank`.
                Default: None.

        Keyword Args:
            To be passed on to backend-specific methods (e.g. trainable, initializer, etc..).

        Returns:
            any: A Tensor Variable/Placeholder.
        """
        raise NotImplementedError

    def flatten(self, mapping=None, _scope=None, _list=None):
        """
        A mapping function to flatten this Space into an OrderedDict whose only values are
        primitive (non-container) Spaces. The keys are created automatically from Dict keys and
        Tuple indexes.

        Args:
            mapping (Optional[callable]): A mapping function that takes a flattened auto-generated key and a primitive
                Space and converts the primitive Space to something else. Default is pass through.
            _scope (Optional[str]): For recursive calls only. Used for automatic key generation.
            _list (Optional[list]): For recursive calls only. The list so far.

        Returns:
            OrderedDict: The OrderedDict using auto-generated keys and containing only primitive Spaces
                (or whatever the mapping function maps the primitive Spaces to).
        """
        # default: no mapping
        if mapping is None:
            def mapping(key, x):
                return x

        # Are we in the non-recursive (first) call?
        ret = False
        if _list is None:
            _list = list()
            ret = True
            _scope = ""

        self._flatten(mapping, _scope, _list)

        # Non recursive (first) call -> Return the final FlattenedDataOp.
        if ret:
            return OrderedDict(_list)

    def _flatten(self, mapping, _scope, _list):
        """
        Base implementation. May be overridden by ContainerSpace classes.
        Simply sends `self` through the mapping function.

        Args:
            mapping (callable): The mapping function to use on a primitive (non-container) Space.
            _scope (str): The key to use to store the mapped result in list_ (which will be converted into
                an FlattenedDataOp at the very end).
            _list (list): The list to append the mapped results to (under key=`scope_`).
        """
        _list.append(tuple([_scope, mapping(_scope, self)]))

    def __repr__(self):
        return "Space(shape=" + str(self.shape) + ")"

    def __eq__(self, other):
        raise NotImplementedError

    def sample(self, size=None):
        """
        Uniformly randomly samples an element from this space. This is for testing purposes, e.g. to simulate
        a random environment.

        Args:
            size (Optional[int]): The number of samples or batch size to sample.
                If size is > 1: Returns a batch of size samples with the 0th rank being the batch rank
                    (even if `self.has_batch_rank` is False).
                If size is None or (1 and self.has_batch_rank is False): Returns a single sample w/o batch rank.
                If size is 1 and self.has_batch_rank is True: Returns a single sample w/ the batch rank.

        Returns:
            any: The sampled element(s).
        """
        raise NotImplementedError

    def _get_np_shape(self, num_samples=None):
        """
        Helper to determine, which shape one should pass to the numpy random funcs for sampling from a Space.
        Depends on num_samples, the shape of this Space and the add_batch_rank setting.

        Args:
            num_samples (Optional[int]): Number of samples to pull. If None or 0, pull 1 sample, but without batch rank
                (no matter what the value of `self.has_batch_rank` is).

        Returns:
            Tuple[int]: Shape to use for numpy random sampling.
        """
        # No batch rank.
        if not num_samples or (num_samples == 1 and not self.has_batch_rank):
            if len(self.shape) == 0:
                return None
            else:
                return self.shape
        # With batch rank.
        else:
            return tuple((num_samples,) + self.shape)

    def contains(self, sample):
        """
        Checks whether this space contains the given sample. This is more for testing purposes.

        Args:
            sample: The element to check.

        Returns:
            bool: Whether sample is a valid member of this space.
        """
        raise NotImplementedError
