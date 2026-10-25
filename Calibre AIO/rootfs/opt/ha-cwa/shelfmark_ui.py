"""Keep the administrator setup wizard out of ordinary reader sessions."""
from flask import request, session


def install_reader_ui(app):
    @app.after_request
    def hide_admin_onboarding(response):
        if (request.path == '/api/config' and response.status_code == 200
                and response.is_json and not session.get('is_admin', False)):
            config = response.get_json()
            config['onboarding_complete'] = True
            response.set_data(app.json.dumps(config))
        return response
