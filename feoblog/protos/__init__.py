"""
This module/directory contains files generated from the included copy of
https://github.com/NfNitLoop/feoblog/blob/develop/protobufs/feoblog.proto

You can regenerate them with the command:

protoc --proto_path=. --python_out=. ./feoblog.proto

"""

# reexport with a nicer name:

from .feoblog_pb2 import *