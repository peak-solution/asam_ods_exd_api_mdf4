# ASAM ODS EXD-API MDF4 plugin

This repository contains a [ASAM ODS EXD-API](https://www.asam.net/standards/detail/ods/) plugin that uses [asammdf](https://pypi.org/project/asammdf/) to read the [ASAM MDF4](https://www.asam.net/standards/detail/mdf/wiki/) files.

> This is only a prototype to check if it works with [asammdf](https://pypi.org/project/asammdf/).


## GRPC stub

Because the repository does not contain the ASAM ODS protobuf files the generated stubs are added.
The files that match `*_pb2*` are generated using the following command. To renew them you must put the 
proto files from the ODS standard into `proto_src` and rerun the command.

```
python -m grpc_tools.protoc --proto_path=proto_src --pyi_out=. --python_out=. --grpc_python_out=. ods.proto ods_external_data.proto
```

## Content

### `exd_api_server.py`

Runs the GRPC service to be accessed using http-2.

### `external_data_reader.py`

Implements the EXD-API interface to access MDF4 files using [asammdf](https://pypi.org/project/asammdf/).

### `exd_api_test.py`

Some basic tests on example files in `data` folder.

### `example_access_exd_api_mdf4.ipynb`

jupyter notebook the shows communication done by ASAM ODS server or Importer using the EXD-API plugin.