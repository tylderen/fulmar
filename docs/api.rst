API Index
=========

BaseSpider
----------

It's the main class.

You should use it in your script file like this::

    from fulmar.base_spider import BaseSpider

Then you should create a new class which inherit ``BaseSpider`` just like::

    class Handler(BaseSpider)

Note that the name of the class don't have to be ``Handler``.


CrawlRate
---------

It is used for limiting the crawl rate.
It is a decorator for the ``Handler`` class.

You can use it just like:


.. code-block:: python

   from fulmar.base_spider import BaseSpider, CrawlRate

   @CrawlRate(request_number=1, time_period=2)
   class Handler(BaseSpider):

      def on_start(self):
         self.crawl('http://www.baidu.com/', callback=self.parse_and_save)

      def parse_and_save(self, response):
         return {
            "url": response.url,
            "title": response.page_lxml.xpath('//title/text()')[0]}


It means you can only send ``requests_number`` requests during ``time_period`` seconds.
Note that this rate limitation is used for one Worker.

So if you start `fulmar` with ``n`` workers, you actually send ``requests_number * n`` requests during ``time_period`` seconds.


def start(self)
---------------

In the class ``Handler``, you should define a method called ``start``.
It's the entrance of the whole crawl.

def crawl(self, url, **kwargs)
------------------------------

It's used to define a new crawl task.
You can use it like::

    self.crawl('http://www.baidu.com/', callback=self.detail_page)

There are many parameters can be used.

url
^^^^

    URL for the new request.

method
^^^^^^

    method for the new request. Defaults to ``GET``.
    (optional) Dictionary or bytes to be sent in the query string for the request.

data
^^^^

    (optional) Dictionary or bytes to be send in the body of request.

headers
^^^^^^^

    (optional) Dictionary of HTTP Headers to be send with the request.

cookies
^^^^^^^
    (optional) Dictionary to be send with the request.

cookie_persistence
^^^^^^^^^^^^^^^^^^
    Previous request and response's cookies will persist next request for
    the same website. Defaults to ``True``.
    Type: ``bool``.

timeout
^^^^^^^
    (optional) How long to wait for the server to send data before giving up.
    Type: ``float``.


priority
^^^^^^^^
    The bigger, the higher priority of the request.
    Type: ``int``.

callback
^^^^^^^^
    The method to parse the response.

callback_args
^^^^^^^^^^^^^
    The additional args to the callback.
    Type: ``list``.

callback_kwargs
^^^^^^^^^^^^^^^
    The additional kwargs to the callback.
    Type: ``dict``.

taskid
^^^^^^
    (optional) Unique id to identify the task. Default is the sha1 check code of the URL.
    But it won't be unique when you request the same url with different post params.

crawl_at
^^^^^^^^
    The time to start the rquest. It must be a timestamp.
    Type: ``Int`` or ``Float``.

crawl_later
^^^^^^^^^^^

    Starts the request after ``crawl_later`` seconds.

crawl_period
^^^^^^^^^^^^

    Schedules the request to be called periodically.
    The request is called every ``crawl_period`` seconds.

crawl_rate
^^^^^^^^^^

    This should be a dict Which contain ``request_number`` and ``time_period``.
    Note that the  ``time_period`` is given in seconds.
    If you don't set ``time_period``, the default is 1.
    E.g.,

            ``crawl_rate={'request_number': 10, 'time_period': 2}``

            Which means you can crawl the url at most 10 times every 2 seconds.
    Type: dict.

allow_redirects
^^^^^^^^^^^^^^^

    (optional) Boolean. Defaults to ``True``.
    Type: ``bool``.

proxy_host
^^^^^^^^^^
    (optional) HTTP proxy hostname.
    To use proxies, proxy_host and proxy_port must be set;
    proxy_username and proxy_password are optional.
    Type: ``string``.

proxy_port
^^^^^^^^^^
    (optional) HTTP proxy port.
    Type: ``Int``.

proxy_username
^^^^^^^^^^^^^^
    (optional) HTTP proxy username.
    Type: ``string``.

proxy_password
^^^^^^^^^^^^^^
    (optional) HTTP proxy password.
    Type: ``string``.

fetch_type
^^^^^^^^^^
    (optional) Set to ``js`` to enable JavaScript fetcher. Defaults to ``None``.

js_script
^^^^^^^^^
    (optional) JavaScript run before or after page loaded,
    should been wrapped by a function like ``function() { document.write("Hello World !"); }``.

js_run_at
^^^^^^^^^
    (optional) Run JavaScript specified via js_script at
    ``document-start`` or ``document-end``. Defaults to ``document-end``.

js_viewport_width
^^^^^^^^^^^^^^^^^
    (optional) Set the size of the viewport for the JavaScript fetcher of the layout process.

js_viewport_height
^^^^^^^^^^^^^^^^^^
    (optional) Set the size of the viewport for the JavaScript fetcher of the layout process.

load_images
^^^^^^^^^^^
    (optional) Load images when JavaScript fetcher enabled. Defaults to ``False``.

validate_cert
^^^^^^^^^^^^^
    (optional) For HTTPS requests, validate the server’s certificate? Defaults to ``True``.




