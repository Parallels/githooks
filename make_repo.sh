#!/bin/bash
# -*- coding: utf-8 -*-
# vim:ts=4:sw=4:expandtab
#
#   Deploy test environment for githooks
#
# This script deploys githooks in a Stash-alike environment
# STASH_HOME=$PWD/testroot/stash. It installs githooks in
# $STASH_HOME/external-hooks (external-hooks plugin safe-dir).
# See:
#
# https://github.com/ngsru/atlassian-external-hooks/wiki/Configuration
#
#
# Also, the script initializes:
#
# 1. An empty remote repository in $PWD/testroot/remote_repo.git
# and installs githooks sample configuration files:
#   - pre-receive.conf.sample
#   - post-receive.conf.sample
#   - githooks.ini
# in $STASH_HOME/external-hooks/conf.
#
# 2. A local repository in $PWD/testroot/repo and sets it
# to track $PWD/testroot/remote_repo.git.
#


test_root=`pwd`/tmp
rm -rf $test_root
mkdir $test_root

export STASH_HOME=$test_root/stash
export STASH_USER_NAME=$USER
export STASH_BASE_URL="http://STASH"
export STASH_PROJECT_KEY="LOCAL"
export STASH_REPO_NAME="test"

mkdir $STASH_HOME
mkdir $STASH_HOME/log
mkdir -p $STASH_HOME/external-hooks/hooks.d
mkdir -p $STASH_HOME/external-hooks/conf/$STASH_PROJECT_KEY/$STASH_REPO_NAME

# Set up the hooks
cp githooks.py $STASH_HOME/external-hooks
cp hooks.d/*.py $STASH_HOME/external-hooks/hooks.d
chmod +x $STASH_HOME/external-hooks/githooks.py
chmod +x $STASH_HOME/external-hooks/hooks.d/*.py
# Copy hook configuration files
cp githooks.ini $STASH_HOME/external-hooks
cp `pwd`/pre-receive.conf.sample $STASH_HOME/external-hooks/conf/$STASH_PROJECT_KEY/$STASH_REPO_NAME/pre-receive.conf
cp `pwd`/post-receive.conf.sample $STASH_HOME/external-hooks/conf/$STASH_PROJECT_KEY/$STASH_REPO_NAME/post-receive.conf

# Init a remote repo.
mkdir $test_root/remote_repo.git
git init --bare $test_root/remote_repo.git

echo '#!/bin/bash' > $test_root/remote_repo.git/hooks/pre-receive
echo "$STASH_HOME/external-hooks/githooks.py $STASH_PROJECT_KEY/$STASH_REPO_NAME/pre-receive.conf < /dev/stdin" >> $test_root/remote_repo.git/hooks/pre-receive
chmod +x $test_root/remote_repo.git/hooks/pre-receive

echo '#!/bin/bash' > $test_root/remote_repo.git/hooks/post-receive
echo "$STASH_HOME/external-hooks/githooks.py $STASH_PROJECT_KEY/$STASH_REPO_NAME/post-receive.conf < /dev/stdin" >> $test_root/remote_repo.git/hooks/post-receive
chmod +x $test_root/remote_repo.git/hooks/post-receive

# Init a local repo.
mkdir $test_root/repo
git init $test_root/repo

git -C $test_root/repo remote add origin $test_root/remote_repo.git
