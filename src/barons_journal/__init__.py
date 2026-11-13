def main() -> None:
    from . import ui  # lazy: keeps Qt out of the non-UI packages' import path

    raise SystemExit(ui.run())
