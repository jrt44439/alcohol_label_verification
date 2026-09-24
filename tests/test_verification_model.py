from app.models import verification as verification_model

SAMPLE_FIELD_SUMMARY_PASS = {
    "brand_name": {"status": "match", "value": "Old Ridge", "source_index": 0, "expected": "Old Ridge"},
    "class_type": {"status": "match", "value": "Bourbon", "source_index": 0, "expected": "Bourbon"},
}

SAMPLE_FIELD_SUMMARY_NEEDS_REVIEW = {
    "brand_name": {"status": "match", "value": "Old Ridge", "source_index": 0, "expected": "Old Ridge"},
    "class_type": {"status": "not_found", "expected": "Bourbon"},
}


def test_create_and_get_by_id_round_trips_field_summary(app):
    with app.app_context():
        vid = verification_model.create(
            "test.docx", SAMPLE_FIELD_SUMMARY_PASS, True, False, [{"index": 0, "raw_text": "hi"}]
        )
        saved = verification_model.get_by_id(vid)

    assert saved.source_filename == "test.docx"
    assert saved.field_summary == SAMPLE_FIELD_SUMMARY_PASS
    assert saved.warning_caps_ok is True
    assert saved.warning_bold_ok is False
    assert saved.photos == [{"index": 0, "raw_text": "hi"}]


def test_overall_status_pass_when_all_match(app):
    with app.app_context():
        vid = verification_model.create("test.docx", SAMPLE_FIELD_SUMMARY_PASS, None, None, [])
        saved = verification_model.get_by_id(vid)
    assert saved.overall_status == "pass"


def test_overall_status_needs_review_when_any_field_not_match(app):
    with app.app_context():
        vid = verification_model.create("test.docx", SAMPLE_FIELD_SUMMARY_NEEDS_REVIEW, None, None, [])
        saved = verification_model.get_by_id(vid)
    assert saved.overall_status == "needs_review"


def test_get_all_lists_without_full_payload(app):
    with app.app_context():
        verification_model.create("a.docx", SAMPLE_FIELD_SUMMARY_PASS, None, None, [])
        verification_model.create("b.docx", SAMPLE_FIELD_SUMMARY_NEEDS_REVIEW, None, None, [])
        summaries = verification_model.get_all()
    assert len(summaries) == 2
    assert {s.source_filename for s in summaries} == {"a.docx", "b.docx"}


def test_update_persists_correction_and_recomputes_status(app):
    with app.app_context():
        vid = verification_model.create("test.docx", SAMPLE_FIELD_SUMMARY_NEEDS_REVIEW, None, None, [])
        corrected = dict(SAMPLE_FIELD_SUMMARY_NEEDS_REVIEW)
        corrected["class_type"] = {"status": "match", "value": "Bourbon", "source_index": 0, "expected": "Bourbon"}
        verification_model.update(vid, corrected, None, None, [])
        saved = verification_model.get_by_id(vid)
    assert saved.overall_status == "pass"
    assert saved.field_summary["class_type"]["status"] == "match"


def test_delete_removes_record(app):
    with app.app_context():
        vid = verification_model.create("test.docx", SAMPLE_FIELD_SUMMARY_PASS, None, None, [])
        verification_model.delete(vid)
        assert verification_model.get_by_id(vid) is None


def test_get_by_id_missing_returns_none(app):
    with app.app_context():
        assert verification_model.get_by_id(999) is None


def test_brand_name_exists_true_after_save(app):
    with app.app_context():
        verification_model.create("test.docx", SAMPLE_FIELD_SUMMARY_PASS, None, None, [])
        assert verification_model.brand_name_exists("Old Ridge") is True


def test_brand_name_exists_is_case_and_whitespace_insensitive(app):
    with app.app_context():
        verification_model.create("test.docx", SAMPLE_FIELD_SUMMARY_PASS, None, None, [])
        assert verification_model.brand_name_exists("  old ridge  ") is True


def test_brand_name_exists_false_for_different_name(app):
    with app.app_context():
        verification_model.create("test.docx", SAMPLE_FIELD_SUMMARY_PASS, None, None, [])
        assert verification_model.brand_name_exists("New Summit") is False


def test_brand_name_exists_false_for_blank_name(app):
    with app.app_context():
        verification_model.create("test.docx", SAMPLE_FIELD_SUMMARY_PASS, None, None, [])
        assert verification_model.brand_name_exists(None) is False
        assert verification_model.brand_name_exists("   ") is False
