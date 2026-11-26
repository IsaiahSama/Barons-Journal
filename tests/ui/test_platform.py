from barons_journal.ui import prefer_xwayland


def test_wayland_linux_prefers_xcb_with_wayland_fallback():
    env = {"WAYLAND_DISPLAY": "wayland-1"}
    prefer_xwayland(env, "linux")
    # Qt tries each in order: without a working xcb plugin the app still starts on Wayland.
    assert env["QT_QPA_PLATFORM"] == "xcb;wayland"


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


def test_session_wide_wayland_preference_overridden():
    # COSMIC and others export QT_QPA_PLATFORM=wayland;xcb for every app; that's not a choice for this app.
    for session in ("wayland;xcb", "wayland", "xcb"):
        env = {"WAYLAND_DISPLAY": "wayland-1", "QT_QPA_PLATFORM": session}
        prefer_xwayland(env, "linux")
        assert env["QT_QPA_PLATFORM"] == "xcb;wayland", session
