# -*- encoding: utf-8 -*-

import os
import sys
import six
import copy
import time
import yaml
import shutil
import logging
import logging.config

import click
import spiderman

from spiderman import utils


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
@click.version_option(version=spiderman.__version__, prog_name=spiderman.__name__)
@click.pass_context
def cli(ctx, **kwargs):
    """
    A powerful spider system in python.
    """
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
    setattr(utils, 'redis', redis_conn)

    ctx.obj = utils.ObjectDict(ctx.obj or {})
    ctx.obj.update(config)
    return ctx


@cli.command()
@click.option('--poolsize', default=100, help="pool size")
@click.option('--proxy', help="proxy host:port")
@click.option('--user-agent', help='user agent')
@click.option('--timeout', help='default fetch timeout')
@click.option('--worker-cls', default='spiderman.worker.Worker', callback=load_cls)
@click.pass_context
def worker(ctx, proxy, user_agent, timeout, worker_cls, poolsize, async=True):
    """
    Run Worker.
    """
    g = ctx.obj
    from spiderman.message_queue import newtask_queue, ready_queue
    from spiderman.scheduler.projectdb import projectdb
    Worker = load_cls(None, None, worker_cls)

    worker = Worker(ready_queue, newtask_queue, projectdb,
                    poolsize=poolsize, proxy=proxy, async=async, user_agent=user_agent)
    worker.run()


@cli.command()
@click.option('--scheduler-cls', default='spiderman.scheduler.Scheduler', callback=load_cls)
@click.pass_context
def scheduler(ctx, scheduler_cls):
    """
    Run Scheduler.
    """
    g = ctx.obj
    from spiderman.message_queue import newtask_queue, ready_queue
    from spiderman.scheduler.projectdb import projectdb
    Scheduler = load_cls(None, None, scheduler_cls)

    scheduler = Scheduler(newtask_queue, ready_queue)
    scheduler.run()


@cli.command()
@click.option('--worker-num', default=1, help='default worker num')
@click.pass_context
def all(ctx, worker_num):
    g = ctx.obj
    threads = []
    scheduler_config = g.get('scheduler', {})
    threads.append(utils.run_in_thread(ctx.invoke, scheduler, **scheduler_config))

    worker_config = g.get('worker', {})
    threads.append(utils.run_in_thread(ctx.invoke, worker, **worker_config))
    for i in threads:
        logging.info(i)
    time.sleep(500)


@cli.command()
@click.argument('project_file')
@click.pass_context
def update_project(ctx, project_file):
    """
    Update a project
    """
    from spiderman.scheduler.projectdb import projectdb
    from spiderman.util import md5string
    # todo: add default dir to put project
    raw_code = ''
    with open(project_file, 'rb') as f:
        for line in f:
            raw_code += line

    project_id = md5string(raw_code)
    project_name = project_file.split('/')[-1].strip(' .py')
    data = {'project_name': project_name, 'script': raw_code, 'project_id': project_id}
    projectdb.set(project_name, data)


@cli.command()
@click.argument('project')
@click.pass_context
def start_project(ctx, project):
    """
    Start a project
    """
    from spiderman.message_queue import newtask_queue, ready_queue
    from spiderman.scheduler.projectdb import projectdb
    project_name = project.split('/')[-1].strip(' .py')
    project_data = projectdb.get(project_name)
    if not project_data:
        ctx.invoke(update_project, project_file=project)
        project_data = projectdb.get(project_name)

    logging.info(project_data)

    newtask = {
        "project_name": project_name,
        'project_id': project_data.get('project_id'),
        "taskid": project + 'on_start',
        "url": 'first_task' + project,
        "process": {
            "callback": "on_start",
        },
        "schedule": {
        },
    }
    newtask_queue.push(newtask)


def main():
    cli()


if __name__ == '__main__':
    main()