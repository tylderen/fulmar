import lxml.html
import logging


from fulmar.base_handler import *

# logger = logging.getLogger(__name__)

class Handler(BaseHandler):

    def on_start(self):
        logger.error('Start a new project !')
        self.crawl('http://www.baidu.com/', callback=self.index_page)

    def index_page(self, response):
        logger.error('in index page')
        logger.error(response.headers)
        try:
            page = lxml.html.fromstring(response.content.decode('utf-8'))

            logger.info(page.xpath('//title/text()'))
        except Exception as e:
            logger.error(str(e))
    def detail_page(self, response):
        logger.error('-------------detail page --------------')
        logger.info(str({
            "url": response.url,
            "title": response.doc('title').text(),
        }))