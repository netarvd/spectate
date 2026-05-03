import flask


def login(request):
    return flask.jsonify({"ok": True})
