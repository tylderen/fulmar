.. fulmar documentation master file, created by
   sphinx-quickstart on Tue Aug  2 14:19:45 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

fulmar
=======

|docs|

Fulmar is a distributed crawler system.

By using non-blocking network I/O, Fulmar can handle hundreds of open connections at the same time.
You can extract the data you need from websites.
In a fast, simple way.

Some features you may want to know:

* Write script in Python
* Use Redis as message queue
* Use MongoDB as default database at present
* Support rate limitation of requests for a certain website or url
* Task crontab, priority
* Distributed architecture
* Crawl Javascript pages


Quick links
-----------

* `Source (github) <https://github.com/tylderen/fulmar>`_
* `Wiki <https://github.com/tylderen/fulmar/wiki/Links>`_

Script example
-----------

.. code-block:: python

   from fulmar.base_spider import BaseSpider

   class Handler(BaseSpider):

      def on_start(self):
         self.crawl('http://www.baidu.com/', callback=self.detail_page)

      def parse_and_save(self, response):
         return {
            "url": response.url,
            "title": response.page_lxml.xpath('//title/text()')[0]}

You can save above code in a new file called ``baidu_spider.py`` and run command::

                  fulmar start_project baidu_spider.py

If you have installed `redis`, you will get::

                  Successfully start the project, project name: "baidu_spider".

Finally, start Fulmar::

                  fulmar all

Installation
-----------


**Automatic installation**::

    pip install fulmar

Fulmar is listed in `PyPI <http://pypi.python.org/pypi/fulmar>`_ and
can be installed with ``pip`` or ``easy_install``.

**Manual installation**: Download tarball, then:

.. parsed-literal::

    tar xvzf fulmar-|version|.tar.gz
    cd fulmar-|version|
    python setup.py build
    sudo python setup.py install

The Fulmar source code is `hosted on GitHub
<https://github.com/tylderen/fulmar>`_.

**Prerequisites**: Fulmar runs on Python 2.7, and 3.3+
For Python 2, version 2.7.9 or newer is *strongly*
recommended for the improved SSL support.

Documentation
-----------


This documentation is also available in `PDF and Epub formats
<https://readthedocs.org/projects/fulmar/downloads/>`_.

.. toctree::
   :maxdepth: 2

   quick
   global_opitions
   commands


.. |docs| image:: https://readthedocs.org/projects/fulmar/badge/?version=latest
    :alt: Documentation Status
    :scale: 100%
    :target: https://fulmar.readthedocs.io/en/latest/?badge=latest
