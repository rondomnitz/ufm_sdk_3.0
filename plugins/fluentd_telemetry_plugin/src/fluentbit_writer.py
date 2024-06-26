#!/usr/bin/python3

"""
@copyright:
    Copyright (C) Mellanox Technologies Ltd. 2014-2020.  ALL RIGHTS RESERVED.

    This software product is a proprietary product of Mellanox Technologies
    Ltd. (the "Company") and all right, title, and interest in and to the
    software product, including all associated intellectual property rights,
    are and shall remain exclusively with the Company.

    This software product is governed by the End User License Agreement
    provided with the software product.

@author: Anan Al-Aghbar
@date:   Mar 10, 2024

This file originally is based on the clxcli writer
https://gitlab-master.nvidia.com/telemetry/Collectx/-/blob/master/server/exporter/fluentbit_writer.py
"""
import time
import datetime
from ctypes import Structure, CDLL, POINTER, pointer,\
    cast, c_char_p, c_void_p, c_int
import msgpack

# pylint: disable=no-name-in-module,import-error
from utils.logger import Logger, LOG_LEVELS
from utils.fluentd.fluent import asyncsender as asycsender
from utils.utils import Utils


LIB_RAW_MSGPACK_API_SO_PATH = '/opt/ufm/telemetry/collectx/lib/libraw_msgpack_api.so'
DEFAULT_FB_PLUGIN_NAME = 'forward'
DEFAULT_FB_HOST = '127.0.0.1'
DEFAULT_FB_PORT = '24224'


def str2c_char_ptr(str_val):
    return c_char_p(str_val.encode('utf-8'))


def load_api_lib_from_path(path):
    if not path:
        return None
    try:
        api_lib = CDLL(path)
        Logger.log_message(f'opened raw_msgpack API lib: {api_lib}', LOG_LEVELS.DEBUG)
        return api_lib
    except Exception as ex:  # pylint: disable=broad-except
        Logger.log_message(f'Failed to load the API: {path}, due to the error: {str(ex)}', LOG_LEVELS.DEBUG)
        return None


class LoadFBLibFailure(Exception):
    """LoadFBLibFailure Exception"""


class InitFBLibFailure(Exception):
    """InitFBLibFailure Exception"""


class ParamPair(Structure):
    """ParamPair Structure class"""
    _fields_ = [("name", c_char_p), ("val", c_char_p)]


class PluginParams(Structure):
    """
    PluginParams Structure class
    for initializing and managing the FB plugin's params
    """
    _fields_ = [("param_count", c_char_p), ("params", POINTER(ParamPair))]

    def __init__(self, params_count, in_plugin_params):  # pylint: disable=super-init-not-called
        elems = (ParamPair * params_count)()
        self.params = cast(elems, POINTER(ParamPair))
        self.param_count = params_count

        i = 0
        for p_name, p_val in in_plugin_params.items():
            self.params[i].name = str2c_char_ptr(p_name.replace("plugin_", ""))
            self.params[i].val = str2c_char_ptr(p_val)
            i += 1


