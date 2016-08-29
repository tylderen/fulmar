Subcommands
==================

Fulmar mainly has two parts, scheduler and worker.


fulmar all
----------

Start scheduler and worker, also run phantomjs if phantomjs is installed.

fulmar scheduler
----------------

Run Scheduler. Note that you should only start one scheduler.

fulmar worker
-------------

Run worker.

You can get ``help``, just run:

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