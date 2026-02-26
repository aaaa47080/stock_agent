
QUESTION_STARTERS = (
    "你覺得", "你認為", "你建議", "哪個", "哪則", "哪一", "哪些",
    "為什麼", "什麼", "怎麼", "如何", "多少", "幾個", "是否",
    "What", "Which", "How", "Why", "Who", "When", "Where", 
    "Is", "Are", "Do", "Does", "Can", "Could", "Would", "Should"
)

def check(resp):
    resp_stripped = resp.strip()
    is_question = (
        resp_stripped.endswith("?") or resp_stripped.endswith("？") or
        any(resp_stripped.lower().startswith(w.lower()) for w in QUESTION_STARTERS)
    )
    print(f"Input: '{resp}'")
    print(f"Stripped: '{resp_stripped}'")
    print(f"Ends with ?: {resp_stripped.endswith('?')}")
    # Show matching word
    match = next((w for w in QUESTION_STARTERS if resp_stripped.lower().startswith(w.lower())), None)
    print(f"Starts with starter: {match}")
    print(f"Is Question: {is_question}")

check("Which news is important?")
check("Which news is important")
check("analyze this")
