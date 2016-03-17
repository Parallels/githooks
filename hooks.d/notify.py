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
notify: A hook to notify file owners of any changes made to their files

Files are assigned via .gitattributes:
*.py owners=karl@gmail.com

'owners' can be a list of emails separated by comma
'''

import os
import re
import itertools
from textwrap import wrap
import logging

import hookutil


class Hook(object):

    def __init__(self, repo_dir, settings, params):
        self.repo_dir = repo_dir
        self.settings = settings
        self.params = params

    def compose_mail(self, branch, old_sha, new_sha):
        pusher = self.params['user_name']
        base_url = self.params['base_url']
        proj_key = self.params['proj_key']
        repo_name = self.params['repo_name']

        # Before the hook is run git has already created
        # a new_sha commit object

        log = hookutil.parse_git_log(self.repo_dir, branch, old_sha, new_sha)

        files = []
        for commit in log:
            show = hookutil.parse_git_show(self.repo_dir, commit['commit'])
            for modfile in show:
                owners_attr = hookutil.get_attr(self.repo_dir, new_sha, modfile['path'], 'owners')
                if owners_attr == 'unspecified' or owners_attr == 'unset':
                    continue
                for owner in set(owners_attr.split(',')):
                    files.append({'owner':owner, 'commit':commit, 'path':modfile})

        files = sorted(files, key=lambda ko: ko['owner'])

        mails = {}
        for owner, commits in itertools.groupby(files, key=lambda ko: ko['owner']):
            text = '<b>Branch:</b> %s\n' % branch.replace('refs/heads/', '')
            text += '<b>By user:</b> %s\n' % pusher
            text += '\n'

            # No need to sort by commit hash because it is in order
            for commit, paths in itertools.groupby(commits, key=lambda kc: kc['commit']):
                link = base_url + \
                    "/projects/%s/repos/%s/commits/%s\n" % (proj_key, repo_name, commit['commit'])

                text += 'Commit: %s (%s)\n' % (commit['commit'], "<a href=%s>View in Stash</a>" % link)
                text += 'Author: %s %s\n' % (commit['author_name'], commit['author_email'])
                text += 'Date: %s\n' % commit['date']
                text += '\n'

                text += '\t%s' % '\n\t'.join(wrap(commit['message'][:100], width=70))
                if len(commit['message']) > 100:
                    text += '...'
                text += '\n\n'

                for path in paths:
                    text += '\t%s  %s\n' % (path['path']['status'], path['path']['path'])

                text += '\n\n'

            mails[owner] = text

        return mails

    def check(self, branch, old_sha, new_sha):
        logging.debug("Run: branch=%s, old_sha=%s, new_sha=%s",
                      branch, old_sha, new_sha)
        logging.debug("params=%s", self.params)

        try:
            pusher = self.params['user_name']
            proj_key = self.params['proj_key']
            repo_name = self.params['repo_name']
            smtp_server = self.params['smtp_server']
            smtp_port = self.params['smtp_port']
            smtp_from = self.params['smtp_from']
        except KeyError as err:
            logging.error("%s not in hook settings", err)
            raise RuntimeError("%s not in hook settings, check githooks configuration" % err)

        # Do not run the hook if the branch is being deleted
        if new_sha == '0' * 40:
            logging.debug("Deleting the branch, skip the hook")
            return True, []

        # Check if branch matches any of the whitelist
        for branch_re in self.settings:
            try:
                branch_rec = re.compile(branch_re)
            except re.error:
                logging.warning("Branch regexp '%s' does not compile, skip", branch_re)
                continue

            if branch_rec.match(branch):
                logging.debug("Matched: %s", branch_re)
                mails = self.compose_mail(branch, old_sha, new_sha)
                hookutil.send_mail(mails, smtp_from,
                    "%s/%s - Hook notify: Files you subscribed to were modified" % (proj_key, repo_name),
                    smtp_server, smtp_port)

                return True, []

        logging.debug("Branch %s does not match any of %s, skip the hook", branch, ', '.join(self.settings))

        return True, []
