from surface_proteome.cli import main


def test_cli_entrypoint_importable() -> None:
    assert callable(main)
