Opitions
================

Fulmar is easy to use.

**Note:**  `Redis` is necessary, so make sure you have installed it.

**--help**
-----------

You can get ``help``, just run:

``fulmar --help``

You will see:

::

   Usage: fulmar [OPTIONS] COMMAND [ARGS]...

   A  crawler system.

   Options:
     -c, --config TEXT      a yaml file with default config.  [default:
                            /fulmar/fulmar/config.yml]
     --redis TEXT           redis address, e.g, 'redis://127.0.0.1:6379/0'.
     --mongodb TEXT         mongodb address, e.g, 'mongodb://localhost:27017/'.
     --phantomjs-proxy TEXT phantomjs proxy ip:port.
     --logging-config TEXT  logging config file for built-in python logging
                            module  [default: /fulmar/fulmar/logging.conf]

     --version              Show the version and exit.
     --help                 Show this message and exit.

    Commands:
      all             Start scheduler and worker, also run...
      crontab         Crontab infos and operations.
      delete_project  Delete a project.
      phantomjs       Run phantomjs if phantomjs is installed.
      scheduler       Run Scheduler.
      show_projects   Show projects.
      start_project   Start a project.
      stop_project    Stop a project.
      update_project  Update a project.
      worker          Run Worker.


**--config**
------------

Config file is a YAML file with config values for global options or subcommands.
Fulmar has a default config file, the content is:

::

   redis:
       url: redis://127.0.0.1:6379/0
   mongodb:
       url: mongodb://localhost:27017/
   worker:
       async: true
       poolsize: 300
       timeout: 180

If you run fulmar without any paramtets or config file, fulmar will use this default configuration.
You can write your own config file, and use it just like:

``fulmar --config=your-config-file all``


**--redis**
-----------
Redis address.
You can run fulmar just like:

``fulmar --redis=redis://127.0.0.1:6379/0 all``


**--mongodb**
-------------

MongoDB address.

**--phantomjs-proxy**
----------------------

phantomjs proxy ip:port.
If you set it, it means you have already run phantomjs.
So fulmar will not try to run a new phantomjs,
instead just use this one.

**--logging-config**
--------------------

Log config file. Fulmar use `logging <https://docs.python.org/2/library/logging.html>`_. If you want to change
the default log behavior, you can write you own log file,
reference: `configuration-file-format <https://docs.python.org/2/library/logging.config.html#configuration-file-format>`_

**--version**
-------------

Show fulmar version.
