# -*- encoding: utf-8 -*-
import os
import six
import time
import yaml
import logging
import logging.config

import click
import fulmar
from tabulate import tabulate
from fulmar import utils
from fulmar.utils import json_dumps


def load_cls(ctx, param, value):
    if isinstance(value, six.string_types):
        return utils.load_object(value)
    return value


@click.group()
@click.option('--redis', help="redis address, e.g, 'redis://127.0.0.1:6379/0'.")
@click.option('--mongodb', help="mongodb address, e.g, 'mongodb://localhost:27017/'.")
@click.option('--logging-config', default=os.path.join(os.path.dirname(__file__), "logging.conf"),
              help="logging config file for built-in python logging module", show_default=True)
@click.option('--config', '-c', default=os.path.join(os.path.dirname(__file__), "config.yml"),
              help='a yaml file with default config.', show_default=True)
@click.version_option(version=fulmar.__version__, prog_name=fulmar.__name__)
@click.pass_context
def cli(ctx, **kwargs):
    """A  crawler system."""
    logging.config.fileConfig(kwargs['logging_config'])
    config = {}
    config_filepath = kwargs['config']
    if config_filepath:
        if not os.path.exists(config_filepath):
            raise IOError('No such file or directory: "%s".' % config_filepath)

        if not os.path.isfile(config_filepath):
            raise IOError('Is not a file: "%s".' % config_filepath)

        try:
            with open(config_filepath, 'r') as f:
                config = yaml.load(f)
        except Exception as err:
            raise err

    if kwargs.get('redis'):
        redis_conn = utils.connect_redis(kwargs['redis'])
    elif config.get('redis'):
        redis_conn = utils.connect_redis(config['redis']['url'])
    else:
        raise Exception('Could not find redis address.')

    if kwargs.get('mongodb'):
        mongodb_conn = utils.connect_mongodb(kwargs['mongodb'])
    elif config.get('mongodb'):
        mongodb_conn = utils.connect_mongodb(config['mongodb']['url'])
    else:
        logging.warning('Could not find mongodb address.')

    from fulmar.utils import LUA_RATE_LIMIT_SCRIPT
    lua_rate_limit = redis_conn.register_script(LUA_RATE_LIMIT_SCRIPT)
    setattr(utils, 'redis_conn', redis_conn)
    setattr(utils, 'lua_rate_limit',lua_rate_limit)
    setattr(utils, 'mongodb_conn', mongodb_conn)

    ctx.obj = utils.ObjectDict(ctx.obj or {})
    ctx.obj.update(config)
    return ctx


@cli.command()
@click.option('--poolsize', default=300, help="pool size")
@click.option('--proxy', help="proxy host:port")
@click.option('--user-agent', help='user agent')
@click.option('--timeout', default=180, help='default request timeout')
@click.pass_context
def worker(ctx, proxy, user_agent, timeout, poolsize, async=True):
    """Run Worker."""
    from fulmar.message_queue import newtask_queue, ready_queue
    from fulmar.scheduler.projectdb import projectdb
    from fulmar.database import mongo
    from fulmar.worker import Worker
    worker = Worker(ready_queue, newtask_queue, mongo,
                    projectdb, poolsize=poolsize, proxy=proxy,
                    async=async, user_agent=user_agent, timeout=timeout)
    worker.run()


@cli.command()
@click.pass_context
def scheduler(ctx):
    """Run Scheduler."""
    from fulmar.scheduler.projectdb import projectdb
    from fulmar.message_queue import newtask_queue, ready_queue, cron_queue
    from scheduler import Scheduler
    scheduler = Scheduler(newtask_queue, ready_queue, cron_queue, projectdb)
    scheduler.run()


@cli.command()
@click.option('--phantomjs-path', default='phantomjs', help='phantomjs path')
@click.option('--port', default=25555, help='phantomjs port')
@click.option('--auto-restart', default=False, help='auto restart phantomjs if crashed')
@click.argument('args', nargs=-1)
@click.pass_context
def phantomjs(ctx, phantomjs_path, port, auto_restart, args):
    """
    Run phantomjs if phantomjs is installed.
    """
    args = args or ctx.default_map and ctx.default_map.get('args', [])

    import subprocess
    g = ctx.obj
    _quit = []
    phantomjs_fetcher = os.path.join(
        os.path.dirname(fulmar.__file__), 'worker/phantomjs_fetcher.js')
    cmd = [phantomjs_path,
           # this may cause memory leak: https://github.com/ariya/phantomjs/issues/12903
           #'--load-images=false',
           '--ssl-protocol=any',
           '--disk-cache=true'] + list(args or []) + [phantomjs_fetcher, str(port)]

    try:
        _phantomjs = subprocess.Popen(cmd)
    except OSError:
        logging.warning('phantomjs not found, continue running without it.')
        return None

    if not g.get('phantomjs_proxy'):
        g['phantomjs_proxy'] = '127.0.0.1:%s' % port

    while True:
        _phantomjs.wait()
        if _quit or not auto_restart:
            break
        _phantomjs = subprocess.Popen(cmd)


