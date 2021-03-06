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
from yarl.components import Component
from yarl.spaces import ContainerSpace

if get_backend() == "tf":
    import tensorflow as tf


class Distribution(Component):
    """
    A distribution wrapper class that can incorporate a backend-specific distribution object that gets its parameters
    from an external source (e.g. a NN).

    API:
    ins:
        parameters (numeric): The parameters of the distribution (e.g. mean and variance for a Gaussian).
            The Space of parameters must have a batch-rank.
        values (numeric): Values for which we want log probabilities returned.
        max_likelihood (bool): Whether to sample or to get the max-likelihood value (deterministic) when
            using the "draw" out-Socket. This Socket is optional and can be switched on via the constructor parameter:
            "expose_draw"=True.
        other_distribution (backend-specific distribution object): Input distribution for calculating the
            KL-divergence between this Distribution and "other_distribution".
    outs:
        sample_stochastic (numeric): Returns a stochastic sample from the distribution.
        sample_deterministic (numeric): Returns the max-likelihood value (deterministic) from the distribution.
        entropy (float): The entropy value of the distribution.
        log_prob (numeric): The log probabilities for given values.
        draw (numeric): Draws a sample from the distribution (if max_likelihood is True, this is will be
            a deterministic draw, otherwise a stochastic sample). This Socket is optional and can be switched on via
            the constructor parameter: "expose_draw"=True. By default, this Socket is not exposed.
        kl_divergence (numeric): The Kullback-Leibler Divergence between this Distribution and another one.
    """
    def __init__(self, scope="distribution", **kwargs):
        super(Distribution, self).__init__(scope=scope, **kwargs)

        # Define a generic Distribution interface.
        self.define_inputs("parameters", "values", "other_distribution", "max_likelihood")
        self.define_outputs("sample_stochastic", "sample_deterministic", "draw", "entropy", "log_prob", "distribution")

        # "distribution" will be an internal Socket used to connect the GraphFunctions with each other.
        self.add_graph_fn("parameters", "distribution", self._graph_fn_parameterize)
        self.add_graph_fn("distribution", "sample_stochastic", self._graph_fn_sample_stochastic)
        self.add_graph_fn("distribution", "sample_deterministic", self._graph_fn_sample_deterministic)
        self.add_graph_fn("distribution", "entropy", self._graph_fn_entropy)
        self.add_graph_fn(["distribution", "values"], "log_prob", self._graph_fn_log_prob)
        self.add_graph_fn(["distribution", "other_distribution"], "kl_divergence", self._graph_fn_kl_divergence)
        self.add_graph_fn(["distribution", "max_likelihood"], "draw", self._graph_fn_draw)

        # Make some in-Sockets optional (don't need to be connected; will not sanity check these).
        self.unconnected_sockets_in_meta_graph.update(["values", "max_likelihood", "other_distribution"])

    def check_input_spaces(self, input_spaces, action_space):
        in_space = input_spaces["parameters"]
        # Must not be ContainerSpace (not supported yet for Distributions, doesn't seem to make sense).
        assert not isinstance(in_space, ContainerSpace), "ERROR: Cannot handle container input Spaces " \
                                                         "in distribution '{}' (atm; may soon do)!".format(self.name)

    def _graph_fn_parameterize(self, *parameters):
        """
        Parameterizes this distribution (normally from an NN-output vector). Returns
        the backend-distribution object (a DataOp).

        Args:
            *parameters (DataOp): The input(s) used to parameterize this distribution. This is normally a cleaned up
                single NN-output that (e.g.: the two values for mean and variance for a univariate Gaussian
                distribution).

        Returns:
            DataOp: The parameterized backend-specific distribution object.
        """
        raise NotImplementedError

    def _graph_fn_draw(self, distribution, max_likelihood):
        """
        Takes a sample from the (already parameterized) distribution. The parameterization also includes a possible
        batch size.

        Args:
            distribution (DataOp): The (already parameterized) backend-specific distribution DataOp to use for
                sampling. This is simply the output of `self._graph_fn_parameterize`.
            max_likelihood (bool): Whether to return the maximum-likelihood result, instead of a random sample.
                Can be used to pick deterministic actions from discrete ("greedy") or continuous (mean-value)
                distributions.

        Returns:
            DataOp: The taken sample(s).
        """
        if get_backend() == "tf":
            return tf.cond(
                pred=max_likelihood,
                true_fn=lambda: self._graph_fn_sample_deterministic(distribution),
                false_fn=lambda: self._graph_fn_sample_stochastic(distribution)
            )

    def _graph_fn_sample_deterministic(self, distribution):
        """
        Returns the maximum-likelihood value for a given distribution.

        Args:
            distribution (DataOp): The (already parameterized) backend-specific distribution whose max-likelihood value
                to calculate. This is simply the output of `self._graph_fn_parameterize`.

        Returns:
            DataOp: The max-likelihood value.
        """
        raise NotImplementedError

    @staticmethod
    def _graph_fn_sample_stochastic(distribution):
        """
        Returns an actual sample for a given distribution.

        Args:
            distribution (DataOp): The (already parameterized) backend-specific distribution from which a sample
                should be drawn. This is simply the output of `self._graph_fn_parameterize`.

        Returns:
            DataOp: The drawn sample.
        """
        return distribution.sample()

    @staticmethod
    def _graph_fn_log_prob(distribution, values):
        """
        Probability density/mass function.

        Args:
            distribution (DataOp): The (already parameterized) backend-specific distribution for which the log
                probabilities should be calculated. This is simply the output of `self._graph_fn_parameterize`.
            values (SingleDataOp): Values for which to compute the log probabilities given `distribution`.

        Returns:
            DataOp: The log probability of the given values.
        """
        if get_backend() == "tf":
            return distribution.log_prob(value=values)

    @staticmethod
    def _graph_fn_entropy(distribution):
        """
        Returns the DataOp holding the entropy value of the distribution.

        Args:
            distribution (DataOp): The (already parameterized) backend-specific distribution whose entropy to
                calculate. This is simply the output of `self._graph_fn_parameterize`.

        Returns:
            DataOp: The distribution's entropy.
        """
        return distribution.entropy()

    @staticmethod
    def _graph_fn_kl_divergence(distribution_a, distribution_b):
        """
        Kullback-Leibler divergence between two distribution objects.

        Args:
            distribution_a (tf.Distribution): A Distribution object.
            distribution_b (tf.Distribution): A distribution object.

        Returns:
            DataOp: (batch-wise) KL-divergence between the two distributions.
        """
        if get_backend() == "tf":
            return tf.no_op()
            # TODO: never tested. tf throws error: NotImplementedError: No KL(distribution_a || distribution_b) registered for distribution_a type Bernoulli and distribution_b type ndarray
            #return tf.distributions.kl_divergence(
            #    distribution_a=distribution_a,
            #    distribution_b=distribution_b,
            #    allow_nan_stats=True,
            #    name=None
            #)
