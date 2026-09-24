from app.ocr.engine import WordBox
from app.ocr.layout import cluster_lines, group_words_by_line


def _word(text, height, top, left=0, block_num=1, par_num=1, line_num=1):
    return WordBox(
        text=text, conf=90, left=left, top=top, width=50, height=height,
        block_num=block_num, par_num=par_num, line_num=line_num,
    )


def test_group_words_by_line_disambiguates_paragraphs_sharing_line_num():
    # Two different paragraphs in the same block, each with their own
    # line_num starting at 1 -- must not be merged just because the
    # (block_num, line_num) pair collides.
    words = [
        _word("First", height=20, top=10, par_num=1, line_num=1),
        _word("Second", height=20, top=100, par_num=2, line_num=1),
    ]
    line_info = group_words_by_line(words)
    assert len(line_info) == 2
    assert line_info[(1, 1, 1)]["text"] == "First"
    assert line_info[(1, 2, 1)]["text"] == "Second"


def test_group_words_by_line_sorts_words_left_to_right():
    words = [
        _word("World", height=20, top=10, left=60),
        _word("Hello", height=20, top=10, left=0),
    ]
    line_info = group_words_by_line(words)
    assert line_info[(1, 1, 1)]["text"] == "Hello World"


def test_cluster_lines_merges_close_similar_height_lines():
    line_info = {
        (1, 1, 1): {"text": "Line One", "height": 20, "top": 0, "left": 0},
        (1, 1, 2): {"text": "Line Two", "height": 20, "top": 24, "left": 0},
        (1, 1, 3): {"text": "Line Three", "height": 20, "top": 48, "left": 0},
    }
    keys = cluster_lines(line_info, (1, 1, 1), max_lines=3)
    assert keys == [(1, 1, 1), (1, 1, 2), (1, 1, 3)]


def test_cluster_lines_stops_at_font_size_change():
    line_info = {
        (1, 1, 1): {"text": "Big Text", "height": 40, "top": 0, "left": 0},
        (1, 1, 2): {"text": "small print", "height": 12, "top": 44, "left": 0},
    }
    keys = cluster_lines(line_info, (1, 1, 1), max_lines=5)
    assert keys == [(1, 1, 1)]


def test_cluster_lines_stops_at_large_vertical_gap():
    line_info = {
        (1, 1, 1): {"text": "Address Line", "height": 20, "top": 0, "left": 0},
        # Same height, but far below -- a visually unrelated block.
        (1, 1, 2): {"text": "Unrelated Line", "height": 20, "top": 200, "left": 0},
    }
    keys = cluster_lines(line_info, (1, 1, 1), max_lines=5)
    assert keys == [(1, 1, 1)]


def test_cluster_lines_respects_max_lines():
    line_info = {
        (1, 1, i): {"text": f"Line {i}", "height": 20, "top": (i - 1) * 24, "left": 0}
        for i in range(1, 6)
    }
    keys = cluster_lines(line_info, (1, 1, 1), max_lines=2)
    assert keys == [(1, 1, 1), (1, 1, 2)]


def test_cluster_lines_missing_start_key_returns_empty():
    assert cluster_lines({}, (1, 1, 1)) == []


def test_cluster_lines_merges_across_different_blocks_and_paragraphs():
    # A stylized brand name split into separate Tesseract blocks (e.g. a
    # logo graphic interrupting the text region) should still merge, since
    # the two lines are visually close and the same font size -- the walk
    # isn't restricted to a single (block_num, par_num).
    line_info = {
        (1, 1, 1): {"text": "OLD RIDGE", "height": 30, "top": 0, "left": 0},
        (2, 1, 1): {"text": "DISTILLERY", "height": 30, "top": 34, "left": 0},
    }
    keys = cluster_lines(line_info, (1, 1, 1), max_lines=3)
    assert keys == [(1, 1, 1), (2, 1, 1)]
