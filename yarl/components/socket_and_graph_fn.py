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

import itertools
from collections import OrderedDict
import re

from yarl import YARLError
from yarl.spaces import Space
from yarl.utils.util import force_tuple
from yarl.utils.ops import SingleDataOp, FlattenedDataOp
from yarl.spaces.space_utils import flatten_op, get_space_from_op, unflatten_op


class Socket(object):
    """
    A Socket object describes a connection to other Sockets, GraphFunctions, or Spaces inside and between ModelComponents.
    One Socket either carries:

    - a single op (e.g. some tensor)
    - a tuple of ops (nesting also supported)
    - a dict of ops (nesting also supported)

    Also, each of the above possibilities can have many parallel solutions. These splits happen e.g. if two Sockets
    connect to the same target Socket. In this case, the target Socket's inputs are treated as possible alternatives
    and the Socket then implicitly produces two outputs that it further passes on to the next Sockets/GraphFunctions.

    When connected to a GraphFunction object, a Socket always represents one of the input parameters to the graph_fn
    method. Also, each returned value of a graph_fn method corresponds to one Socket.
    """
    def __init__(self, name, component, type_="in"):
        """
        Args:
            name (str): The name of this Socket (as it will show in the final call interface).
            component (Component): The Component object that this Socket belongs to.
            type_ (str): The Socket type: "in" or "out".
        """
        # The name of this Socket.
        self.name = name
        # "in" or "out"
        self.type = type_
        # The Component that this Socket belongs to.
        self.component = component

        # Which other socket(s), space(s), graph_fn(s) are we connected to on the incoming and outgoing side?
        # - Records in these lists have a parallel relationship (they are all alternatives to each other).
        # - Each record is either:
        #   - another Socket
        #   - a Space
        #   - a dict of: {graph_fn-method, slot for this socket, [required input sockets], [output sockets]}
        self.incoming_connections = list()
        self.outgoing_connections = list()

        # The inferred Space coming into this Socket.
        # TODO: Make sure all incoming connections have the same Space.
        self.space = None

        ## Support for in-Sockets that always feed a constant value. Useful for setting default parameters for
        ## _graph functions.
        #self.constant_value = False

        # The set of (alternative) ops (dictop, tuple or primitive) that this socket carries. Populated at build time.
        self.ops = set()

    # A+B -> comp -> C+D -> C -> E (which also gets an alternative input from G) AND D -> F
    # A arrives -> wait (no B yet)
    # b arrives -> comp(A,b) -> C1+D1(given A+b)
    # a arrives -> comp(a,b) -> C2+D2(given a+b)
    # B arrives -> comp(a,B) -> C3+D3(given a+B) AND comp(A,B) -> C4+D4(given A+B)
    # now we have C with ops: {opC1: [A,b], opC2: [a,b], opC3: [a,B], opC4:[A,B]}
    # same for D
    # E: incoming_connections: [C, G] -> pass on ops from C to E (just copy!) and concat(!) with all ops from G
    # expose E as interface and make it "callable", then pull ops depending on input given (e.g. [a,b] -> pull opC2).
    def connect_to(self, to_):
        if to_ not in self.outgoing_connections:
            self.outgoing_connections.append(to_)

    def disconnect_to(self, to_):
        if to_ in self.outgoing_connections:
            self.outgoing_connections.remove(to_)

    def connect_from(self, from_):
        if from_ not in self.incoming_connections:
            # We need to set this flag here to be able to determine, whether a graph_fn is a no-input
            # (or constant-values-only) graph_fn.
            if isinstance(from_, SingleDataOp):
                self.component.no_input_entry_points.append(self)
            self.incoming_connections.append(from_)

    def disconnect_from(self, from_):
        if from_ in self.incoming_connections:
            if isinstance(from_, SingleDataOp):
                self.component.no_input_entry_points.remove(self)
            self.incoming_connections.remove(from_)

    def update_from_input(self, incoming, op_registry, in_socket_registry, graph_fn_in_slot=None,
                          socket_in_op=None):
        """
        Updates this socket based on an incoming connection (from a Space or GraphFunction or another Socket).

        Args:
            incoming (Union[Space,GraphFunction,Socket]): The incoming item.
            op_registry (dict): Dict that keeps track of which ops require which other ops to be calculated.
            in_socket_registry (dict): Dict that keeps track of which very in-Socket (name) needs which
                ops (placeholders/feeds).
            graph_fn_in_slot (Optional[int]): If incoming is a GraphFunction, which output slot does this Socket
                connect to?
            socket_in_op (Optional[op]): If incoming is a Socket, this may hold a single op that we should
                build from. If None and incoming is Socket, update all.

        Raises:
            YARLError: If there is an attempt to connect more than one Space to this Socket.
        """
        # Space: generate backend-ops.
        if isinstance(incoming, Space):
            if self.space is not None:
                raise YARLError("ERROR: A Socket can only have one incoming Space!")
            op = incoming.get_tensor_variable(name=self.name, is_input_feed=True)
            # Add new DataOp to our set of (alternative) DataOps.
            self.ops.add(op)
            # Keep track of which Spaces can go (alternatively) into this Socket.
            in_socket_registry[self.name] = {op} if self.name not in in_socket_registry \
                else (in_socket_registry[self.name] | {op})
            # Remember, that this DataOp goes into a Socket at the very beginning of the Graph (e.g. a tf.placeholder).
            op_registry[op] = {self}
            # Store this Space as our incoming Space.
            self.space = incoming
        # GraphFunction: Connect this Socket to the nth op coming out of the GraphFunction function.
        elif isinstance(incoming, GraphFunction):
            assert isinstance(graph_fn_in_slot, int) and graph_fn_in_slot >= 0, \
                "ERROR: If incoming is a GraphFunction, slot must be set and >=0!"
            # Add every nth op from the output of the completed call to graph_fn to this Socket's set of ops.
            nth_computed_ops = list()
            for outputs in incoming.processed_ops.values():
                nth_computed_ops.append(outputs[graph_fn_in_slot])

            # Store incoming Space.
            # TODO: Maybe check whether all incoming ops have same Space.
            if self.space is None:
                if len(nth_computed_ops) > 0:
                    self.space = get_space_from_op(next(iter(nth_computed_ops)))
                else:
                    self.space = 0

            self.ops.update(nth_computed_ops)
        # Incoming is another Socket -> Simply update ops from this one.
        elif isinstance(incoming, Socket):
            # Update given op or all (it's a set, so no harm).
            self.ops.update(socket_in_op or incoming.ops)
            self.space = incoming.space
            self.component.check_input_completeness()
        # Constant DataOp with a value.
        elif isinstance(incoming, SingleDataOp):
            self.ops.update([incoming])
            if len(self.ops) > 1:
                raise YARLError("ERROR: A constant-value Socket may only have one such incoming value! Socket '{}' "
                                "already has {} other incoming connections.".format(self.name,
                                                                                    len(self.incoming_connections)))
            self.space = get_space_from_op(incoming)
            self.component.check_input_completeness()
        else:
            raise YARLError("ERROR: Incoming must be another Socket, a Space, a GraphFunction, or a constant numeric "
                            "scalar value or array!")

    def __str__(self):
        return "{}-Socket('{}/{}'{})".format(self.type, self.component.scope, self.name,
                                             " dev='{}'".format(self.component.device) if self.component.device else "")


