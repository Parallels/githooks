#!/usr/bin/env python
# Example githooks configuration file
import os

#
# githooks developer email
#
# Used in test.TestNotify
#
devmail = None

#
# Stash and external-hooks environment
#
stash_server = os.environ['STASH_BASE_URL']
# githooks root directory
safe_dir = os.path.join(os.environ['STASH_HOME'], 'external-hooks')
# githooks configuration files
config_dir = os.path.join(safe_dir, 'conf')

logfile = os.path.join(os.environ['STASH_HOME'], 'log', 'atlassian-stash-githooks.log')
pusher = os.environ['STASH_USER_NAME']

#
# SMTP relay settings
#
# Used in hooks.d/hookutil.py
# This is restricted Gmail SMTP server - does not require authentication,
# and you will be restricted to send messages to Gmail or Google
# Apps users only.
#
smtp_server = 'aspmx.l.google.com'
smtp_port = 25
send_from = devmail

#
# get_username
#
# Used in notify.py to check if pusher is file owner.
# Maps owner email address in .gitattributes to their Stash username.
# Also, can use to check owner's email address.
#
def get_username(email):
    if not email.endswith('@gmail.com'):
        raise RuntimeError(
            "'%s' is not a Google mail address" % email)

    email_map = {
        'karl@gmail.com': 'karl',
    }
    try:
        return email_map[email]
    except KeyError:
        return None
