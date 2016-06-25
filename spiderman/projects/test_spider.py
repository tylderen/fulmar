from spiderman.base_handler import *


class Handler(BaseHandler):

    def on_start(self):
        self.crawl('https://www.baidu.com/', callback=self.index_page)

    def index_page(self, response):
        for each in response.doc('a[href^="http"]').items():
            self.crawl(each.attr.href, callback=self.detail_page)

    def detail_page(self, response):
        return {
            "url": response.url,
            "title": response.doc('title').text(),
        }
