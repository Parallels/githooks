#!/bin/bash
# -*- coding: utf-8 -*-
# vim:ts=4:sw=4:expandtab
#
#   Deploy a test repo for githooks
#
# This script deploys an empty remote repo in $PWD/tmp/remote_repo.git
# and installs githooks with sample configuration:
#   - pre-receive.conf.sample
#   - post-receive.conf.sample
# in there.
#
# Also, it initializes a local repo in $PWD/tmp/repo and sets it
# to track $PWD/tmp/remote_repo.git origin.
#


cwd=`pwd`

rm -rf $cwd/tmp
mkdir $cwd/tmp

# Init a remote repo.
mkdir $cwd/tmp/remote_repo.git
git init --bare $cwd/tmp/remote_repo.git

# Set up the hooks.
mkdir $cwd/tmp/remote_repo.git/log
export STASH_HOME=$cwd/tmp/remote_repo.git
export STASH_USER_NAME=$USER
export STASH_PROJECT_KEY="LOCAL"
export STASH_REPO_NAME="test"
mkdir -p $STASH_HOME/external-hooks
cp githooks.py $STASH_HOME/external-hooks
cp -r hooks.d $STASH_HOME/external-hooks
chmod +x $STASH_HOME/external-hooks/githooks.py
chmod +x $STASH_HOME/external-hooks/hooks.d/*.py

# Copy hook configs.
mkdir -p $STASH_HOME/external-hooks/conf
cp $cwd/pre-receive.conf.sample $STASH_HOME/external-hooks/conf/pre-receive.conf
cp $cwd/post-receive.conf.sample $STASH_HOME/external-hooks/conf/post-receive.conf

echo '#!/bin/bash' > $cwd/tmp/remote_repo.git/hooks/pre-receive
echo "./external-hooks/githooks.py pre-receive.conf < /dev/stdin" >> $cwd/tmp/remote_repo.git/hooks/pre-receive
chmod +x $cwd/tmp/remote_repo.git/hooks/pre-receive

echo '#!/bin/bash' > $cwd/tmp/remote_repo.git/hooks/post-receive
echo './external-hooks/githooks.py post-receive.conf < /dev/stdin' >> $cwd/tmp/remote_repo.git/hooks/post-receive
chmod +x $cwd/tmp/remote_repo.git/hooks/post-receive

# Init a local repo.
mkdir $cwd/tmp/repo
git init $cwd/tmp/repo

git -C $cwd/tmp/repo remote add origin $cwd/tmp/remote_repo.git
