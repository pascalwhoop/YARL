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

import os
import tensorflow as tf
from tensorflow.python.client import device_lib

from yarl.graphs.graph_executor import GraphExecutor
from yarl.backend_system import get_distributed_backend
import yarl.utils as util


class TensorFlowExecutor(GraphExecutor):
    """
    A Tensorflow executioner manages execution via TensorFlow sessions.
    """

    def __init__(self, **kwargs):
        super(TensorFlowExecutor, self).__init__(**kwargs)
        self.global_training_timestep = None

        # The tf.Graph object to be run in a tf session.
        self.graph = None
        # Saver.
        self.saver = None
        self.saver_directory = None

        # tf.Scaffold.
        self.scaffold = None

        # The Server (for distributed mode).
        self.server = None  # The tf.Server object (if any).

        # Summary settings.
        self.summary_writer = None
        # self.summary_configuration_op = None
        # The merged summary op to be used by the session to write the summaries.
        self.summary_op = None

        # The session for the computation graph.
        self.session = None
        self.monitored_session = None

        self.graph_default_context = None
        self.local_device_protos = device_lib.list_local_devices()
        self.available_devices = [x.name for x in self.local_device_protos]

        # Tf profiler.
        self.session_options = tf.RunOptions(trace_level=tf.RunOptions.FULL_TRACE)
        self.run_metadata = tf.RunMetadata()

        # Tf Profiler config.
        self.profiling_enabled = self.execution_spec["enable_profiler"]
        if self.profiling_enabled is True:
            self.profiler = None
            self.profile_step = 0
            self.profiling_frequency = self.execution_spec["profiler_frequency"]

        # Default device is first available CPUs
        default_device = self.execution_spec.get("default_device", None)
        if default_device is None:
            self.default_device = [x.name for x in self.local_device_protos if x.device_type == 'CPU'][0]
        else:
            self.default_device = default_device

        # # Initialize distributed backend.
        # distributed_backend_ = self.execution_spec.get("distributed_backend", "distributed_tf")
        #
        # self.logger.info("Updating global distributed backend setting with backend {}".format(distributed_backend_))
        # set_distributed_backend(distributed_backend_)

    def build(self):
        # Prepare for graph assembly.
        self.init_execution()
        self.setup_graph()

        # Assemble graph via graph builder.
        self.graph_builder.build_graph_from_meta_graph(self.available_devices, self.default_device)

        # Set up any remaining session or monitoring configurations.
        self.finish_graph_setup()

    def execute(self, sockets, inputs=None):
        fetch_list, feed_dict = self.graph_builder.get_execution_inputs(output_socket_names=sockets, inputs=inputs)
        ret = self.monitored_session.run(fetch_list, feed_dict=feed_dict,
                                         options=self.session_options, run_metadata=self.run_metadata)

        if self.profiling_enabled:
            self.update_profiler_if_necessary()
        if len(fetch_list) == 1:
            return ret[0]
        else:
            return ret

    def update_profiler_if_necessary(self):
        """
        Updates profiler according to specification.
        """
        if self.profile_step % self.profiling_frequency == 0:
            self.profiler.add_step(self.profile_step, self.run_metadata)
            self.profiler.profile_operations(
                options=tf.profiler.ProfileOptionBuilder(
                    options=tf.profiler.ProfileOptionBuilder.time_and_memory()).with_node_names().build()
            )
        self.profile_step += 1

    def read_variable_values(self, variables):
        """
        Fetches the given variables from the graph and returns their current values.
        The returned structure corresponds to the data type and structure of `variables`
        (e.g. if a dict with variables as values comes in, a dict with the same keys and current values as values
        is returned).

        Args:
            variables (any): Any structure that contains variables.

        Returns:
            any: Values of the given variables in the exact same structure as `variables`.
        """
        self.logger.debug('Fetching values of variables {} from graph.'.format(variables))
        return self.monitored_session.run(variables, feed_dict=dict())

    def init_execution(self):
        """
        Creates and stores a tf server (and optionally joins it if we are a parameter-server).
        Only relevant, if we are running in distributed mode.
        """
        if self.execution_mode == "distributed":
            if get_distributed_backend() == "distributed_tf":
                self.setup_distributed_tf()
            elif get_distributed_backend() == "horovod":
                self.setup_horovod_execution()

    def setup_distributed_tf(self):
        """
        Sets up distributed TensorFlow.
        """
        self.logger.info("Setting up distributed TensorFlow execution mode.")
        # Create the Server object.
        self.server = tf.train.Server(
            server_or_cluster_def=self.distributed_spec["cluster_spec"],
            job_name=self.distributed_spec["job"],
            task_index=self.distributed_spec["task_index"],
            protocol=self.distributed_spec.get("protocol"),
            config=self.distributed_spec.get("session_config"),
            start=True
        )
        if self.distributed_spec["job"] == "ps":
            # Just join and be done.
            self.logger.info("Job is parameter server, joining and waiting.")
            self.server.join()
            quit()

    def setup_horovod_execution(self):
        """
        Sets up Horovod.
        """
        # Check again to avoid import if unset which will crash if horovod is not installed.
        if get_distributed_backend() == "horovod":
            import horovod.tensorflow as hvd
            self.logger.info("Setting up Horovod execution.")
            hvd.init()
            config = tf.ConfigProto()
            config.gpu_options.visible_device_list = str(hvd.local_rank())
        
    def get_available_devices(self):
        return self.available_devices

    def get_device_assignments(self, device_names=None):
        if device_names is None:
            return self.graph_builder.device_component_assignments
        else:
            assignments = dict()
            for device in self.graph_builder.device_component_assignments:
                if device in device_names:
                    assignments[device] = self.graph_builder.device_component_assignments[device]
            return assignments

    def setup_graph(self):
        # Generate the tf-Graph object and enter its scope as default graph.
        self.graph = tf.Graph()
        self.graph_default_context = self.graph.as_default()
        self.graph_default_context.__enter__()
        # Set the random seed graph-wide.
        if self.seed is not None:
            self.logger.info("Initializing TensorFlow graph with seed {}".format(self.seed))
            tf.set_random_seed(self.seed)

    def finish_graph_setup(self):
        # After the graph is built -> Setup saver, summaries, etc..
        hooks = []  # Will be appended to in the following functions.
        self.setup_saver(hooks)
        self.setup_summaries(hooks)
        self.setup_scaffold()

        # Finalize our graph, create and enter the session.
        self.setup_session(hooks)

    def setup_saver(self, hooks):
        """
        Creates the tf.train.Saver object and stores it in self.saver.

        Args:
            hooks (list): List of hooks to use for Saver and Summarizer in Session. Should be appended to.
        """
        self.saver = tf.train.Saver(
            var_list=list(self.graph_builder.core_component.variables.values()),
            reshape=False,
            sharded=False,
            max_to_keep=self.saver_spec["max_checkpoints"],  # TODO: open question: how to handle settings?
            keep_checkpoint_every_n_hours=10000.0,
            name=None,
            restore_sequentially=False,
            saver_def=None,
            builder=None,
            defer_build=False,
            allow_empty=True,
            write_version=tf.train.SaverDef.V2,
            pad_step_number=False,
            save_relative_paths=True,
            filename=None
        )

        # Add saver hook to session.
        if self.execution_mode == "single" or self.distributed_spec["task_index"] == 0:
            self.saver_directory = self.saver_spec["directory"]
            saver_hook = tf.train.CheckpointSaverHook(
                checkpoint_dir=self.saver_directory,
                # Either save_secs or save_steps must be set.
                save_secs=self.saver_spec["save_secs"],  # TODO: open question: how to handle settings?
                save_steps=self.saver_spec["save_steps"],
                saver=self.saver,
                checkpoint_basename=self.saver_spec["checkpoint_basename"],  # TODO: open question: how to handle settings?
                scaffold=None,  # None since not created yet.
                listeners=None
            )
            hooks.append(saver_hook)

    def setup_summaries(self, hooks):
        """
        Sets up tf.summary ops generated during the build of the graph inside the different Components.

        Args:
            hooks (list): List of hooks to use for Saver and Summarizer in Session. Should be appended to.
        """
        # Create our tf summary writer object.
        self.summary_writer = tf.summary.FileWriter(
            logdir=self.summary_spec["directory"],
            graph=self.graph,
            max_queue=10,
            flush_secs=120,
            filename_suffix=None
        )

        # Creates a single summary op to be used by the session to write the summary files.
        summary_list = list(self.graph_builder.core_component.summaries.values())
        if len(summary_list) > 0:
            self.summary_op = tf.summary.merge(inputs=summary_list)

            # Create an update saver hook for our summaries.
            summary_saver_hook = tf.train.SummarySaverHook(
                save_steps=self.summary_spec["save_steps"],  # Either one or the other has to be set.
                save_secs=self.summary_spec["save_secs"],
                output_dir=None,  # None since given via 'summary_writer' argument.
                summary_writer=self.summary_writer,
                scaffold=None,  # None since summary_op given directly here.
                summary_op=self.summary_op
            )
            # ... and append it to our list of hooks to use in the session.
            hooks.append(summary_saver_hook)

    def setup_scaffold(self):
        """
        Creates a tf.train.Scaffold object to be used by the session to initialize variables and to save models
        and summaries.
        Assigns the scaffold object to `self.scaffold`.
        """
        if self.execution_mode == "single":
            var_list = list(self.graph_builder.core_component.variables.values())
            init_op = tf.variables_initializer(var_list=var_list)
            ready_op = tf.report_uninitialized_variables(var_list=var_list)
        else:
            # TODO: Distributed tf scaffold.
            init_op = None
            ready_op = None

        def init_fn(scaffold, session):
            # NOTE: `self.load_from_file` is either True or a string value.
            # - No specific file given -> Use latest checkpoint.
            if self.load_from_file is True:
                file = tf.train.latest_checkpoint(
                    checkpoint_dir=self.saver_spec["directory"],
                    latest_filename=None
                )
            # - File given -> Look for it in cwd, then in our checkpoint directory.
            else:
                assert isinstance(self.load_from_file, str)
                file = self.load_from_file
                if not os.path.isfile(file):
                    file = os.path.join(self.saver_spec["directory"], self.load_from_file)

            if file is not None:
                scaffold.saver.restore(sess=session, save_path=file)

        # Create the tf.train.Scaffold object.
        self.scaffold = tf.train.Scaffold(
            init_op=init_op,
            init_feed_dict=None,
            init_fn=init_fn if self.load_from_file else None,
            ready_op=ready_op,
            ready_for_local_init_op=None,
            local_init_op=None,
            summary_op=self.summary_op,
            saver=self.saver,
            copy_from_scaffold=None
        )

    def setup_session(self, hooks):
        """
        Creates and then enters the session for this model. Also finalizes the graph.

        Args:
            hooks (list): A list of session hooks to use.
        """
        if self.execution_mode == "distributed":
            self.logger.info("Setting up distributed TensorFlow session.")
            session_creator = tf.train.ChiefSessionCreator(
                scaffold=self.scaffold,
                master=self.server.target,
                config=self.session_config,
                checkpoint_dir=None,
                checkpoint_filename_with_path=None
            )
            self.monitored_session = tf.train.MonitoredSession(
                session_creator=session_creator,
                hooks=hooks,
                stop_grace_period_secs=120  # Default value.
            )
        else:
            self.logger.info("Setting up singular monitored session for non-distributed mode.")
            self.global_training_timestep = tf.get_variable(
                name="global-timestep", dtype=util.dtype("int"), trainable=False, initializer=0,
                collections=["global-timestep", tf.GraphKeys.GLOBAL_STEP])
            self.monitored_session = tf.train.SingularMonitoredSession(
                hooks=hooks,
                scaffold=self.scaffold,
                master='',  # Default value.
                config=self.session_config,
                checkpoint_dir=None
            )

        # Exit the graph-context and finalize the graph.
        if self.graph_default_context is not None:
            self.graph_default_context.__exit__(None, None, None)
        self.graph.finalize()

        # Enter the session to be ready for acting/learning.
        self.monitored_session.__enter__()
        self.session = self.monitored_session._tf_sess()

        # Setup the tf Profiler.
        if self.profiling_enabled:
            self.profiler = tf.profiler.Profiler(graph=self.session.graph)

    def load_model(self, path=None):
        pass

    def store_model(self, path=None, add_timestep=True):
        if self.summary_writer is not None:
            self.summary_writer.flush()

        self.saver.save(
            sess=self.session,
            save_path=(path or self.saver_directory),
            # TODO: global_timestep
            global_step=(self.global_training_timestep if add_timestep is False else None),
            latest_filename=None,
            meta_graph_suffix="meta",
            write_meta_graph=True,
            write_state=True
        )
        self.logger.info("Stored model to path: {}".format(path))

    def export_graph_definition(self, filename):
        """
        Exports TensorFlow meta graph to file.

        Args:
            filename (str): File to save meta graph. Should end in .meta
        """
        if not filename.endswith('.meta'):
            self.logger.warn('Filename for TensorFlow meta graph should end with .meta.')
        self.saver.export_meta_graph(filename=filename)

    def get_weights(self):
        # Default out-socket pulls on variables.
        return self.execute(sockets="_variables")

    def set_weights(self, weights):
        # Note that this can only assign components which have been declared synchronizable.
        self.execute(sockets="sync", inputs=dict(sync_in=weights))