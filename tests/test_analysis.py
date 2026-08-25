import pytest

from tules.analysis import CodeAnalyzer, Reviewer
from tules.matching import common_indent, describe_closest, locate_block, normalize, reindent


@pytest.fixture
def reviewer(workspace) -> Reviewer:
	return Reviewer(workspace)


def test_normalize_folds_quotes_tabs_and_invisibles():
	raw = "\ufeff\u201ca\u201d\t\u00a0b  \r\n"
	assert normalize(raw) == '"a"     b\n'


def test_common_indent_ignores_blank_lines():
	assert common_indent(["\t\tone", "", "\t\t\ttwo"]) == "\t\t"


def test_reindent_keeps_relative_depth():
	assert reindent(["\tif x:", "\t\ty()"], "\t", "\t\t") == ["\t\tif x:", "\t\t\ty()"]


def test_locate_block_finds_an_exact_region():
	lines = ["a = 1", "b = 2", "c = 3"]
	assert locate_block(lines, ["b = 2"]) == (1, 2, 1.0)


def test_locate_block_ignores_blank_line_differences():
	first, last, confidence = locate_block(["a = 1", "", "b = 2"], ["a = 1", "b = 2"])
	assert (first, last, confidence) == (0, 3, 1.0)


def test_locate_block_uses_context_to_disambiguate():
	lines = ["x = 1", "flag = True", "y = 2", "flag = True", "z = 3"]
	first, _, confidence = locate_block(lines, ["flag = Tru"], context_before=["y = 2"])
	assert first == 3
	assert confidence < 1.0


def test_locate_block_reports_no_match_for_an_empty_search():
	assert locate_block(["a = 1"], ["", "  "]) == (-1, -1, 0.0)


def test_describe_closest_marks_the_region():
	rendered = describe_closest("a = 1\nb = 2\n", "b = 3")
	assert ">>>" in rendered
	assert "b = 2" in rendered


def test_summarize_counts_lines_and_symbols(workspace):
	summary = CodeAnalyzer().summarize(workspace.load("sample.py"))
	assert summary["total_lines"] == 11
	assert {item["name"] for item in summary["symbols"] if item["kind"] != "import"} == {
		"greet", "Widget", "build"}


def test_extract_symbols_handles_javascript(workspace):
	(workspace.root / "app.js").write_text("function run() {}\nconst x = 1;\n", encoding="utf-8")
	symbols = CodeAnalyzer().extract_symbols(workspace.load("app.js"))
	assert [item["name"] for item in symbols] == ["run", "x"]


def test_review_flags_an_unused_import(reviewer, workspace):
	(workspace.root / "unused.py").write_text("import json\nx = 1\n", encoding="utf-8")
	messages = [issue["message"] for issue in reviewer.review("unused.py")]
	assert "Possibly unused import: json" in messages


def test_review_keeps_an_import_that_is_used(reviewer, workspace):
	(workspace.root / "used.py").write_text(
		"import json\n\n\ndef dump(x):\n\treturn json.dumps(x)\n", encoding="utf-8")
	assert reviewer.review("used.py") == []


def test_review_reports_a_syntax_error(reviewer, workspace):
	(workspace.root / "broken.py").write_text("def f(\n", encoding="utf-8")
	issues = reviewer.review("broken.py")
	assert issues[0]["severity"] == "error"


def test_review_flags_a_redefinition(reviewer, workspace):
	(workspace.root / "twice.py").write_text(
		"def f():\n\tpass\n\n\ndef f():\n\tpass\n", encoding="utf-8")
	assert "Redefinition of f" in reviewer.review("twice.py")[0]["message"]


def test_review_allows_the_same_method_name_in_two_classes(reviewer, workspace):
	(workspace.root / "pair.py").write_text(
		"class A:\n\tdef run(self):\n\t\tpass\n\n\nclass B:\n\tdef run(self):\n\t\tpass\n",
		encoding="utf-8")
	assert reviewer.review("pair.py") == []


def test_find_duplicates_across_files(reviewer, workspace):
	(workspace.root / "other.py").write_text("def greet(name):\n\tpass\n", encoding="utf-8")
	duplicates = reviewer.find_duplicates()
	assert [item["name"] for item in duplicates] == ["greet"]


def test_find_dependents_detects_an_import(reviewer, workspace):
	(workspace.root / "main.py").write_text(
		"import sample\n\nsample.greet('x')\n", encoding="utf-8")
	dependents = reviewer.find_dependents("sample.py")
	assert dependents[0]["file"] == "main.py"


def test_survey_counts_the_project(reviewer):
	survey = reviewer.survey()
	assert survey["total_files"] == 2
	assert survey["files_by_type"] == {".py": 1, ".md": 1}
