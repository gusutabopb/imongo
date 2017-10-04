#!/usr/bin/env python
import json
import os
import sys
from setuptools import setup
from setuptools.command.install import install

if sys.version_info.major != 3:
    sys.exit('Support Python 3 only')


class Installer(install):
    def run(self):
        # Regular install
        install.run(self)

        # Post install
        print('Installing Jupyter kernelspec')
        from jupyter_client.kernelspec import KernelSpecManager
        from IPython.utils.tempdir import TemporaryDirectory
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
            ksm.install_kernel_spec(td, 'imongo', user=self.user, replace=True, prefix=self.prefix)


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
      cmdclass={'install': Installer},
      license='MIT',
      install_requires=['jupyter>=1.0.0',
                        'ipykernel',
                        'pexpect>=4.2.1',
                        'pyyaml'],
      classifiers=[
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'Intended Audience :: Science/Research',
          'Development Status :: 3 - Alpha',
          'Programming Language :: Python :: 3',
          'Topic :: System :: Shells',
      ])
