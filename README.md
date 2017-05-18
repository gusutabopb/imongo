# imongo
A MongoDB kernel for Jupyter. Mainly for educational purposes.

This kernel wraps the Mongo shell using 
[pexpect](https://github.com/pexpect/pexpect) and was
insipred by [bash_kernel](https://github.com/takluyver/bash_kernel)
 and [ipython_mysql_kernel](https://github.com/mmisono/ipython_mysql_kernel). 
 Uses [Renderjson](https://github.com/caldwell/renderjson) for JSON pretty-printing.

![IMongo in action](screenshot.png)

## How to install

### Major requirements
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

#### Kernel installation

Using `pip`:
```
 $ pip install git+https://github.com/gusutabopb/imongo
 ```

Using `setuptools`:
```
$ git clone https://github.com/gusutabopb/imongo
$ cd imongo
$ python setup.py install
```

Both methods install the `imongo` package and configure
Jupyter to be used with the new kernel by installing a 
[kernel spec](https://jupyter-client.readthedocs.io/en/latest/kernels.html#kernel-specs).

#### Configuration

MongoDB configuration such as host/port can be passed as a YAML configuration file, 
located at the Jupyter [configuration directory](http://jupyter.readthedocs.io/en/latest/projects/jupyter-directories.html#configuration-files). 
The default path for UNIX systems is `~/.jupyter/imongo_config.yml`.  
The options available are the same as the ones available for the [`mongo`](https://docs.mongodb.com/manual/reference/program/mongo/) CLI tool.

Sample `imongo_config.yml`:

```yaml
host: some.host.io
port: 27017
username: username
password: password
authenticationDatabase: admin
quiet: null
```

If `imongo_config.yml` doesn't exist or is empty, IMongo will attempt to connect to the MongoDB instance at `localhost:27017`, without any user authentication.


## Uninstall:

```
# Remove library: 
$ pip uninstall imongo
# Remove kernel spec
$ jupyter kernelspec remove imongo
```

-----------

## TODO:
- Implement code completion functionality
- Fix long command issue
- Send Mongo shell Javascript errors/exceptions to stderr
- Add to PyPI
