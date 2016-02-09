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
hookutil: Hook utilities
'''

import subprocess
import tempfile
import os
import sys
import re
import logging

import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
from email.Utils import formatdate, make_msgid

import hookconfig


def run(cmd, exec_dir=os.getcwd(), env=None, check_ret=True):
    '''
    Execute a command in 'exec_dir' directory.
    '''
    log_cmd = ' '.join(cmd[:10] + [" ... (cut %s)" % (len(cmd)-10)] if len(cmd) > 10 else cmd)
    logging.debug("Run cmd: '%s'", log_cmd)

    proc = subprocess.Popen(cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd=exec_dir,
                            env=env)
    out, err = proc.communicate()
    ret = proc.returncode

    if check_ret and ret != 0:
        logging.error("Command '%s' returned non-zero exit status %s", log_cmd, ret)
        raise subprocess.CalledProcessError(ret, log_cmd)

    return ret, out, err


def get_attr(repo_dir, new_sha, filename, attr):
    '''
    Get git attribute 'attr' of file 'filename'.

    - repo_dir: repository root
    - new_sha: git object hash
    '''
    idx_file = tempfile.mkstemp(suffix='git_index')[1]

    # Create an index from new_sha.
    cmd = ['git', 'read-tree', new_sha, '--index-output', idx_file]
    run(cmd, repo_dir)

    # Get the attr only from the index.
    env = os.environ.copy()
    env['GIT_INDEX_FILE'] = idx_file
    cmd = ['git', 'check-attr', '--cached', attr, '--', filename]
    _, out, _ = run(cmd, repo_dir, env)

    os.remove(idx_file)

    # Parse 'git check-attr' output.
    chunks = [c.strip() for c in out.split(':')]
    assert chunks[0] == filename
    assert chunks[1] == attr
    logging.debug("filename='%s', %s='%s'", filename, attr, chunks[2])

    return chunks[2]


def parse_git_log(repo, branch, old_sha, new_sha):
    '''
    Parse 'git log' output. Return an array of dictionaries:
        {
            'commit': commit hash,
            'author_name': commit author name,
            'author_email': commit author email,
            'date': commit date,
            'message': commit message
        }
    for each commit.
    '''
    git_commit_fields = ['commit', 'author_name', 'author_email', 'date', 'message']
    git_log_format = '%x1f'.join(['%H', '%an', '%ae', '%ad', '%s']) + '%x1e'

    # Get all commits that exist only on the branch
    # being updated, and not any others
    # See http://stackoverflow.com/questions/5720343/

    # Get all refs in the repo
    _, refs, _ = run(['git', 'for-each-ref', '--format=%(refname)'], repo)
    refs = refs.splitlines()
    # Remove the branch being pushed
    if branch in refs:
        refs.remove(branch)

    cmd = ['git', 'log', '--format=' + git_log_format]
    if old_sha == '0' * 40:
        # It's a new branch
        cmd += [new_sha]
    else:
        # It's an old branch, look only in this range
        cmd += ["%s..%s" % (old_sha, new_sha)]

    # Exclude commits that exist in the repo
    if refs:
        cmd += ['--not'] + refs

    _, log, _ = run(cmd, repo)

    if not log:
        logging.debug("Empty git log")
        return {}

    log = log.strip('\n\x1e').split("\x1e")
    log = [row.strip().split("\x1f") for row in log]
    log = [dict(zip(git_commit_fields, row)) for row in log]

    for raw in log:
        logging.debug("Parsed row: '%s'", raw)

    return log


def parse_git_show(repo, sha, extensions=None):
    '''
    Parse 'git show' output. Return an arrays of dictionaries:
        {
            'path': path fo file,
            'status': modified, added, deleted, renamed or copied,
            'old_blob': old blob hash,
            'new_blob': new blob hash
        }
    for each modified file.
    '''
    def extension_match(filepath, extensions=None):
        '''
        Check if file extension matches any of the passed.

        - extension: an arrays of extension strings
        '''
        if extensions is None:
            return True
        return any(filepath.endswith(ext) for ext in extensions)

    assert sha != '0' * 40
    cmd = ['git', 'show', '--first-parent', '--raw', '--no-abbrev', '--format=', sha]
    _, show, _ = run(cmd, repo)

    git_show_fields = ('old_blob', 'new_blob', 'status', 'path')
    show_json = []
    for line in show.splitlines():
        # Parse git raw lines:
        # :100755 100755 7469841... 7399137... M  githooks.py
        match = re.match(r"^:\d{6}\s\d{6}\s([a-z0-9]{40})\s([a-z0-9]{40})\s([MAD])\s+(.+)$",
                         line)
        if not match:
            logging.error("Could not parse 'git show' output: '%s'" % line)
            continue

        # Check if file extension matches any of the passed.
        path = match.group(4)
        if extension_match(path, extensions):
            show_json.append(dict(zip(git_show_fields, match.groups())))
            logging.debug("Parsed row: '%s'", show_json[-1])

    return show_json


def send_mail(mail_to, smtp_from, subject):
    '''
    Connect to the server once and send all mails
    from 'mail_to' dictionary. Contains emails as
    keys and messages to send as values.

    smtp_to: the sender
    subject: subject line, common for all mails
    '''
    if not mail_to:
        logging.debug('No mails to send, mail_to empty')
        return

    smtp_server = hookconfig.smtp_server
    smtp_port = hookconfig.smtp_port

    logging.debug("Connecting to the server '%s:%s'", smtp_server, smtp_port)
    smtp = smtplib.SMTP(smtp_server, smtp_port)
    logging.debug('Connected.')
    smtp.set_debuglevel(0)

    for send_to in mail_to:
        text = mail_to[send_to]

        msg_root = MIMEMultipart('related')
        msg_root['From'] = smtp_from
        msg_root['To'] = send_to
        msg_root['Date'] = formatdate(localtime=True)
        msg_root['Message-ID'] = make_msgid()
        msg_root['Subject'] = subject
        msg_root.preamble = 'This is a multi-part message in MIME format.'

        msg = MIMEMultipart('alternative')
        msg.set_charset('utf-8')

        msg_root.attach(msg)

        # Wrapping text to the simple html header
        text = '<HTML><BODY><div><pre>' + text + '</pre></div></BODY></HTML>'

        # Attaching text to the letter
        msg_text = MIMEText(text.encode(
            'utf-8', 'replace'), 'html', _charset='utf-8')
        msg.attach(msg_text)

        email_file_data = msg_root.as_string()

        smtp.sendmail(smtp_from, send_to, email_file_data)
        logging.debug("Sent outgoing email to '%s'", send_to)

    smtp.close()
