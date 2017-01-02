#!/usr/bin/env python

import json
import os

from setuptools import setup
from jupyter_client.kernelspec import KernelSpecManager
from IPython.utils.tempdir import TemporaryDirectory


def install_kernel_spec(user=True, prefix=None):
    kernel_json = {
        "argv": ["python", "-m", "imongo", "-f", "{connection_file}"],
        "codemirror_mode": "shell",
        "display_name": "IMongo"
    }
    with TemporaryDirectory() as td:
        os.chmod(td, 0o755)
        with open(os.path.join(td, 'kernel.json'), 'w') as f:
            json.dump(kernel_json, f, sort_keys=True)
        ksm = KernelSpecManager()
        ksm.install_kernel_spec(td, 'imongo', user=user, replace=True, prefix=prefix)


print('Installing Jupyter kernelspec')
install_kernel_spec()

with open('README.md', 'r') as f:
    long_description = f.read()

setup(name='imongo',
      version='0.1.0',
      description='A MongoDB kernel for Jupyter',
      long_description=long_description,
      author='Gustavo Bezerra',
      author_email='gusutabopb@gmail.com',
      url='https://github.com/gusutabopb/imongo',
      packages=['imongo'],
      license='MIT',
      install_requires=['jupyter>=1.0.0'],
      classifiers=[
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'Intended Audience :: Science/Research',
          'Development Status :: 3 - Alpha',
          'Programming Language :: Python :: 3',
          'Topic :: System :: Shells',
      ])
