Quickstart
==========


Installation
------------

* `pip install fulmar`


Please install `Redis <http://redis.io/download>`_.

**Note:**  `Redis` is necessary, so make sure you have installed it.


Please install MongoDB if needed: https://www.mongodb.com/download-center?jmp=docs#community

**Note:**  `MongoDB` will be enabled only if it is installed and you have provided its address.
If not, the result will not be saved.


Please install PhantomJS if needed: http://phantomjs.org/build.html

**Note:**  `PhantomJS` will be enabled only if it is excutable in the `PATH` or in the System Environment.


Run command:
------------

* `fulmar`

**Note:**  `fulmar` command is running fulmar in `testing` mode, which running components in threads or subprocesses.
For production environment, please refer to [Deployment](Deployment).


Your First Spider
-----------------

.. code-block:: python

   from fulmar.base_spider import BaseSpider

   class Handler(BaseSpider):

      def on_start(self):
         self.crawl('http://www.baidu.com/', callback=self.detail_page)

      def parse_and_save(self, response):
         return {
            "url": response.url,
            "title": response.page_lxml.xpath('//title/text()')[0]}


You can save above code in a new file called   `baidu_spider.py`   and run command in a new console::

                  fulmar start_project baidu_spider.py

If you have installed `redis`, you will get::

                  Successfully start the project, project name: `baidu_spider`.



In the example:
^^^^^^^^^^^^^^


**on_start(self)**

    It is the entry point of the spider.

**self.crawl(url, callback=self.parse_and_save)**

    It is the most important API here.
    It will add a new task to be crawled.

**parse_and_save(self, response)**

    It get a `Response </apis/Response>`_ object.
    `response.page_lxml </apis/Response/#page_lxml>`_ is a `lxml.html document_fromstring <https://pythonhosted.org/pyquery/>`_ object
    which has `xpath` API to select elements to be extracted.

    It return a `dict` object as result.
    The result will be captured into `resultdb` by default.
    You can override `on_result(self, result)` method to manage the result yourself.


More details you need to know:
^^^^^^^^^

**CrawlRate**

    It is a decorator for the `Handler` class.
    It is used for limiting the crawl rate.

    You can use it just like:


.. code-block:: python

   from fulmar.base_spider import BaseSpider, CrawlRate

   @CrawlRate(request_number=1, time_period=2)
   class Handler(BaseSpider):

      def on_start(self):
         self.crawl('http://www.baidu.com/', callback=self.detail_page)

      def parse_and_save(self, response):
         return {
            "url": response.url,
            "title": response.page_lxml.xpath('//title/text()')[0]}


It means you can only send `requests_number` requests during `time_period` seconds.
Note that this rate limitation is used for a Worker.

So if you start `fulmar` with `n` workers, you actually send `requests_number * n` requests during `time_period` seconds.



![index demo](imgs/index_page.png)

Your script is running now!
