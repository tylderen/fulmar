Service
========

**Note:**  `Redis` is necessary, so make sure you have installed it.

More precisely, fulmar is a sevice which can run all the time.
Fulmar mainly has three parts, scheduler, worker and phantomjs.
You can start them all in one, or run them separately.


Subcommands
-----------

all
^^^^^^^^^^

Run fulmar all in one.
Start scheduler and worker.
If phantomjs is installed and global opitions ``phantomjs-proxy`` isn't provided,
phantomjs will get started too.

phantomjs
^^^^^^^^^^^^^^^^

Run phantomjs when phantomjs is installed and global opitions
``phantomjs-proxy`` isn't provided.

scheduler
^^^^^^^^^^^^^^^^

Run Scheduler. Note that you should only start one scheduler.

worker
^^^^^^^^^^^^^

Run worker.

You can get ``worker help``, just run:

``fulmar worker --help``

You will see:

::

    Usage: fulmar worker [OPTIONS]

    Run Worker.

    Options:
      --poolsize INTEGER  pool size
      --user-agent TEXT   user agent
      --timeout INTEGER   default request timeout
      --help              Show this message and exit.


**--poolsize**

The maximum number of simultaneous fetch operations that can execute in parallel. Defaults to 300.

**--timeout**

The request timeout. Defaults to 180s.
