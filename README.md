# SPINDRIFT
## A REST Framework

*Spindrift* is a python 3.6+ framework for quickly creating
production quality micro-services.

Most of the boilerplate code, like setting up logging, database, config files and routing
are supported by *spindrift* with a simple `micro` file.
What is unique to a service is the actual code used to satisfy
the service's API, and this is what *spindrift* allows you to focus on.

## An Example

Consider the following `micro` file:

```
SERVER myserver 10000
  ROUTE /test/hello$
    GET example.hi
```

This describes a service that will listen on port 10000 for incoming REST calls.
If a GET HTTP request comes in with the resource `/test/hello`, the
function `hi` inside the python program `example.py` will be invoked.
The function `hi` is called the *handler*.

Here is a possible implementation of that handler:

```python
def hi(request):
  return {'hello': 'World'}
```

With two lines of python code you have a micro service. Granted, `hello world`
programs abound, and no real-world server is ever this simple. Don't worry, *spindrift*
can do much more.
