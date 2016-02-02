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
import itertools
from textwrap import wrap
import logging
import hookconfig
import hookutil


class Hook(object):

    def __init__(self, repo_dir, settings):
        self.repo_dir = repo_dir
        self.settings = settings
        try:
            self.repo = os.environ['STASH_REPO_NAME']
            self.proj = os.environ['STASH_PROJECT_KEY']
        except KeyError as key:
            logging.error("%s not in env", key)
            raise RuntimeError("%s not in env" % key)

    def compose_mail(self, branch, old_sha, new_sha, pusher):
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
                for owner in owners_attr.split(','):
                    if hookconfig.get_username(owner) == pusher:
                        logging.warning("Pusher '%s' owns '%s', skip", pusher, modfile['path'])
                        continue

                    files.append({'owner':owner, 'commit':commit, 'path':modfile})

        mails = {}
        for owner, commits in itertools.groupby(files, key=lambda ko: ko['owner']):
            text = '<b>Branch:</b> %s\n' % branch.replace('refs/heads/', '')
            text += '<b>By user:</b> %s\n' % pusher
            text += '\n'

            for commit, paths in itertools.groupby(commits, key=lambda kc: kc['commit']):
                link = hookconfig.stash_server + \
                    "/projects/%s/repos/%s/commits/%s\n" % (self.proj, self.repo, commit['commit'])

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

    def check(self, branch, old_sha, new_sha, pusher):
        logging.debug("branch='%s', old_sha='%s', new_sha='%s', pusher='%s'",
                      branch, old_sha, new_sha, pusher)

        mails = self.compose_mail(branch, old_sha, new_sha, pusher)

        messages = []
        if mails:
            hookutil.send_mail(mails, hookconfig.send_from,
                               "%s/%s - Hook notify: Files you own were modified" % (self.proj, self.repo))
            # messages.append("Notified users %s" % ', '.join(mails.keys()))

        return True, messages
