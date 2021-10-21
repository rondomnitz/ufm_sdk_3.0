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

import json
import os
from flask_restful import Resource
from flask import request
from datetime import datetime, timedelta
from topo_diff.topo_diff import compare_topologies
import logging
import hashlib


def read_json_file(file_name):
    try:
        with open(file_name) as file:
            data = json.load(file)
    except Exception as ex:
        logging.error(ex)
        data = {}
    return data


class UFMResource(Resource):
    def __init__(self):
        self.response_file = ""
        self.reports_dir = "reports"
        self.ndt_files_dir = "ndt_files"
        # self.reports_dir = "/data/reports"
        # self.ndt_files_dir = "/data/ndt_files"
        self.reports_list_file = os.path.join(self.reports_dir, "reports_list.json")
        self.ndts_list_file = os.path.join(self.ndt_files_dir, "ndts_list.json")
        self.response_code = 200
        try:
            logging.info("Creating file for reports list")
            if not os.path.exists(self.reports_list_file):
                with open(self.reports_list_file, "w") as file:
                    json.dump([], file)

            logging.info("Creating file for NDTs list")
            if not os.path.exists(self.ndts_list_file):
                with open(self.ndts_list_file, "w") as file:
                    json.dump([], file)

        except Exception as ex:
            logging.error(ex)

    def get_ndt_path(self, file_name):
        return os.path.join(self.ndt_files_dir, file_name)

    def get_report_path(self, file_name):
        return os.path.join(self.reports_dir, file_name)

    def get(self):
        return read_json_file(self.response_file), self.response_code

    def post(self):
        pass


def get_timestamp():
    return str(datetime.now())


def get_hash(file_content):
    sha1 = hashlib.sha1()
    sha1.update(file_content.encode('utf-8'))
    return sha1.hexdigest()


class UploadMetadata(UFMResource):
    def post(self):
        logging.info("POST /plugin/ndt/upload_metadata")
        try:
            json_data = request.get_json(force=True)
            logging.debug("Parsing JSON request: {}".format(json_data))
            for file_dict in json_data:
                file_name = file_dict["file_name"]
                file_content = file_dict["file"]
                sha1 = get_hash(file_content)
                file_content = file_content.replace('\r\n', '\n')
                file_type = file_dict["file_type"]
                checksum = file_dict["sha-1"]

                if checksum != sha1:
                    logging.error("Provided sha-1 {} is not equal to actual one {}"
                                  .format(checksum, sha1))

                logging.debug("Updating NDTs list")
                with open(self.ndts_list_file, "r+") as file:
                    data = json.load(file)
                    if not os.path.exists(self.get_ndt_path(file_name)):
                        entry = {"file": file_name,
                                 "timestamp": get_timestamp(),
                                 "sha-1": sha1,
                                 "file_type": file_type}
                        logging.debug("New NDT: {}".format(entry))
                        data.append(entry)
                    else:
                        for entry in data:
                            if entry["file"] == file_name:
                                entry["timestamp"] = get_timestamp()
                                entry["sha-1"] = sha1
                                entry["file_type"] = file_type
                    file.seek(0)
                    json.dump(data, file)

                logging.debug("Uploading file: {}".format(file_name))
                with open(self.get_ndt_path(file_name), "w") as file:
                    file.write(file_content)

        except Exception as ex:
            logging.error(ex)


class Delete(UFMResource):
    def post(self):
        logging.info("POST /plugin/ndt/delete")
        try:
            json_data = request.get_json(force=True)
            logging.debug("Parsing JSON request: {}".format(json_data))
            with open(self.ndts_list_file, "r") as file:
                data = json.load(file)

                logging.debug("Looking for the file to delete")
                for file_dict in json_data:
                    file_name = file_dict["file_name"]
                    for entry in list(data):
                        if entry["file"] == file_name:
                            logging.debug("Deleting file: {}".format(entry))
                            data.remove(entry)
                            os.remove(self.get_ndt_path(file_name))

            logging.debug("Updating NDTs list")
            with open(self.ndts_list_file, "w") as file:
                json.dump(data, file)

        except Exception as ex:
            logging.error(ex)


class Compare(UFMResource):
    def __init__(self, scheduler):
        super().__init__()
        self.scheduler = scheduler

    def compare(self):
        logging.info("Run topology comparison")
        timestamp = get_timestamp()
        response = compare_topologies(timestamp, self.ndts_list_file)

        logging.debug("Updating NDTs list")
        with open(self.reports_list_file, "r+") as reports_list_file:
            data = json.load(reports_list_file)
            reports_number = len(data)
            if reports_number == 10:
                os.remove(self.get_report_path("report_1.json"))
                data.remove(data[0])
                data = [{key: report[key] - 1 for key in report if key == "report_id"} for report in data]
                reports_number = 9
            entry = {"report_id": reports_number + 1,
                     "timestamp": timestamp}
            self.response_file = os.path.join(self.reports_dir, "report_{}.json".format(reports_number + 1))
            logging.debug("Report file name: {}".format(self.response_file))
            with open(self.response_file, "w") as response_file:
                json.dump(response, response_file)
            data.append(entry)
            reports_list_file.seek(0)
            json.dump(data, reports_list_file)

    def post(self):
        try:
            logging.info("POST /plugin/ndt/compare")
            if request.data:
                json_data = request.get_json(force=True)
                logging.debug("Parsing JSON request: {}".format(json_data))
                params = json_data["run"]
                start_time = params["startTime"]
                datetime_start = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
                end_time = params["endTime"]
                datetime_end = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
                interval = params["interval"]
                while datetime_start <= datetime_end:
                    self.scheduler.add_job(func=self.compare, run_date=datetime_start)
                    datetime_start += timedelta(minutes=interval)
                self.scheduler.start()
            else:
                logging.info("Running instant topology comparison")
                self.compare()

        except Exception as ex:
            logging.error(ex)


class Cancel(UFMResource):
    def __init__(self, scheduler):
        super().__init__()
        self.scheduler = scheduler

    def get(self):
        try:
            self.scheduler.shutdown(wait=False)
        except Exception as ex:
            logging.error(ex)


class ReportId(UFMResource):
    def __init__(self):
        super().__init__()
        try:
            logging.debug("Loading reports list file")
            with open(self.reports_list_file, "r") as file:
                self.data = json.load(file)
        except Exception as ex:
            logging.error(ex)
            self.data = {}

    def get(self, report_id):
        logging.info("GET /plugin/ndt/reports")
        try:
            for entry in self.data:
                if entry["report_id"] == int(report_id):
                    self.response_file = \
                        os.path.join(self.reports_dir,
                                     "report_{}.json".format(report_id))
                    logging.debug("Report found: {}".format(self.response_file))
                    break
            else:
                logging.info("Report {} not found".format(report_id))
        except Exception as ex:
            logging.error(ex)
        finally:
            return super().get()


class Reports(UFMResource):
    def __init__(self):
        logging.info("GET /plugin/ndt/reports")
        super().__init__()
        self.response_file = self.reports_list_file


class Ndts(UFMResource):
    def __init__(self):
        logging.info("GET /plugin/ndt/list")
        super().__init__()
        self.response_file = self.ndts_list_file
