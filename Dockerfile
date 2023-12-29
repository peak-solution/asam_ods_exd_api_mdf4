# docker build --tag docker.peak-solution.de/exd_api/np_mdf4 .
FROM python:3.8-slim-buster
WORKDIR /app
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt
COPY proto_src/ods.proto ods.proto
COPY proto_src/ods_external_data.proto ods_external_data.proto
RUN python3 -m grpc_tools.protoc -I. --python_out=. ods.proto
RUN python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. ods_external_data.proto
COPY exd_api_server.py exd_api_server.py
COPY external_data_reader.py external_data_reader.py
CMD [ "python3", "exd_api_server.py"]