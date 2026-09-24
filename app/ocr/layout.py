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
    direction: int = 1,
) -> list[LineKey]:
    """Starting at ``start_key``, walk through the page's lines in
    top-to-bottom (then left-to-right) order -- forward (``direction=1``,
    the default) or backward (``direction=-1``) -- including a line only
    while it's "close together with a similar font" to the line most
    recently added to the cluster:

    - its average word height is within ``height_ratio`` of that line's
      height (similar font size -- not a smaller/larger unrelated block of
      text). Comparing to the most recently added line, not always the
      original start line, lets a gradual, multi-line size progression
      (e.g. three lines that shrink slightly each step) chain together even
      if the first and last of them individually fall outside each other's
      ratio.
    - the vertical gap between it and the previously included line's near
      edge is small relative to that line's height (physically close
      together -- not separated by a large blank gap that suggests
      unrelated content).

    The walk isn't restricted to the start line's Tesseract block/paragraph
    -- a stylized brand name or heading can get split across separate
    blocks (e.g. a logo graphic interrupting the text region), so scanning
    the whole page's line order rather than just one block lets those still
    get grouped together as long as they're visually close and similarly
    sized.

    Stops at the first line that fails either check, or after ``max_lines``.
    Returns the ordered list of included keys, top-to-bottom, always
    including ``start_key`` itself.
    """
    if start_key not in line_info:
        return []

    ordered_keys = sorted(line_info, key=lambda k: (line_info[k]["top"], line_info[k]["left"]))
    start_idx = ordered_keys.index(start_key)
    candidates = ordered_keys[start_idx + 1 :] if direction >= 0 else reversed(ordered_keys[:start_idx])

    base = line_info[start_key]
    included = [start_key]
    prev_height = base["height"]
    prev_edge = base["top"] + base["height"] if direction >= 0 else base["top"]

    for key in candidates:
        if len(included) >= max_lines:
            break
        candidate = line_info[key]
        if not (prev_height * height_ratio <= candidate["height"] <= prev_height / height_ratio):
            break
        gap = (candidate["top"] - prev_edge) if direction >= 0 else (prev_edge - (candidate["top"] + candidate["height"]))
        if gap > prev_height * max_gap_ratio:
            break
        included.append(key)
        prev_height = candidate["height"]
        prev_edge = candidate["top"] + candidate["height"] if direction >= 0 else candidate["top"]

    if direction < 0:
        included.reverse()
    return included
