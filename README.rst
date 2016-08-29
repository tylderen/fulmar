.. fulmar documentation master file, created by
   sphinx-quickstart on Tue Aug  2 14:19:45 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

fulmar
=======

|docs|

Fulmar is a distributed crawler system. By using non-blocking network I/O,
Fulmar can handle hundreds of open connections at the same time. You can
extractthe data you need from websites. In a fast, simple way.


Quick links
^^^^^^^^^^^

* `Documentation <http://fulmar.readthedocs.io/en/latest/>`_
* `Source (github) <https://github.com/tylderen/fulmar>`_
* `Wiki <https://github.com/tylderen/fulmar/wiki/Links>`_

Code example
^^^^^^^^^^^^

.. code-block:: python

   from fulmar.base_spider import BaseSpider

   class Handler(BaseSpider):

      def on_start(self):
         self.crawl('http://www.baidu.com/', callback=self.detail_page)

      def parse_and_save(self, response):
         return {
            "url": response.url,
            "title": response.page_lxml.xpath('//title/text()')[0]}

You can save above code in a new file called   `baidu_spider.py`   and run command::

                  fulmar start_project baidu_spider.py

If you have installed `redis`, you will get::

                  Successfully start the project, project name: "baidu_spider".

Finally, start Fulmar::

                  fulmar all

Installation
------------

**Automatic installation**::

    pip install fulmar

Fulmar is listed in `PyPI <http://pypi.python.org/pypi/fulmar>`_ and
can be installed with ``pip`` or ``easy_install``.

Fulmar source code is `hosted on GitHub
<https://github.com/tylderen/fulmar>`_.



Documentation
-------------

Please visit  `Fulmar Docs <http://fulmar.readthedocs.io/en/latest/>`_.

.. |docs| image:: https://readthedocs.org/projects/fulmar/badge/?version=latest
    :alt: Documentation Status
    :scale: 100%
    :target: https://fulmar.readthedocs.io/en/latest/?badge=latest
