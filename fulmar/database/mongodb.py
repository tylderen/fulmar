import time
import inspect

class MongoDB(object):

    def __init__(self, server):
        self.db_conn = server

    def update(self, db_name, coll_name, results, task, query, upsert=True):
        self.db_coll = self.db_conn[db_name][coll_name]

        if inspect.isgenerator(results):
            pass
        elif not isinstance(results, list):
            results = [results]

        for r in results:
            assert isinstance(r, dict), 'result saved to mongodb must be dict.'
            if not query:
                query = {'taskid': task.get('taskid')}
            self.db_coll.update(
                query,
                {'$set': r,
                 '$setOnInsert': {'updated_at': time.time()}},
                upsert=upsert,
            )