from hn_search.preprocessor import tokenize, clean_html


def test_keeps_python3_and_year():
    tokens = tokenize("Learning Python3 in 2024")
    assert "python3" in tokens
    assert "2024" in tokens
    assert "in" not in tokens


def test_hyphen_joined_tech_terms():
    tokens = tokenize("GPT-4 and LLaMA-3 compared")
    assert "gpt4" in tokens
    assert "llama3" in tokens


def test_protected_cpp_csharp():
    tokens = tokenize("Why C++ and C# still matter")
    assert "cpp" in tokens
    assert "csharp" in tokens


def test_dotjs_normalization():
    tokens = tokenize("Node.js vs Deno")
    assert "nodejs" in tokens
    assert "deno" in tokens


def test_stopwords_only_after_apostrophe_strip():
    # "don't" → "dont" (stopword), "it's" → "its" (stopword)
    tokens = tokenize("Don't use it's")
    assert "dont" not in tokens
    assert "its" not in tokens


def test_html_cleaning():
    html = '<p>Check out <a href="https://github.com/foo/bar">this repo</a></p>'
    cleaned = clean_html(html)
    assert "<p>" not in cleaned
    assert "&" not in cleaned
    tokens = tokenize(cleaned)
    assert "github" in tokens


def test_hn_prefix_stripped():
    tokens = tokenize("Ask HN: What are you working on?")
    assert "ask" not in tokens
    assert "hn" not in tokens


def test_empty_and_punctuation_only():
    assert tokenize("") == []
    assert tokenize("!!! ??? ---") == []
