
import grpc


class MockServicerContext(grpc.ServicerContext):
    def __init__(self):
        self._code = None
        self._details = None

    def cancel(self):
        pass

    def is_cancelled(self):
        return False

    def set_code(self, code):
        self._code = code

    def set_details(self, details):
        self._details = details

    def abort(self, code, details):
        self.set_code(code)
        self.set_details(details)
        raise grpc.RpcError(details)

    def abort_with_status(self, status):
        self.set_code(status.code())
        self.set_details(status.details())
        raise grpc.RpcError(status.details())

    def is_active(self):
        return True

    def time_remaining(self):
        return 1000

    def add_callback(self, callback):
        pass

    def invocation_metadata(self):
        return []

    def peer(self):
        return "peer"

    def send_initial_metadata(self, initial_metadata):
        pass

    def set_trailing_metadata(self, trailing_metadata):
        pass

    def auth_context(self):
        return {}

    def set_compression(self, compression):
        pass

    def disable_next_message_compression(self):
        pass

    def initial_metadata(self):
        return []

    def trailing_metadata(self):
        return []

    def code(self):
        return self._code

    def details(self):
        return self._details

    def peer_identities(self):
        return super().peer_identities()

    def peer_identity_key(self):
        return super().peer_identity_key()
