import click


def get_banner_width() -> int:
    width, _ = click.get_terminal_size()
    return max(width, 40)


def format_banner(title: str) -> str:
    width = get_banner_width()
    separator = "=" * width
    centered_title = title.center(width)
    return f"{separator}\n{centered_title}\n{separator}"
