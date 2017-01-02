from ipykernel.kernelapp import IPKernelApp
from .kernel import MongoKernel

IPKernelApp.launch_instance(kernel_class=MongoKernel)
