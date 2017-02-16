#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim:ts=4:sw=4:expandtab
#
# ==================================================================
#
# Copyright (c) 2016-2017, Parallels International GmbH
# Released under the terms of MIT license (see LICENSE for details)
#
# ==================================================================
#
'''
copyright: A hook to check copyright string
'''

import re
import datetime
import logging
import hookutil


class Hook(object):

    def __init__(self, repo_dir, settings, params):
        self.repo_dir = repo_dir
        # Replace '%Y' in copyright string with current year
        self.settings = [(copyright['start'].replace('%Y', str(datetime.date.today().year)), copyright['full'].replace('%Y', str(datetime.date.today().year))) for copyright in settings]
        self.params = params

    def check(self, branch, old_sha, new_sha):
        logging.debug("Run: branch=%s, old_sha=%s, new_sha=%s",
                      branch, old_sha, new_sha)
        logging.debug("params=%s", self.params)

        if not self.settings:
            return True, []

        permit = True

        # Do not run the hook if the branch is being deleted
        if new_sha == '0' * 40:
            logging.debug("Deleting the branch, skip the hook")
            return True, []

        # Before the hook is run git has already created
        # a new_sha commit object

        log = hookutil.parse_git_log(self.repo_dir, branch, old_sha, new_sha, this_branch_only=False)

        messages = []
        for commit in log:
            modfiles = hookutil.parse_git_show(self.repo_dir, commit['commit'])

            def has_good_copyright(file_contents, copyrights):
                '''
                Check if file contains good copyright string
                '''
                for (start, full) in copyrights:
                    if re.search(start, file_contents):
                        if not re.search(full, file_contents):
                            return False
                return True

            for modfile in modfiles:
                # Skip deleted files
                if modfile['status'] == 'D':
                    logging.debug("Deleted %s, skip", modfile['path'])
                    continue

                cmd = ['git', 'show', modfile['new_blob']]
                _, file_contents, _ = hookutil.run(cmd, self.repo_dir)

                permit_file = has_good_copyright(file_contents, self.settings)
                logging.debug("modfile='%s', permit_file='%s'", modfile['path'], permit_file)

                if not permit_file:
                    messages.append({'at': commit['commit'],
                        'text': "Error: Bad copyright in file '%s'!" % modfile['path']})
                permit = permit and permit_file

        if not permit:
            text = 'Please update the copyright strings to match one of the following:\n\n\t- ' + '\n\t- '.join([full for (start, full) in self.settings])
            messages.append({'at': new_sha, 'text': text + '\n'})

        logging.debug("Permit: %s", permit)

        return permit, messages
