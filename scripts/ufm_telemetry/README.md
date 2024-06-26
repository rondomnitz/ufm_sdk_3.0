UFM Telemetry
--------------------------------------------------------


This plugin is used to load UFM telemetry counters and metrics.

Overview
--------------------------------------------------------

NVIDIA UFM Telemetry platform provides network validation tools to monitor network performance and conditions, capturing and streaming rich real-time network telemetry information, application workload usage to an on-premise or cloud-based database for further analysis.
As a fabric manager, the UFM Telemetry holds a real-time network telemetry information of the network topology.


Prerequisites
--------------------------------------------------------

To install all prerequisites, please run :

    pip install -r requirements.txt

To exported your repository to PYTHONPATH, please run :

   export PYTHONPATH="${PYTHONPATH}:<your ufm_sdk_cookbook path>"


Run
--------------------------------------------------------
### 1. Using command line arguments :

    python3 load_telemetry.py --ufm_telemetry_host=<ufm_telemetry_host> --ufm_telemetry_port=<ufm_telemetry_port> --ufm_telemetry_url=<ufm_telemetry_url>

### 2. using configuration file:

  - Copy config file sample telemetry.sample.cfg to telemetry.cfg


        cp telemetry.sample.cfg telemetry.cfg

  - Edit config file with relevant parameters


        vi telemetry.cfg
    

  - Run


        python3 ufm-topology.py
      
 Configuration Parameters Details:
--------------------------------------------------------

| Parameter | Required | Description |
| :---: | :---: |:---: |
| [ufm-telemetry-endpoint.host](telemetry.sample.cfg#L2) | True | Hostname or IPv4 or IPv6 for The UFM Telemetry Endpoint [Default is 127.0.0.1]
| [ufm-telemetry-endpoint.port](telemetry.sample.cfg#L3) | True | Port for The UFM Telemetry Endpoint [Default is 9001]
| [ufm-telemetry-endpoint.url](telemetry.sample.cfg#L4) | True | URL for The UFM Telemetry Endpoint [Default is 'labels/csv/metrics', for Prometheus format you can use 'labels/metrics']

