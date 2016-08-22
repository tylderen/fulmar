import logging

from fulmar.base_spider import BaseSpider

logger = logging.getLogger(__name__)

class Handler(BaseSpider):

    def on_start(self):
        self.crawl('http://www.baidu.com/', callback=self.detail_page)

    def detail_page(self, response):
        try:
            page_lxml = response.page_lxml
        except Exception as e:
            logger.error(str(e))

        return {
                "url": response.url,
                "title": page_lxml.xpath('//title/text()')[0]}