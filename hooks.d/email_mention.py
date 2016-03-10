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
email_mention: A hook to notify users mentioned in commit messages

`git ci -m 'My cool new feature @someone'` to send this commit to
someone@domain. Domain is specified in githooks.ini.
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
        email_domain = self.params['email_domain']

        # Before the hook is run git has already created
        # a new_sha commit object

        log = hookutil.parse_git_log(self.repo_dir, branch, old_sha, new_sha)

        users = []
        for commit in log:
            for username in re.findall('(?:\W+|^)@(\w[\w\.]*\w|\w)', commit['message']):
                ci = commit.copy()
                ci.update({'user': username})
                users.append(ci)

        users = sorted(users, key=lambda ko: ko['user'])

        mails = {}
        for user, commits in itertools.groupby(users, key=lambda ko: ko['user']):
            text = '<b>Branch:</b> %s\n' % branch.replace('refs/heads/', '')
            text += '<b>By user:</b> %s\n' % pusher
            text += '\n'

            for commit in commits:
                link = base_url + \
                    "/projects/%s/repos/%s/commits/%s\n" % (proj_key, repo_name, commit['commit'])

                text += 'Commit: %s (%s)\n' % (commit['commit'], "<a href=%s>View in Stash</a>" % link)
                text += 'Author: %s %s\n' % (commit['author_name'], commit['author_email'])
                text += 'Date: %s\n' % commit['date']
                text += '\n'

                text += '\t%s' % '\n\t'.join(wrap(commit['message'], width=70))
                text += '\n\n'

            mails[user + '@' + email_domain] = text

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
            email_domail = self.params['email_domain']
        except KeyError as err:
            logging.error("%s not in hook settings", err)
            raise RuntimeError("%s not in hook settings, check githooks configuration" % err)

        # Do not run the hook if the branch is being deleted
        if new_sha == '0' * 40:
            logging.debug("Deleting the branch, skip the hook")
            return True, []

        mails = self.compose_mail(branch, old_sha, new_sha)
        hookutil.send_mail(mails, smtp_from,
            "%s/%s - Hook email-mention: You were mentioned in a commit message" % (proj_key, repo_name),
            smtp_server, smtp_port)

        return True, []

