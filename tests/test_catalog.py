from rrs_orcaslicer_mcp.catalog import extract, snapshot


def test_extractor_ignores_comments_preserves_strings():
    result = extract("""
    // def = this->add("old", coBool);
    /*def = this->add("removed", coInt); */
    def = this->add("live", coString);
    def->tooltip = L("https://example.test/*not-comment*/");
    def->enum_values.push_back("one");
    """)
    assert set(result) == {"live"}
    assert "https://example.test" in result["live"]["tooltip"]


def test_source_snapshot_has_real_options():
    result = snapshot()
    assert len(result["options"]) > 800
    assert "layer_height" in result["options"]
    assert "slice" in result["options"]
    assert "export_gcode" not in result["options"]  # commented out upstream
