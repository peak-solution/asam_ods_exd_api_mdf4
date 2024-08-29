# docker build --tag docker.peak-solution.de/exd_api/np_mdf4 .
FROM python:3.12-slim
WORKDIR /app
# Install required packages
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
# Copy ASAM ODS Interface files into container
## Download from ASAM ODS github repository
ADD https://raw.githubusercontent.com/asam-ev/ASAM-ODS-Interfaces/main/ods.proto /app/
ADD https://raw.githubusercontent.com/asam-ev/ASAM-ODS-Interfaces/main/ods_external_data.proto /app/
## Use local copy
# COPY proto_src/ods.proto ods.proto
# COPY proto_src/ods_external_data.proto ods_external_data.proto
# Use protoc to compile stubs in container
RUN python3 -m grpc_tools.protoc -I. --python_out=. ods.proto
RUN python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. ods_external_data.proto
# Copy Plugin Implementation
COPY exd_api_server.py exd_api_server.py
COPY external_data_reader.py external_data_reader.py
# Start server
CMD [ "python3", "exd_api_server.py"]