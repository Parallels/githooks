#!/usr/bin/env python

import os
import sys
import socket
import json
import time

data = json.dumps(sys.argv[1:])

request = os.path.join(os.getcwd(), '..', 'request.json')
response = os.path.join(os.getcwd(), '..', 'response.json')

with open(request, 'w+') as req:
    req.write(data)

attempts = 0
while 1:
    if not os.path.exists(response):
        attempts = attempts + 1
        time.sleep(0.1)
    else:
        break

    if attempts >= 200:
        raise RuntimeError('Timeout exceeded')

with open(response) as f:
    data = json.loads(f.read())
os.remove(response)

code = data[0]
text = data[1]

print text
sys.exit(code)
