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
notify: A hook to check that file owners approved any changes made to their files

Files are assigned via .gitattributes:
*.py owners=karl@gmail.com

'owners' can be a list of emails separated by comma
'''

import requests
import itertools
import logging
from textwrap import wrap

import hookutil


class Hook(object):

    def __init__(self, repo_dir, settings, params):
        self.repo_dir = repo_dir
        self.settings = settings
        self.params = params

    def check(self, branch, old_sha, new_sha):
        logging.debug("Run: branch=%s, old_sha=%s, new_sha=%s",
                      branch, old_sha, new_sha)
        logging.debug("params=%s", self.params)

        try:
            base_url = self.params['base_url']
            proj_key = self.params['proj_key']
            repo_name = self.params['repo_name']
            pull_id = self.params['pull_id']
            pusher = self.params['pusher']
            user_name = self.params['user_name']
            user_passwd = self.params['user_passwd']
        except KeyError as err:
            logging.error("%s not in hook settings", err)
            raise RuntimeError("%s not in hook settings, check githooks configuration" % err)

        permit = False

        # Fetch pull request reviewers
        try:
            pr = requests.get("%s/rest/api/1.0/projects/%s/repos/%s/pull-requests/%s" % (base_url, proj_key, repo_name, pull_id), auth=(user_name, user_passwd))
            pr.raise_for_status()
        except Exception as err:
            err_msg = "Failed to fetch pull request data (%s)" % str(err)
            logging.error(err_msg)
            raise RuntimeError(err_msg)

        try:
            pr_reviewers = pr.json()['reviewers']

            reviewers = []
            for reviewer in pr_reviewers:
                if reviewer['role'] != 'REVIEWER':
                    continue

                email = reviewer['user']['emailAddress']
                if reviewer['approved']:
                    reviewers.append(email)
        except KeyError as key:
            logging.error("Failed to parse %s from pull request # %s data" % (pull_id, str(key)))
            raise RuntimeError("Failed to parse pull request # %s data (%s: no such key)" % (pull_id, str(key)))

        logging.debug("Pull request reviewers who approved: %s", reviewers)

        # Parse modified files per commit
        log = hookutil.parse_git_log(self.repo_dir, branch, old_sha, new_sha)

        files = []

        for commit in log:
            modfiles = hookutil.parse_git_show(self.repo_dir, commit['commit'])

            for modfile in modfiles:
                owners_attr = hookutil.get_attr(self.repo_dir, new_sha, modfile['path'], 'owners')
                if owners_attr == 'unspecified' or owners_attr == 'unset':
                    continue
                for owner in owners_attr.split(','):
                    # Skip this path as it is owned by the guy who merges the pull request
                    # Go to next modfile processing
                    if pusher == owner:
                        break

                    # Avoid mail groups here -- check if Bitbucket user exists
                    #
                    # Do not fail if a mail group found in the owners list;
                    # Those mail groups are valid for the change notification hook
                    try:
                        ru = requests.get("%s/rest/api/1.0/users/%s" % (base_url, owner.split('@')[0]), auth=(user_name, user_passwd))
                        ru.raise_for_status()
                    except Exception as err:
                        logging.error("Failed to fetch user %s data (%s)" % (owner, str(err)))
                        continue

                    if owner not in reviewers:
                        files.append({'commit':commit['commit'], 'owner':owner, 'path':modfile['path']})

        if not files:
            permit = True
            logging.debug("files = []; either all approved or no approve required, permit = %s", permit)
            return permit, []


        logging.debug("Unapproved files: %s", files)

        all_owners = list(set([f['owner'] for f in files]))
        if len(all_owners) > 1:
            all_owners_str = ', '.join(all_owners[:-1] + ' and ', all_owners[-1])
        else:
            all_owners_str = ''.join(all_owners)

        print '\n'.join(wrap("<h4>This pull request must be approved by %s!</h4>" % all_owners_str, width=80))
        print '\n'.join(wrap('Changes to the following files must be approved ' \
                             'by their owners as specified in .gitattributes. ' \
                             'Please add those people to the pull request reviewers '
                             'if you haven\'t done so and wait for them to approve.', width=80))
        print "<p>"
        print '\n'.join(wrap("List of files that require approval:", width=80))

        for path, files_by_path in itertools.groupby(sorted(files, key=lambda k: k['path']), key=lambda ko: ko['path']):
            path_owners = list(set([f['owner'] for f in files_by_path]))

            text = "<i>%s</i> by " % path

            if len(path_owners) > 1:
                text += ', '.join(path_owners[:-1] + ' or ', path_owners[-1])
            else:
                text += ''.join(path_owners)

            print '\n'.join(wrap(text, width=80))

        print "</p>"

        logging.debug("Permit: %s", permit)
        return permit, []
