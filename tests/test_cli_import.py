from accessible_surfaceome.cli import main


def test_cli_entrypoint_importable() -> None:
    assert callable(main)
