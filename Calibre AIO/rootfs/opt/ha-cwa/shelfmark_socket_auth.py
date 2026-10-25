"""Apply upstream proxy authentication to Socket.IO's separate request path."""
from functools import wraps


def install_socket_auth(upstream):
    # Flask before_request hooks do not run for Socket.IO event handlers.
    # Refresh the session from the gateway's trusted headers before joining
    # status rooms, including when an old cookie belongs to another HA user.
    for event, original in (
        ('connect', upstream.handle_connect),
        ('request_status', upstream.handle_status_request),
    ):
        def secure(handler):
            @wraps(handler)
            def authenticated(*args, **kwargs):
                if upstream.proxy_auth_middleware() is not None:
                    return False
                return handler(*args, **kwargs)
            return authenticated

        upstream.socketio.on_event(event, secure(original))
