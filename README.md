# imongo
A MongoDB kernel for Jupyter.

This kernel wrappes the Mongo shell using 
[pexpect](https://github.com/pexpect/pexpect).

Meant to be used for educational purposes.

Insipred by [bash_kernel](https://github.com/takluyver/bash_kernel)
 and [ipython_mysql_kernel](https://github.com/mmisono/ipython_mysql_kernel).

## How to install

### Requirements
IMongo requires [Jupyter](http://jupyter.org/) and [MongoDB](https://www.mongodb.com).

#### MongoDB
On macOS, use [Homebrew](http://brew.sh/): `brew install mongodb`

For other platforms, please refer to the MongoDB [documentation](https://docs.mongodb.com/manual/installation/) 

#### IPython/Jupyter
I recommend using the [Anaconda](https://www.continuum.io/downloads) Python distribution.
To setup a minimal test environment for the kernel:
```
$ conda create -n imongoenv jupyter
```

### Kernel installation

Using `pip`: `pip install git+https://github.com/gusutabopb/imongo`

Using `setuptools`:
```
$ git clone https://github.com/gusutabopb/imongo
$ cd imongo
$ python setup.py install
```

Both methods install the `imongo` package and configure
Jupyter to be used with the new kernel by installing a 
[kernel spec](https://jupyter-client.readthedocs.io/en/latest/kernels.html#kernel-specs).

## Uninstall:

- Remove library: `pip uninstall imongo`
- Remove kernel spec: `jupyter kernelspec remove imongo`

-----------

## TODO:
- Implement code completion functionality
- Add to PyPI