class GraphFunction(object):
    """
    Class describing a segment of the graph defined by a _graph_fn-method inside a Component.
    A GraphFunction is connected to incoming Sockets (these are the input parameters to the _graph-func) and to
    outgoing Sockets (these are the return values of the _graph func).
    Implements the update_from_input method which checks whether all necessary inputs to a graph_fn
    are given and - if yes - starts producing output ops from these inputs and the graph_fn to be passed
    on to the outgoing Sockets.
    """
    def __init__(self, method, component, input_sockets, output_sockets,
                 flatten_ops=True, split_ops=True,
                 add_auto_key_as_first_param=False, unflatten_ops=True):
        """
        Args:
            method (Union[str,callable]): The method of the graph_fn (must be the name (w/o _graph prefix)
                of a method in `component` or directly a callable.
            component (Component): The Component object that this GraphFunction belongs to.
            input_sockets (List[Socket]): The required input Sockets to be passed as parameters into the
                graph_fn. In the order of graph_fn's parameters.
            output_sockets (List[socket]): The Sockets associated with the return values coming from the graph_fn.
                In the order of the returned values.
            flatten_ops (Union[bool,Set[str]]): Whether to flatten all or some DataOps by creating
                a FlattenedDataOp (with automatic key names).
                Can also be a set of in-Socket names to flatten explicitly (True for all).
                (default: True).
            split_ops (Union[bool,Set[str]]): Whether to split all or some of the already flattened DataOps
                and send the SingleDataOps one by one through the graph_fn.
                Example: in-Sockets=A=Dict (container), B=int (primitive)
                    The graph_fn should then expect for each primitive Space in A:
                        _graph_func(primitive-in-A (Space), B (int))
                        NOTE that B will be the same in all calls for all primitive-in-A's.
                (default: True).
            add_auto_key_as_first_param (bool): If `split_ops` is not False, whether to send the
                automatically generated flat key as the very first parameter into each call of the graph_fn.
                Example: in-Sockets=A=float (primitive), B=Tuple (container)
                    The graph_fn should then expect for each primitive Space in B:
                        _graph_func(key, A (float), primitive-in-B (Space))
                        NOTE that A will be the same in all calls for all primitive-in-B's.
                        The key can now be used to index into variables equally structured as B.
                Has no effect if `split_ops` is False.
                (default: False).
            unflatten_ops (bool): Whether to re-establish a nested structure of DataOps
                for graph_fn-returned FlattenedDataOps.
                (default: True)

        Raises:
            YARLError: If a graph_fn with the given name cannot be found in the component.
        """

        # The component object that the method belongs to.
        self.component = component

        self.flatten_ops = flatten_ops
        self.split_ops = split_ops
        self.add_auto_key_as_first_param = add_auto_key_as_first_param
        self.unflatten_ops = unflatten_ops

        if isinstance(method, str):
            self.name = method
            self.method = getattr(self.component, "_graph_fn_" + method, None)
            if not self.method:
                raise YARLError("ERROR: No `_graph_fn_...` method with name '{}' found!".format(method))
        else:
            self.method = method
            self.name = re.sub(r'^_graph_', "", method.__name__)

        # Dict-records for input-sockets (by name) to keep information on their position and "op-completeness".
        self.input_sockets = OrderedDict()
        for i, in_sock in enumerate(input_sockets):
            self.input_sockets[in_sock.name] = dict(socket=in_sock, pos=i, ops=set())
        # Just a list of Socket objects.
        self.output_sockets = output_sockets

        # Whether we have all necessary input-sockets for passing at least one input-op combination through
        # our computation method. As long as this is False, we return prematurely and wait for more ops to come in
        # (through other Sockets).
        self.input_complete = False
        # Registry for which incoming Sockets' ops we have already passed through the computation to generate
        # output ops.
        # key=tuple of input-ops combination (len==number of input params).
        # value=list of generated output ops (len==number of return values).
        self.processed_ops = dict()

    #def to_graph(self, method):
    #    """
    #    Converts function containing Python control flow to graph.
    #
    #    Args:
    #        method (callable): Function object containing computations and potentially control flow.
    #
    #    Returns:
    #        GraphFunction graph object.
    #    """
    #    return method  # not mandatory

    def update_from_input(self, input_socket, op_registry, in_socket_registry):
        """
        Updates our "waiting" inputs with the incoming socket and checks whether this computation is "input-complete".
        If yes, do all possible combinatorial pass-throughs through the computation function to generate output ops
        and assign these ops to our respective output sockets (first socket gets first output op, etc.. depending
        on how many return values the computation function has).

        Args:
            input_socket (Optional[Socket]): The incoming Socket (by design, must be type "in").
                None, if this GraphFunction has no in-Sockets anyway.
            op_registry (dict): Dict that keeps track of which ops require which other ops to be calculated.
            in_socket_registry (dict): Dict that keeps track of which in-Socket (name) needs which
                ops (placeholders/feeds).
        """
        assert input_socket is None or (isinstance(input_socket, Socket) and input_socket.type == "in"), \
            "ERROR: `input_socket` must be a Socket object and of type 'in'!"

        if input_socket is not None:
            # Update waiting_ops.
            record = self.input_sockets[input_socket.name]
            record["ops"].update(input_socket.ops)
            # Check for input-completeness.
            self.check_input_completeness()

            # No elif! We have to check again.
            # We are input-complete: Get all possible combinations of input ops and pass all these combinations through
            # the function (only those combinations that we didn't do yet).
            if self.input_complete:
                # Generate a list of all possible input op combinations.
                in_ops = [in_sock_rec["ops"] for in_sock_rec in self.input_sockets.values()]
                input_combinations = list(itertools.product(*in_ops))
                for input_combination in input_combinations:
                    input_combination_wo_constant_values = tuple([
                        op for op in input_combination if not isinstance(op, SingleDataOp)
                                                          or op.constant_value is None
                    ])

                    # key = tuple(input_combination)
                    # Make sure we call the computation method only once per input-op combination.
                    if input_combination_wo_constant_values not in self.processed_ops:
                        # Replace constant-value Sockets with their SingleDataOp's constant numpy values.
                        input_combination_w_constant_values = [
                            op.constant_value if isinstance(op, SingleDataOp) and op.constant_value is not None
                            else op for op in input_combination
                        ]
                        # Build the ops from this input-combination.
                        # - Flatten input items.
                        if self.flatten_ops is not False:
                            flattened_ops = self.flatten_input_ops(*input_combination_w_constant_values)
                            # Split into SingleDataOps?
                            if self.split_ops:
                                call_params = self.split_flattened_input_ops(*flattened_ops)
                                if isinstance(call_params, FlattenedDataOp):
                                    ops = FlattenedDataOp()
                                    for key, params in call_params.items():
                                        ops[key] = self.method(*params)
                                else:
                                    ops = self.method(*call_params)
                            else:
                                ops = self.method(*flattened_ops)
                        # - Just pass in everything as is.
                        else:
                            ops = self.method(*input_combination_w_constant_values)

                        # Need to un-flatten return values?
                        if self.unflatten_ops:
                            ops = self.unflatten_output_ops(*force_tuple(ops))

                        # Make sure everything coming from a computation is always a tuple (for out-Socket indexing).
                        ops = force_tuple(ops)

                        self.processed_ops[input_combination_wo_constant_values] = ops
                        # Keep track of which ops require which other ops.
                        for op in ops:
                            op_registry[op] = set(input_combination_wo_constant_values)
                    # TODO: Warn for now: should this even happen?
                    else:
                        print("input_combination '{}' already in self.processed_ops!".format(input_combination))
        # This GraphFunction has no in-Sockets.
        else:
            self.input_complete = True
            # Call the method w/o any parameters.
            ops = force_tuple(self.method())
            if ops == ():
                raise YARLError("ERROR: {}'s computation method '{}' does not return an op!".
                                format(self.component.name, self.method.__name__))
            self.processed_ops[()] = ops  # Use empty tuple as input-ops combination.
            # Tag all out-ops as not requiring any input.
            for op in ops:
                op_registry[op] = set()

        if self.input_complete:
            # Loop through our output Sockets and keep processing them with this computation's outputs.
            for slot, output_socket in enumerate(self.output_sockets):
                output_socket.update_from_input(self, op_registry, in_socket_registry, slot)

    def check_input_completeness(self):
        """
        Checks whether this GraphFunction is "input-complete" and stores the result in self.input_complete.
        Input-completeness is reached (only once and then it stays that way) if all in-Sockets to this computation
        have at least one op defined in their Socket.ops set.
        """
        if not self.input_complete:
            # Check, whether we are input-complete now (whether all in-Sockets have at least one op defined).
            self.input_complete = True
            for record in self.input_sockets.values():
                if len(record["ops"]) == 0:
                    self.input_complete = False
                    return

    def flatten_input_ops(self, *ops):
        """
        Flattens all DataOps in ops into FlattenedDataOp with auto-key generation.
        Ops whose Sockets are not in self.flatten_ops (if its a set)
        will be ignored.

        Args:
            *ops (DataOp): The items to flatten.

        Returns:
            tuple: All *ops as FlattenedDataOp.
        """
        # The returned sequence of output ops.
        ret = []
        in_socket_names = self.input_sockets.keys()
        for i, op in enumerate(ops):
            # self.flatten_ops cannot be False here.
            if self.flatten_ops is True or (isinstance(self.flatten_ops, set) and
                                            in_socket_names[i] in self.flatten_ops):
                ret.append(flatten_op(op))
            else:
                ret.append(op)

        # Always return a tuple for indexing into the return values.
        return tuple(ret)

    # TODO: Move this one into op_utils.py as well.
    def split_flattened_input_ops(self, *ops):
        """
        Splits any FlattenedDataOp in ops into its SingleDataOps and passes them
        one by one through the computation function. If more than one FlattenedDataOp exists in ops,
        these must have the exact same keys.
        If self.add_auto_key_as_first_param is True: Pass in auto-key as very first parameter into each
            call to computation func.

        Args:
            *ops (DataOp): The input items into this GraphFunction.

        Returns:
            FlattenedDataOp: The sorted parameter tuples (by flat-key) to use in the calls to the computation method.
            Tuple[DataOp]: If no FlattenedDataOp is in ops.

        Raises:
            YARLError: If there are more than 1 flattened ops in ops and their keys don't match 100%.
        """
        # Collect FlattenedDataOp for checking their keys (must match).
        flattened = [op.items() for op in ops if isinstance(op, FlattenedDataOp)]
        # If it's more than 1, make sure they match. If they don't match: raise Error.
        if len(flattened) > 1:
            # Loop through the first one and make sure all others match.
            for key, value in flattened[0]:
                for other in flattened[1:]:
                    k_other, v_other = next(iter(other))
                    if key != k_other:  # or get_shape(v_other) != get_shape(value):
                        raise YARLError("ERROR: Flattened ops have a key mismatch ({} vs {})!".format(key, k_other))

        # We have (matching) ContainerDataOps: Split the calls.
        if len(flattened) > 0:
            # The first op that is a FlattenedDataOp.
            guide_op = next(op for op in ops if isinstance(op, FlattenedDataOp))
            # Re-create our iterators.
            flattened = [op.items() if isinstance(op, FlattenedDataOp) else op for op in ops]
            collected_call_params = FlattenedDataOp()
            # Do the single split calls to our computation func.
            for key, value in guide_op.items():
                # Prep input params for a single call.
                params = [key, value] if self.add_auto_key_as_first_param else [value]
                # Pull along the other ops' values for the guide_op's current key
                # (all container ops match structure-wise).
                for other in flattened[1:]:
                    v_other = next(iter(other))[1]  # if isinstance(other, odict_items) else other
                    params.append(v_other)
                # Now do the single call.
                collected_call_params[key] = params
            return collected_call_params
        # We don't have any container ops: No splitting possible. Return as is.
        else:
            return ops

    @staticmethod
    def unflatten_output_ops(*ops):
        """
        Re-creates the originally nested input structure (as DataOpDict/DataOpTuple) of the given output ops.
        Process all FlattenedDataOp with auto-generated keys, and leave the others untouched.

        Args:
            *ops (DataOp): The ops that need to be re-nested (only process the FlattenedDataOp
                amongst these and ignore all others).

        Returns:
            Tuple[DataOp]: A tuple containing the ops as they came in, except that all FlattenedDataOp
                have been un-flattened (re-nested) into their original ContainerDataOp structures.
        """
        # The returned sequence of output ops.
        ret = []

        for i, op in enumerate(ops):
            # A FlattenedDataOp: Try to re-nest it and then compare it to input_template_op's structure.
            if isinstance(op, dict):  # allow any dict to be un-flattened
                ret.append(unflatten_op(op))
            # All others are left as-is.
            else:
                ret.append(op)

        # Always return a tuple for indexing into the return values.
        return tuple(ret)

    def __str__(self):
        return "{}('{}' in=[{}] out=[{}])". \
            format(type(self).__name__, self.name, str(self.input_sockets), str(self.output_sockets))


#class TfGraphFunction(GraphFunction):
#    """
#    TensorFlow computation.
#    """
#    def to_graph(self, method):
#        return autograph.to_graph(method, verbose=True)
