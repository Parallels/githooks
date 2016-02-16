#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:ts=4:sw=4:expandtab
#
# ==================================================================
#
# Copyright (c) 2016, Parallels IP Holdings GmbH
# Released under the terms of MIT license (see LICENSE for details)
#
# ==================================================================
#
'''
Stash external hooks entry point

Executes hooks from this_file_path/hooks.d as specified in
the configuration file (passed as parameter). Reads stdin and passes
it to each executed hook.

On how to configure external hooks see
https://github.com/ngsru/atlassian-external-hooks/wiki/Configuration
'''

import os
import sys
import json
import ConfigParser
import fileinput
import logging

encoding = sys.getfilesystemencoding()
this_file_path = os.path.dirname(unicode(__file__, encoding))
hooks_dir = os.path.join(this_file_path, 'hooks.d')
sys.path.append(hooks_dir)


def configure_defaults():
    '''
    Validate Stash and external-hooks plugin environment required
    to run the hooks. Configure default githooks source layout.

    Note: these values can be overriden by values in DEFAULT section
    of githooks.ini.
    '''
    params = {}
    try:
        params['stash_home'] = os.environ['STASH_HOME']
        params['user_name'] = os.environ['STASH_USER_NAME']
        params['base_url'] = os.environ['STASH_BASE_URL']
        params['proj_key'] = os.environ['STASH_PROJECT_KEY']
        params['repo_name'] = os.environ['STASH_REPO_NAME']
    except KeyError as key:
        raise RuntimeError("%s not in env" % key)

    params['log_file'] = os.path.join(params['stash_home'], 'log', 'atlassian-stash-githooks.log')
    params['root_dir'] = os.path.join(params['stash_home'], 'external-hooks')
    params['conf_dir'] = os.path.join(params['root_dir'], 'conf')
    params['hooks_dir'] = os.path.join(params['root_dir'], 'hooks.d')

    return params

def load_conf_file(conf_dir, conf_file):
    '''
    Load githooks configuration from conf_dir/conf_file.
    conf_file may be a relative path to conf.
    '''
    conf_path = os.path.join(conf_dir, conf_file)
    try:
        with open(conf_path) as f:
            conf = json.loads(f.read())
        logging.debug("Loaded: '%s'", conf_path)
    except IOError as err:
        logging.error(str(err))
        raise RuntimeError(str(err))

    return conf

def load_ini_file(ini_dir, ini_file):
    '''
    Load githooks .ini configuration from ini_dir/ini_file.
    '''
    ini = ConfigParser.SafeConfigParser()

    ini_path = os.path.join(ini_dir, ini_file)
    try:
        with open(ini_path) as f:
            ini.readfp(f)
    except IOError as err:
        logging.error(str(err))
        raise RuntimeError(str(err))

    return ini

def load_hooks(config, params, ini, repo=os.getcwd()):
    hooks = []
    for hook in config:
        hook_env = params
        # Load hook specific environment from githooks .ini
        try:
            hook_env.update(dict(ini.items(hook)))
        except Exception as err:
            logging.debug(str(err))

        # Load the hooks from hooks_dir
        try:
            module = __import__(hook)
            hooks.append(module.Hook(repo, config[hook], hook_env))
        except ImportError as err:
            message = "Could not load hook: '%s' (%s)" % (hook, str(err))
            logging.error(message)
            raise RuntimeError(message)
    return hooks


if __name__ == '__main__':
    params = configure_defaults()

    ini = load_ini_file(this_file_path, 'githooks.ini')
    # Override default params
    if ini.defaults():
        params.update(dict(ini.defaults()))

    # Set up logging
    logging.basicConfig(format='%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s',
                        level=logging.DEBUG,
                        filename=params['log_file'])
    logging.debug("In '%s'", os.getcwd())

    conf_file = sys.argv[1]
    conf = load_conf_file(params['conf_dir'], conf_file)

    stdin = sys.argv[2:]

    hooks = load_hooks(conf, params, ini)

    permit = True

    # Read in each ref that the user is trying to update.
    for line in fileinput.input(stdin):
        old_sha, new_sha, branch = line.strip().split(' ')

        for hook in hooks:
            status, messages = hook.check(branch, old_sha, new_sha)

            for message in messages:
                print "[%s @ %s]: %s" % (branch, message['at'], message['text'])

            permit = permit and status

    if not permit:
        sys.exit(1)

    sys.exit(0)
