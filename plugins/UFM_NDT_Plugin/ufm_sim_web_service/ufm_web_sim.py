"""
@copyright:
    Copyright (C) Mellanox Technologies Ltd. 2021. ALL RIGHTS RESERVED.

    This software product is a proprietary product of Mellanox Technologies
    Ltd. (the "Company") and all right, title, and interest in and to the
    software product, including all associated intellectual property rights,
    are and shall remain exclusively with the Company.

    This software product is governed by the End User License Agreement
    provided with the software product.

@author: Nahum Kilim
@date:   September 20, 2021
"""

import configparser
from flask import Flask
from flask_restful import Api
import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler

from twisted.web.wsgi import WSGIResource
from twisted.internet import reactor
from twisted.web import server

from resources import Compare, Ndts, Reports, ReportId, UploadMetadata, Delete, Cancel


class UFMWebSim:
    def parse_config(self):
        ndt_config = configparser.ConfigParser()
        # config_file_name = "/config/ndt.conf"
        config_file_name = "../build/config/ndt.conf"
        if os.path.exists(config_file_name):
            ndt_config.read(config_file_name)
            self.log_level = ndt_config.get("Common", "log_level",
                                            fallback=logging.INFO)
        logging.basicConfig(filename="/tmp/ndt.log",
                            level=logging.getLevelName(self.log_level))
        # logging.basicConfig(filename="/data/ndt.log",
        #                     level=logging.getLevelName(self.log_level))

    def init_apis(self):
        default_apis = {
            Ndts: "/list",
            Reports: "/reports",
            Delete: "/delete",
            UploadMetadata: "/upload_metadata",
            ReportId: "/reports/<report_id>",
        }
        for resource, path in default_apis.items():
            self.api.add_resource(resource, path)

        self.api.add_resource(Cancel, "/cancel", resource_class_kwargs={'scheduler': self.scheduler})
        self.api.add_resource(Compare, "/compare", resource_class_kwargs={'scheduler': self.scheduler})

    def __init__(self):
        self.log_level = logging.INFO
        self.port_number = 8980
        self.app = Flask(__name__)
        self.api = Api(self.app)
        self.scheduler = BackgroundScheduler(daemon=True)

        self.parse_config()
        self.init_apis()

    async def run(self):
        self.app.run(port=self.port_number, debug=True)
        # resource = WSGIResource(reactor, reactor.getThreadPool(), self.app)
        # reactor.listenTCP(self.port_number, server.Site(resource))
        # reactor.run()

    async def stop(self):
        pass