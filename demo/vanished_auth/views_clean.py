import auth
import flask


def login(request):
    auth.check_session(request)
    return flask.jsonify({"ok": True})
