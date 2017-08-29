"""Provides an interface the QCDB Server instance"""

import json
from tornado import gen, httpclient, ioloop
import pandas as pd

from . import mongo_helper


class Client(object):
    def __init__(self, port, project="default"):
        if "http" not in port:
            port = "http://" + port
        self.port = port + '/'
        self.project = project
        self.info = self.get_information()

    def get_MongoSocket(self):
        """
        Builds a new MongoSocket from the internal data.
        """
        socket = mongo_helper.MongoSocket(*self.info["mongo_data"])
        socket.set_project(self.project)
        return socket

    @gen.coroutine
    def _query_server(self, function, method, body=None):
        """
        Basic non-blocking server query.
        """
        if body is not None:
            body = json.dumps(body)

        client = httpclient.AsyncHTTPClient()
        http_header = {"project" : self.project}
        yield json.loads(client.fetch(self.port + function, method=method, headers=http_header).body.decode('utf-8'))

    def query_server(self, function, method, body=None, json_load=True):
        """
        Basic blocking server query.
        """
        if body is not None:
            body = json.dumps(body)

        client = httpclient.HTTPClient()
        http_header = {"project" : self.project}
        response = client.fetch(self.port + function, method=method, body=body, headers=http_header, request_timeout=30.0)
        return json.loads(response.body.decode('utf-8'))

    def get_information(self):
        return self.query_server("information", "GET")

    def submit_task(self, json_data):
        return self.query_server("scheduler", "POST", body=json_data)

    def get_queue(self):
        return self.query_server("scheduler", "GET")

    def mongod_query(self, *args, **kwargs):
        json_data = {}

        json_data["function"] = args[0]
        json_data["args"] = args[1:]
        json_data["kwargs"] = kwargs
        ret = self.query_server("mongod", "POST", body=json_data)
        if isinstance(ret, dict) and ("pandas_msgpack" in list(ret)):
            ret = pd.read_json(ret["data"])

        return ret
