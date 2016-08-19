# -*- encoding: utf-8 -*-
import pytest


class TestBaseHandler:
    from fulmar.base_spider import BaseSpider
    BaseSpider.project_name = 'test_project'
    BaseSpider.project_id = 'test_project_id'
    base_spider = BaseSpider()

    def test_crawl(self):

        self.base_spider._reset()
        assert self.base_spider.project_name == 'test_project'
        assert self.base_spider.project_id == 'test_project_id'

        self.base_spider._reset()
        with pytest.raises(AttributeError):
            self.base_spider.crawl('http://www.baidu.com', callback=max)
        assert self.base_spider._follows == []

        self.base_spider._reset()
        self.base_spider.crawl('http://www.baidu.com', callback=None, callback_args=[1, 2, 3], callback_kwargs={'name': 'somebody'})
        assert self.base_spider._follows[0]['process']['callback_args'] == [1, 2, 3]
        assert self.base_spider._follows[0]['process']['callback_kwargs'] == {'name': 'somebody'}

        self.base_spider._reset()
        self.base_spider.crawl('http://www.baidu.com', params={'你好123': u'是的'} )
        assert self.base_spider._follows[0]['url'] == 'http://www.baidu.com/?%E4%BD%A0%E5%A5%BD123=%E6%98%AF%E7%9A%84'

        self.base_spider._reset()
        self.base_spider.crawl('http://www.baidu.com', params=b'你好123' )
        assert self.base_spider._follows[0]['url'] == 'http://www.baidu.com/?%E4%BD%A0%E5%A5%BD123'

        self.base_spider._reset()
        self.base_spider.crawl('http://www.baidu.com', data={'你好123': u'是的'})
        assert self.base_spider._follows[0]['fetch']['data'] == '%E4%BD%A0%E5%A5%BD123=%E6%98%AF%E7%9A%84'
        assert self.base_spider._follows[0]['fetch']['method'] == 'POST'

        self.base_spider._reset()
        self.base_spider.crawl('http://www.baidu.com', data=b'你好123')
        assert self.base_spider._follows[0]['fetch']['data'] == '\xe4\xbd\xa0\xe5\xa5\xbd123'

        self.base_spider._reset()
        self.base_spider.crawl('http://www.baidu.com', timeout=12)
        assert self.base_spider._follows[0]['fetch']['timeout'] == 12

        self.base_spider._reset()
        self.base_spider.crawl('http://www.baidu.com', priority=2)
        assert self.base_spider._follows[0]['schedule']['priority'] == 2

        self.base_spider._reset()
        self.base_spider.crawl('http://www.baidu.com', crawl_later=3, crawl_period=60)
        assert self.base_spider._follows[0]['schedule']['crawl_later'] == 3
        assert self.base_spider._follows[0]['schedule']['crawl_period'] == 60
        assert self.base_spider._follows[0]['schedule']['is_cron'] == True

        self.base_spider._reset()
        self.base_spider.crawl('http://www.baidu.com', taskid='uuid')
        assert self.base_spider._follows[0]['taskid'] == 'uuid'

        self.base_spider._reset()
        self.base_spider.crawl('http://www.baidu.com')
        assert self.base_spider._follows[0]['taskid'] == '5f408e2de1e42ca41b5ea1d53e2831123105f22c'

        self.base_spider._reset()
        self.base_spider.crawl('http://www.baidu.com', cookies={'name': 'somebody'})
        assert self.base_spider._follows[0]['fetch']['cookies'] == {'name': 'somebody'}

        self.base_spider._reset()
        self.base_spider.crawl('http://www.baidu.com', fetch_type='js')
        assert self.base_spider._follows[0]['fetch']['fetch_type'] == 'js'

        self.base_spider._reset()
        self.base_spider.crawl('http://www.baidu.com', request_number=10, time_period=2)
        assert self.base_spider._follows[0]['crawl_rate']['request_number'] == 10
        assert self.base_spider._follows[0]['crawl_rate']['time_period'] == 2
        assert self.base_spider._follows[0]['crawl_rate']['limit_level'] == 'rate_limit: http://www.baidu.com/'
        self.base_spider._reset()
        self.base_spider.crawl('http://www.baidu.com', request_number=10)
        assert self.base_spider._follows[0]['crawl_rate']['request_number'] == 10
        assert self.base_spider._follows[0]['crawl_rate']['time_period'] == 1
        assert self.base_spider._follows[0]['crawl_rate']['limit_level'] == 'rate_limit: http://www.baidu.com/'

        self.base_spider._reset()
