#!/bin/bash
cd /datayes/release
ansible-playbook ansi/mdl/deploy_feeder.yml -i ansi/mdl/hosts \
  --extra-vars "version=2.13.232-1064 executable=feeder_handler" -vvv \
  > /tmp/ansible_debug.log 2>&1
echo "done, exit code: $?"
