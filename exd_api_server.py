"""
This is the script starting the GRPC server.
"""

# Prepare python to use GRPC interface:
# python -m grpc_tools.protoc --proto_path=proto_src --pyi_out=. --python_out=. --grpc_python_out=. ods.proto ods_external_data.proto

from concurrent import futures
import logging

import grpc
import ods_external_data_pb2_grpc

from external_data_reader import ExternalDataReader


def serve():
    """
    Start the GRPC server hosting the External Data interface.
    The server is started at 50051 using http only.
    By default the server will use https.
    """
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    ods_external_data_pb2_grpc.add_ExternalDataReaderServicer_to_server(ExternalDataReader(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    logging.basicConfig()
    serve()
