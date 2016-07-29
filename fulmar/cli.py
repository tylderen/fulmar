# -*- encoding: utf-8 -*-
import os
import six
import time
import yaml
import logging
import logging.config

import click
import fulmar
import threading
from tabulate import tabulate
from fulmar import utils
from fulmar.utils import json_dumps

def connect_redis(ctx, param, value):
    return utils.connect_redis(value)

def load_cls(ctx, param, value):
    if isinstance(value, six.string_types):
        return utils.load_object(value)
    return value


@click.group(invoke_without_command=True)
@click.option('--redis', callback=connect_redis,
              help="redis address", show_default=True)
@click.option('--logging-config', default=os.path.join(os.path.dirname(__file__), "logging.conf"),
              help="logging config file for built-in python logging module", show_default=True)
@click.version_option(version=fulmar.__version__, prog_name=fulmar.__name__)
@click.pass_context
def cli(ctx, **kwargs):
    """A powerful spider system in python."""
    logging.config.fileConfig(kwargs['logging_config'])
    config = {}
    config_filepath = os.path.join(os.path.dirname(__file__), "config.yml")
    try:
        with open(config_filepath, 'r') as f:
            config = yaml.load(f)
    except IOError as e:
        err = 'No default configuration file find.'
    except Exception as e:
        logging.error(e)
    redis_conn = None
    if kwargs.get('redis'):
        redis_conn = kwargs['redis']
    else:
        if config.get('redis'):
             redis_conn = utils.connect_redis(config['redis']['url'])
        else:
            raise Exception('redis in config.yaml wrong!')
    LUA_RATE_LIMIT_SCRIPT = """
    local current_requests = redis.call('get', KEYS[1])
    if not current_requests then
        redis.call('incr', KEYS[1])
        redis.call('expire', KEYS[1], ARGV[1])
        return 0
    end
    if tonumber(current_requests) >= tonumber(ARGV[2]) then
        return 1
    end
    redis.call('incr', KEYS[1])
    return 0
    """
    lua_rate_limit = redis_conn.register_script(LUA_RATE_LIMIT_SCRIPT)
    setattr(utils, 'redis_conn', redis_conn)
    setattr(utils, 'lua_rate_limit',lua_rate_limit)

    ctx.obj = utils.ObjectDict(ctx.obj or {})
    ctx.obj.update(config)
    return ctx


@cli.command()
@click.option('--poolsize', default=300, help="pool size")
@click.option('--proxy', help="proxy host:port")
@click.option('--user-agent', help='user agent')
@click.option('--timeout', help='default fetch timeout')
@click.option('--worker-cls', default='fulmar.worker.Worker', callback=load_cls)
@click.pass_context
def worker(ctx, proxy, user_agent, timeout, worker_cls, poolsize, async=True):
    """Run Worker."""
    g = ctx.obj
    from fulmar.message_queue import newtask_queue, ready_queue
    from fulmar.scheduler.projectdb import projectdb
    Worker = load_cls(None, None, worker_cls)

    worker = Worker(ready_queue, newtask_queue, projectdb,
                    poolsize=poolsize, proxy=proxy, async=async)
    worker.run()


@cli.command()
@click.option('--scheduler-cls', default='fulmar.scheduler.Scheduler', callback=load_cls)
@click.pass_context
def scheduler(ctx, scheduler_cls):
    """Run Scheduler."""
    g = ctx.obj
    from fulmar.message_queue import newtask_queue, ready_queue, cron_queue
    Scheduler = load_cls(None, None, scheduler_cls)

    scheduler = Scheduler(newtask_queue, ready_queue, cron_queue)
    scheduler.run()


@cli.command()
@click.option('--worker-num', default=1, help='Default worker num')
@click.pass_context
def all(ctx, worker_num):
    """Start scheduler and worker together."""
    g = ctx.obj
    threads = []
    scheduler_config = g.get('scheduler', {})
    threads.append(utils.run_in_thread(ctx.invoke, scheduler, **scheduler_config))

    worker_config = g.get('worker', {})
    threads.append(utils.run_in_thread(ctx.invoke, worker, **worker_config))
    for i in threads:
        logging.info(i)
    logging.info(threading.enumerate())
    time.sleep(500)


@cli.command()
@click.argument('project_file')
@click.pass_context
def update_project(ctx, project_file):
    """Update a project."""
    from fulmar.scheduler.projectdb import projectdb
    from fulmar.utils import sha1string
    # todo: add default dir to put project
    raw_code = ''
    with open(project_file, 'rb') as f:
        for line in f:
            raw_code += line

    project_id = sha1string(raw_code)
    project_name = project_file.split('/')[-1].strip(' .py')
    data = {'project_name': project_name, 'script': raw_code, 'project_id': project_id}
    projectdb.set(project_name, data)

    logging.info('Successfully update the project "%s".', project_name)


@cli.command()
@click.argument('project')
@click.pass_context
def start_project(ctx, project):
    """Start a project."""
    from fulmar.message_queue import newtask_queue
    from fulmar.scheduler.projectdb import projectdb
    project_name = project.split('/')[-1].strip(' .py')
    project_data = projectdb.get(project_name)
    if not project_data:
        ctx.invoke(update_project, project_file=project)
        project_data = projectdb.get(project_name)

    newtask = {
        "project_name": project_name,
        'project_id': project_data.get('project_id'),
        "taskid": project_name + 'on_start',
        "url": 'first_task' + project,
        "process": {
            "callback": "on_start",
        },
        "schedule": {
        },
    }
    newtask_queue.put(newtask)

    logging.info('Successfully start the project "%s".', project_name)


@cli.command()
@click.option('--delete', '-d', help='Delete a cron task. Here use taskid, e.g, -d taskid')
@click.option('--list', '-l', is_flag=True, help='List all of cron tasks so far.')
@click.option('--verbose', '-v', is_flag=True, help='Verbose mode. Show more information about this crontab.')
@click.pass_context
def crontab(ctx, delete, verbose, list):
    from fulmar.message_queue import cron_queue
    from datetime import datetime
    range = cron_queue.range()

    if delete:
        is_ok = False
        for task, _ in range:
            if task['taskid'] == delete:
                is_ok = cron_queue.delete_one(task)
                click.echo('Successfully delete task: %s' % delete)
                break
        if not is_ok:
            click.echo('Failed to delete task: %s. Please make sure the taskid is correct.' % delete)
        return

    headers = ['project', 'task_id', 'url', 'crawl_period', 'next_crawl_time']
    table = []
    tasks = []
    if verbose:
        for task, time in range:
            tasks.append(task)
        click.echo(json_dumps(tasks, indent=4))
    else:
        for task, time in range:
            time = datetime.fromtimestamp(time)
            next_crawl_time =time.strftime('%Y-%m-%d %H:%M:%S')
            project = task.get('project_name')
            url = task.get('url')
            taskid = task.get('taskid')
            crawl_period = task.get('schedule',{}).get('crawl_period')
            if crawl_period > 60 * 60 * 24:
                crawl_period = str(crawl_period / (60 * 60 * 24.0)) + '(days)'
            elif crawl_period > 60 * 60:
                crawl_period = str(crawl_period / (60 * 60.0)) + ' (hours)'
            elif crawl_period > 60:
                crawl_period = str(crawl_period / 60.0) + ' (minutes)'
            else:
                crawl_period = str(crawl_period) + ' (seconds)'

            table.append([project, taskid, url, crawl_period, next_crawl_time])
        click.echo(tabulate(table, headers, tablefmt="grid", numalign="right"))


def main():
    cli()


if __name__ == '__main__':
    main()