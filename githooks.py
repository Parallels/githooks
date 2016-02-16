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

Executes hooks from hooks.d as specified in the configuration file
(passed as parameter). Reads stdin and passes it to each executed
hook.

On how to configure external hooks see
https://github.com/ngsru/atlassian-external-hooks/wiki/Configuration
'''

import os
import sys
import json
import ConfigParser
import fileinput
import logging


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


class Githooks(object):
    '''
    Initialize and run githooks.
    '''
    def __init__(self, conf_file, ini_file, repo_dir=os.getcwd()):
        self.this_file_path = os.path.dirname(unicode(__file__, sys.getfilesystemencoding()))

        self.params = configure_defaults()

        self.ini = self.__load_ini_file(ini_file)
        # Override default params
        if self.ini.defaults():
            self.params.update(dict(self.ini.defaults()))

        # Set up logging
        logging.basicConfig(format='%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s',
                            level=logging.DEBUG,
                            filename=self.params['log_file'])

        self.repo_dir = repo_dir
        logging.debug("In '%s'", self.repo_dir)

        self.conf = self.__load_conf_file(conf_file)

        sys.path.append(self.params['hooks_dir'])
        self.hooks = self.load()

    def __load_conf_file(self, conf_file):
        '''
        Load githooks configuration from conf_dir/conf_file.
        conf_file may be a relative path to conf.
        '''
        conf_dir = self.params['conf_dir']

        conf_path = os.path.join(conf_dir, conf_file)
        try:
            with open(conf_path) as f:
                conf = json.loads(f.read())
            logging.debug("Loaded: '%s'", conf_path)
        except IOError as err:
            logging.error(str(err))
            raise RuntimeError(str(err))

        return conf

    def __load_ini_file(self, ini_file):
        '''
        Load githooks .ini configuration from this_file_path/ini_file.
        '''
        ini_dir = self.this_file_path

        ini = ConfigParser.SafeConfigParser()

        ini_path = os.path.join(ini_dir, ini_file)
        try:
            with open(ini_path) as f:
                ini.readfp(f)
        except IOError as err:
            logging.error(str(err))
            raise RuntimeError(str(err))

        return ini

    def load(self):
        '''
        Load the hooks from hooks.d.
        '''
        params = self.params
        conf = self.conf
        ini = self.ini
        repo_dir = self.repo_dir

        hooks = []
        for hook in conf:
            hook_params = params

            # Load hook specific environment from githooks .ini
            try:
                hook_params.update(dict(ini.items(hook)))
            except Exception as err:
                logging.debug(str(err))

            # Load the hooks from hooks_dir
            try:
                module = __import__(hook)
                hooks.append(module.Hook(repo_dir, conf[hook], hook_params))
            except ImportError as err:
                message = "Could not load hook: '%s' (%s)" % (hook, str(err))
                logging.error(message)
                raise RuntimeError(message)

        return hooks

    def run(self, stdin):
        '''
        Run the hooks as specified in the given configuration file.
        Report messages and status.
        '''
        hooks = self.hooks

        permit = True

        # Read in each ref that the user is trying to update
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


if __name__ == '__main__':
    Githooks(conf_file=sys.argv[1], ini_file='githooks.ini').run(sys.argv[2:])
