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

import os
from setuptools import setup, find_packages

# Read __version__ avoiding imports that might be in install_requires
version_vars = dict()
with open(os.path.join(os.path.dirname(__file__), 'yarl', 'version.py')) as fp:
    exec(fp.read(), version_vars)

install_requires = [
    'cached_property',
    'numpy',
    'pyyaml',
    'pytest',
    'six',
    'tensorflow',
    'requests'
]

setup_requires = []

extras_require = {
    'gym': 'gym',
    'horovod': 'horovod',
    'pytorch': 'pytorch',
    'ray': 'ray'
}

setup(
    name='yarl',
    version=version_vars['__version__'],
    description='A Framework for Flexible Deep Reinforcement Learning Graphs',
    url='https://yarl-project.org',
    author='yarl',
    author_email='yarl@yarl-project.org',
    license='Apache 2.0',
    packages=[package for package in find_packages() if package.startswith('yarl')],
    install_requires=install_requires,
    setup_requires=setup_requires,
    extras_require=extras_require,
    zip_safe=False
)
