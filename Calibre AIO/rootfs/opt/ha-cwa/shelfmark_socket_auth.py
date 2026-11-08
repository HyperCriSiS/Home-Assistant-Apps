"""Apply upstream proxy authentication to Socket.IO's separate request path."""
from functools import wraps


def install_socket_auth(upstream):
    # Flask before_request hooks do not run for Socket.IO event handlers.
    # Refresh the session from the gateway's trusted headers before joining
    # status rooms, including when an old cookie belongs to another HA user.
    # Shelfmark registers both the hook and the handlers as closures, so they
    # are taken from Flask's and Flask-SocketIO's registries.
    hooks = {hook.__name__: hook for hook in upstream.app.before_request_funcs[None]}
    authenticate = hooks['proxy_auth_middleware']
    registered = upstream.socketio.server.handlers['/']
    for event in ('connect', 'request_status'):
        def secure(handler):
            @wraps(handler)
            def authenticated(*args, **kwargs):
                if authenticate() is not None:
                    return False
                return handler(*args, **kwargs)
            return authenticated

        upstream.socketio.on_event(event, secure(registered[event].__wrapped__))