class FluentBitCWriter:
    """
    FluentBitCWriter class
    Wrapper class for sending the FB messages via a given plugin
    """

    def __init__(self, context):
        self.initialized = False
        self.raw_msgpack_api_ctx = None
        self.lib = None
        self.lib_path = None

        self.plugin_name = context.get('plugin_name', DEFAULT_FB_PLUGIN_NAME)
        self.host = context.get('plugin_host', DEFAULT_FB_HOST) # could be IPv4, IPv6 or Hostname
        self.port = context.get('plugin_port', DEFAULT_FB_PORT)

        self.lib = context.get('so_lib')
        self.tag_prefix = context.get('tag_prefix', '')
        # the tag will be determined on each write
        # we may use the same fluent writer to send multiple messages with different tags
        self.tag = None

        if not self.lib:
            msg = "Cannot find 'libraw_msgpack_api.so'. Cannot export with Fluent-Bit."
            Logger.log_message(msg, LOG_LEVELS.ERROR)
            raise LoadFBLibFailure(msg)

    def __del__(self):
        self.close_connection()

    def _init_lib_args(self, tag):
        plugin_params = {
            'tag_match_pair': f'{self.tag_prefix}.{tag}'
        }
        self.tag = tag
        # init the lib args
        self.lib.init.argtypes = [c_char_p,
                                  c_char_p,
                                  c_char_p,
                                  c_void_p,
                                  c_char_p]
        self.lib.init.restype = c_void_p

        self.lib.add_data.argtypes = [c_void_p, c_void_p, c_int]
        self.lib.finalize.argtypes = [c_void_p]

        input_params = FluentBitCWriter.prepare_input_params(plugin_params)
        self.raw_msgpack_api_ctx = self.lib.init(str2c_char_ptr(self.plugin_name),
                                                 str2c_char_ptr(self.host),
                                                 str2c_char_ptr(self.port),
                                                 input_params,
                                                 str2c_char_ptr("TFS"))
        self.initialized = True

        if not self.raw_msgpack_api_ctx:
            msg = "Cannot create raw_msgpack_api_ctx", LOG_LEVELS.ERROR
            Logger.log_message(msg)
            raise LoadFBLibFailure(msg)

    @staticmethod
    def prepare_input_params(in_plugin_params):
        params_count = len(in_plugin_params)
        if params_count == 0:
            return None
        ret = PluginParams(params_count, in_plugin_params)
        ret_p = pointer(ret)
        ret_void_p = cast(ret_p, c_void_p)
        return ret_void_p

    @staticmethod
    def prepare_flb_std_record(record):
        timestamp = int(time.time())
        return [timestamp, record]

    def write(self, label, data):
        if not self.lib:
            msg = "Cannot write with fluent-bit. API is not initialized"
            Logger.log_message(msg, LOG_LEVELS.WARNING)
            raise InitFBLibFailure(msg)

        if not self.initialized or self.tag != label:
            self._init_lib_args(tag=label)

        new_record = FluentBitCWriter.prepare_flb_std_record(data)

        buf_packed = msgpack.packb(new_record, use_bin_type=True)

        bytes_num = len(buf_packed)

        self.lib.add_data(self.raw_msgpack_api_ctx, buf_packed, bytes_num)

    def close_connection(self):
        if not self.lib:
            return
        if self.initialized:
            self.initialized = False
            self.lib.finalize(self.raw_msgpack_api_ctx)


def init_fb_writer(host, port, tag_prefix, timeout=120, use_c=True):
    if use_c:
        lib = load_api_lib_from_path(LIB_RAW_MSGPACK_API_SO_PATH)
        ctx = {
            'plugin_name': 'forward',
            'plugin_host': host,
            'plugin_port': str(port),
            'msgpack_data_layout': 'standard',
            'so_lib': lib,
            'tag_prefix': tag_prefix
        }
        fluent_writer = FluentBitCWriter(ctx)
        init_msg = 'Fluent sender is initialized in C'
    else:
        # use the fluentd's python sender
        fluent_writer = asycsender.FluentSender(tag_prefix, host, int(port), timeout=timeout)
        init_msg = 'Fluent sender is initialized in Python'
    Logger.log_message(init_msg, LOG_LEVELS.DEBUG)
    return fluent_writer


if __name__ == '__main__':
    # Example on how to set & use the FB writer
    _USE_C = True
    _HOST = DEFAULT_FB_HOST
    _PORT = DEFAULT_FB_PORT
    _TAG = 'UFM_Telemetry_Streaming'
    msg_record = Utils.read_json_from_file('../tests/message_samples/small_telemetry.json')
    writer = init_fb_writer(_HOST, _PORT, _TAG, use_c=_USE_C)
    #####
    print(f"Start streaming on {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S%z')}, "
          f"{'Using the C writer' if _USE_C else 'Using the Python writer'}..")
    ##################
    writer.write(_TAG, msg_record)
    if _USE_C:
        time.sleep(30)
    print('Streaming is completed')