@cli.command()
@click.pass_context
def all(ctx):
    """
        Start scheduler and worker, also run phantomjs if phantomjs is installed.
        Suggest just for testing.
    """
    g = ctx.obj
    sub_processes = []
    threads = []
    try:
        if not g.get('phantomjs_proxy'):
            phantomjs_config = g.get('phantomjs', {})
            phantomjs_config.setdefault('auto_restart', True)
            sub_processes.append(utils.run_in_subprocess(ctx.invoke, phantomjs, **phantomjs_config))
            time.sleep(2)
            if sub_processes[-1].is_alive() and not g.get('phantomjs_proxy'):
                g['phantomjs_proxy'] = '127.0.0.1:%s' % phantomjs_config.get('port', 25555)

        scheduler_config = g.get('scheduler', {})
        threads.append(utils.run_in_thread(ctx.invoke, scheduler, **scheduler_config))

        worker_config = g.get('worker', {})
        threads.append(utils.run_in_thread(ctx.invoke, worker, **worker_config))

        while threads:
            for t in threads:
                if not t.isAlive():
                  threads.remove(t)
            time.sleep(0.1)

        for sub_process in sub_processes:
            sub_process.join()

    except KeyboardInterrupt:
        logging.info('Keyboard interrupt. Bye, bye.')
    finally:
        # Need to kill subprocesses.
        for process in sub_processes:
            process.terminate()


@cli.command()
@click.pass_context
def show_projects(ctx):
    """Show projects."""
    from fulmar.scheduler.projectdb import projectdb

    projects = projectdb.get_all()

    headers = ['project_name', 'updated_time', 'is_stopped']
    table = []
    for _, project in projects.iteritems():
        project_name = project.get('project_name')
        update_timestamp = project.get('update_time')
        update_time =time.strftime('%Y-%m-%d %H:%M:%S')
        is_stopped = 'True' if project.get('is_stopped') else 'False'
        table.append([project_name, update_time, is_stopped])

    click.echo(tabulate(table, headers, tablefmt="grid", numalign="right"))


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
    data = {'project_name': project_name, 'script': raw_code, 'project_id': project_id, 'update_time': time.time()}
    projectdb.set(project_name, data)

    click.echo('Successfully update the project "%s".' % project_name)


@cli.command()
@click.argument('project')
@click.pass_context
def start_project(ctx, project):
    """Start a project."""
    from fulmar.message_queue import newtask_queue
    from fulmar.scheduler.projectdb import projectdb

    if not os.path.exists(project):
        raise IOError('No such file or directory: "%s".' % project)

    if not os.path.isfile(project):
        raise IOError('Is not a Python file: "%s".' % project)

    if not project.endswith('.py'):
        raise TypeError('Not a standard Python file: "%s". Please make sure it is a Python file which ends with ".py".' % project)

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

    click.echo('Successfully start the project, project name: "%s".' % project_name)


@cli.command()
@click.argument('project_name')
@click.pass_context
def stop_project(ctx, project_name):
    """Stop a project."""
    from fulmar.scheduler.projectdb import projectdb

    project_name = project_name.split('/')[-1].strip(' .py')

    project_data = projectdb.get(project_name)
    if not project_data:
        click.echo('Sorry, can not find project:  "%s".' % project_name)
        return
    project_data.update({'is_stopped': True})
    projectdb.set(project_name, project_data)
    click.echo('Successfully stop project: "%s".' % project_name)


@cli.command()
@click.argument('project_name')
@click.pass_context
def delete_project(ctx, project_name):
    """Delete a project."""
    from fulmar.scheduler.projectdb import projectdb

    project_name = project_name.split('/')[-1].strip(' .py')

    project_data = projectdb.get(project_name)
    if not project_data:
        click.echo('Sorry, can not find project_name: "%s".' % project_name)
        return

    projectdb.delete(project_name)
    click.echo('\nSuccessfully delete project: "%s".\n' % project_name)


@cli.command()
@click.option('--delete', '-d', help='Delete a cron task. Here use taskid, e.g, -d taskid')
@click.option('--verbose', '-v', is_flag=True, help='Verbose mode. Show more information about this crontab.')
@click.pass_context
def crontab(ctx, delete, verbose):
    """Crontab infos and operations."""
    from fulmar.message_queue import cron_queue
    from datetime import datetime
    range = cron_queue.range()

    if delete:
        delete_ok = False
        for task, _ in range:
            if task['taskid'] == delete:
                cron_queue.delete_one(task)
                delete_ok = True
                click.echo('\nSuccessfully delete task: %s\n.' % delete)
                break
        if not delete_ok:
            click.echo('\nFailed to delete task: %s. Please make sure the taskid is correct.\n' % delete)
        return

    headers = ['task_id', 'url', 'project', 'crawl_period', 'next_crawl_time']
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
            project_name = task.get('project_name')
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

            table.append([taskid, url, project_name, crawl_period, next_crawl_time])
        click.echo(tabulate(table, headers, tablefmt="grid", numalign="right"))


def main():
    cli()


if __name__ == '__main__':
    main()