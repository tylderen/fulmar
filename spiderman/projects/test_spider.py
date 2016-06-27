import logging

from spiderman.base_handler import *

logger = logging.getLogger(__name__)

class Handler(BaseHandler):

    def on_start(self):
        logger.info('Start a new project !')
        self.crawl('https://www.baidu.com/', callback=self.index_page)

    def index_page(self, response):
        try:
            for each in response.doc('a[href^="http"]').items():
                self.crawl(each.attr.href, callback=self.detail_page)
        except Exception as e:
            logger.exception(str(e))

    def detail_page(self, response):
        logger.info(str({
            "url": response.url,
            "title": response.doc('title').text(),
        }))