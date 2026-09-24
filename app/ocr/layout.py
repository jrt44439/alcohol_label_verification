"""Groups OCR word boxes into lines and clusters nearby, similarly-sized
lines together -- "words close together with similar fonts belong to the
same group." Reusable by any field extractor that needs to gather text
spanning more than one physically close printed line (a stacked brand name,
a multi-line address, ...), rather than each reimplementing its own
proximity/font-size heuristics.
"""
from app.ocr.engine import WordBox

LineKey = tuple[int, int, int]


def group_words_by_line(words: list[WordBox]) -> dict[LineKey, dict]:
    """Group words into printed lines, keyed by (block_num, par_num,
    line_num). par_num matters: Tesseract's line_num is 1-indexed *within a
    paragraph* and resets for each new paragraph, so two different
    paragraphs in the same block can otherwise collide on the same
    (block_num, line_num).

    Returns ``{key: {"words", "text", "height", "top", "left"}}``, where
    "height" is the line's average word height (a font-size proxy) and
    "top"/"left" are the line's bounding position.
    """
    lines: dict[LineKey, list[WordBox]] = {}
    for word in words:
        key = (word.block_num, word.par_num, word.line_num)
        lines.setdefault(key, []).append(word)

    line_info: dict[LineKey, dict] = {}
    for key, line_words in lines.items():
        line_words.sort(key=lambda w: w.left)
        text = " ".join(w.text for w in line_words).strip()
        if not text:
            continue
        line_info[key] = {
            "words": line_words,
            "text": text,
            "height": sum(w.height for w in line_words) / len(line_words),
            "top": min(w.top for w in line_words),
            "left": min(w.left for w in line_words),
        }
    return line_info


def cluster_lines(
    line_info: dict[LineKey, dict],
    start_key: LineKey,
    max_lines: int = 6,
    height_ratio: float = 0.6,
    max_gap_ratio: float = 1.8,
) -> list[LineKey]:
    """Starting at ``start_key``, walk forward through the page's lines in
    top-to-bottom (then left-to-right) order, including a line only while
    it's "close together with a similar font" to what's been gathered so
    far:

    - its average word height is within ``height_ratio`` of the start
      line's height (similar font size -- not a smaller/larger unrelated
      block of text), and
    - the vertical gap between it and the previous included line's bottom
      edge is small relative to text height (physically close together --
      not separated by a large blank gap that suggests unrelated content).

    The walk isn't restricted to the start line's Tesseract block/paragraph
    -- a stylized brand name or heading can get split across separate
    blocks (e.g. a logo graphic interrupting the text region), so scanning
    the whole page's line order rather than just one block lets those still
    get grouped together as long as they're visually close and similarly
    sized.

    Stops at the first line that fails either check, or after ``max_lines``.
    Returns the ordered list of included keys (always includes
    ``start_key`` itself).
    """
    if start_key not in line_info:
        return []

    ordered_keys = sorted(line_info, key=lambda k: (line_info[k]["top"], line_info[k]["left"]))
    start_idx = ordered_keys.index(start_key)

    base = line_info[start_key]
    included = [start_key]
    prev_bottom = base["top"] + base["height"]

    for key in ordered_keys[start_idx + 1 :]:
        if len(included) >= max_lines:
            break
        candidate = line_info[key]
        if not (base["height"] * height_ratio <= candidate["height"] <= base["height"] / height_ratio):
            break
        gap = candidate["top"] - prev_bottom
        if gap > base["height"] * max_gap_ratio:
            break
        included.append(key)
        prev_bottom = candidate["top"] + candidate["height"]

    return included
