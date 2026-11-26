from barons_journal.ui import prefer_xwayland


def test_wayland_linux_gets_xcb():
    env = {"WAYLAND_DISPLAY": "wayland-1"}
    prefer_xwayland(env, "linux")
    assert env["QT_QPA_PLATFORM"] == "xcb"


def test_explicit_platform_kept():
    env = {"WAYLAND_DISPLAY": "wayland-1", "QT_QPA_PLATFORM": "offscreen"}
    prefer_xwayland(env, "linux")
    assert env["QT_QPA_PLATFORM"] == "offscreen"


def test_x11_session_untouched():
    env = {"DISPLAY": ":0"}
    prefer_xwayland(env, "linux")
    assert "QT_QPA_PLATFORM" not in env


def test_other_os_untouched():
    env = {"WAYLAND_DISPLAY": "wayland-1"}
    prefer_xwayland(env, "win32")
    assert "QT_QPA_PLATFORM" not in env
