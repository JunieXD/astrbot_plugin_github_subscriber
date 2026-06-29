from github_subscriber.templates import render_template, truncate_text


def test_render_template_replaces_known_variables_and_blanks_unknown():
    text = render_template(
        "{repo} #{number}: {title} {unknown}",
        {"repo": "Owner/Repo", "number": 1, "title": "Hello"},
    )

    assert text == "Owner/Repo #1: Hello "


def test_truncate_text_adds_ellipsis_when_needed():
    assert truncate_text("abcdef", 3) == "abc..."
    assert truncate_text("abc", 3) == "abc"
    assert truncate_text("", 3) == ""
