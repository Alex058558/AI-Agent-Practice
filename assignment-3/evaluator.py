import sys
import os
import datetime
import warnings
import re
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_google_genai")
warnings.filterwarnings("ignore", message=".*Convert_system_message_to_human.*")
warnings.filterwarnings("ignore", message=".*API key must be provided when using hosted LangSmith API.*")
import time
from termcolor import colored
from langgraph_agent import run_graph_agent, run_legacy_agent
from config import get_llm
from langchain_core.prompts import ChatPromptTemplate

# CLI: python evaluator.py [GRAPH|LEGACY]
TEST_MODE = sys.argv[1].upper() if len(sys.argv) > 1 else "LEGACY"
TRACES_DIR = "traces"


class DualLogger:
    def __init__(self, filename="evaluation_log.txt"):
        self.terminal = sys.stdout
        self.log = open(filename, "w", encoding="utf-8")
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def write(self, message):
        self.terminal.write(message)
        clean_message = self.ansi_escape.sub('', message)
        self.log.write(clean_message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()


def grade_answer_with_llm(question, agent_answer, expected_facts, forbidden_facts):
    llm = get_llm(temperature=0)

    prompt = ChatPromptTemplate.from_template("""
    You are a strict grading assistant. Check if the AGENT_ANSWER meets the following criteria based on the QUESTION.

    QUESTION: {question}
    AGENT_ANSWER: {agent_answer}

    CRITERIA 1 (Must Include): The answer MUST semantically contain these facts: {expected_facts}.
    CRITERIA 2 (Forbidden): The answer MUST NOT contain information about: {forbidden_facts}.

    Logic:
    - If the agent says "391 billion" and expected is "391,000 million", that is PASS.
    - If the agent answers in a different language but the numbers/facts are correct, that is PASS.
    - If the agent hallucinates or mentions forbidden topics (e.g., mentioning Tesla when asked about Apple), that is FAIL.

    OUTPUT ONLY ONE WORD: "PASS" or "FAIL".
    """)

    chain = prompt | llm
    result = chain.invoke({
        "question": question,
        "agent_answer": agent_answer,
        "expected_facts": str(expected_facts),
        "forbidden_facts": str(forbidden_facts),
    })

    return result.content.strip().upper()


TEST_CASES = [
    {
        "name": "Test A: Apple Revenue",
        "question": "Apple 2024 \u5e74\u7684\u7e3d\u71df\u6536 (Total net sales) \u662f\u591a\u5c11\uff1f",
        "must_contain": ["391", "billion"],
        "forbidden": ["Tesla"],
    },
    {
        "name": "Test B: Tesla R&D",
        "question": "Tesla 2024 \u5e74\u7684\u7814\u767c\u8cbb\u7528 (R&D expenses) \u662f\u591a\u5c11\uff1f",
        "must_contain": ["4.77", "billion"],
        "forbidden": ["Apple"],
    },
    {
        "name": "Test D: Apple Services Cost",
        "question": "Apple 2024 \u5e74\u7684\u300c\u670d\u52d9\u6210\u672c (Cost of sales - Services)\u300d\u662f\u591a\u5c11\uff1f",
        "must_contain": ["25", "billion", "25,119"],
        "forbidden": [],
    },
    {
        "name": "Test E: Tesla Energy Revenue",
        "question": "Tesla 2024 \u5e74\u7684\u300c\u80fd\u6e90\u767c\u96fb\u8207\u5132\u5b58 (Energy generation and storage)\u300d\u71df\u6536\u662f\u591a\u5c11\uff1f",
        "must_contain": ["23.7", "billion", "23,767"],
        "forbidden": [],
    },
    {
        "name": "Test G: Unknown Info",
        "question": "Apple \u8a08\u756b\u5728 2025 \u5e74\u767c\u5e03\u7684 iPhone 17 \u9810\u8a08\u552e\u50f9\u662f\u591a\u5c11\uff1f",
        "must_contain": ["unknown", "provide", "mention", "does not", "\u7121\u6cd5", "\u672a\u63d0\u53ca"],
        "forbidden": ["1000", "999", "1200"],
    },
    {
        "name": "Test A1 [Eng]: Apple Revenue",
        "question": "What was Apple's Total Net Sales for the fiscal year 2024?",
        "must_contain": ["391", "billion", "391,035"],
        "forbidden": ["Tesla"],
    },
    {
        "name": "Test A2 [Eng]: Tesla Automotive Revenue",
        "question": "What is the specific revenue figure for 'Automotive sales' for Tesla in 2024?",
        "must_contain": ["78", "billion", "78,512"],
        "forbidden": ["Apple"],
    },
    {
        "name": "Test B1 [Mixed]: Apple R&D",
        "question": "Apple 2024 \u5e74\u7684\u7814\u767c\u8cbb\u7528 (Research and development expenses) \u662f\u591a\u5c11\uff1f",
        "must_contain": ["31", "billion", "31,370"],
        "forbidden": ["Tesla"],
    },
    {
        "name": "Test B2 [Mixed]: Tesla CapEx",
        "question": "Tesla \u5728 2024 \u5e74\u7684\u8cc7\u672c\u652f\u51fa (Capital Expenditures) \u662f\u591a\u5c11\uff1f",
        "must_contain": ["11", "billion", "11,153"],
        "forbidden": ["Apple"],
    },
    {
        "name": "Test C1 [Eng]: R&D Comparison",
        "question": "Compare the Research and Development (R&D) expenses of Apple and Tesla in 2024. Who spent more?",
        "must_contain": ["Apple", "Apple spent more"],
        "forbidden": [],
    },
    {
        "name": "Test C2 [Eng]: Gross Margin Analysis",
        "question": "Which company had a higher Total Gross Margin percentage in 2024, Apple or Tesla? Please provide the approximate percentages.",
        "must_contain": ["Apple", "Tesla", "46", "18", "Apple"],
        "forbidden": [],
    },
    {
        "name": "Test D1 [Eng]: Apple Services Cost",
        "question": "According to the Consolidated Statements of Operations, what was Apple's 'Cost of sales' specifically for 'Services' in 2024?",
        "must_contain": ["25", "billion", "25,119"],
        "forbidden": [],
    },
    {
        "name": "Test E1 [Mixed]: 2025 Projection (Trap)",
        "question": "\u8ca1\u5831\u4e2d\u6709\u63d0\u5230 Apple 2025 \u5e74\u9810\u8a08\u7684 iPhone \u92b7\u91cf\u76ee\u6a19\u55ce\uff1f",
        "must_contain": ["no", "not mentioned", "does not provide", "\u6c92\u6709\u63d0\u5230", "\u672a\u77e5"],
        "forbidden": ["100 million", "200 million", "increase"],
    },
    {
        "name": "Test F1 [Eng]: CEO Identity",
        "question": "Who signed the 10-K report as the Chief Executive Officer for Tesla?",
        "must_contain": ["Elon Musk"],
        "forbidden": ["Tim Cook"],
    },
]


def run_evaluation():
    score = 0
    total = len(TEST_CASES)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n==================================================")
    print(f"  ASSIGNMENT 3 EVALUATION REPORT")
    print(f"  Time: {timestamp}")
    print(f"  Agent Mode: {TEST_MODE}")
    print(f"==================================================\n")

    print(colored("STARTING EVALUATION...", "cyan", attrs=["bold"]))
    print(f"==================================================\n")

    for test in TEST_CASES:
        print(f"Running: {test['name']}...")
        start_time = time.time()

        try:
            if TEST_MODE == "GRAPH":
                answer = run_graph_agent(test["question"])
            else:
                answer = run_legacy_agent(test["question"])
            clean_answer = answer.split("Observation:")[0].strip()
            display_answer = clean_answer[:300] + "..." if len(clean_answer) > 300 else clean_answer
            result = grade_answer_with_llm(
                test["question"],
                clean_answer,
                test["must_contain"],
                test["forbidden"],
            )

            elapsed = time.time() - start_time
            print(f"A: {display_answer}")
            if "PASS" in result:
                score += 1
                print(colored(f"[PASS] ({elapsed:.2f}s)", "green"))
            else:
                print(colored(f"[FAIL] ({elapsed:.2f}s)", "red"))
                print(f"   Agent Answer: {display_answer}")
                print(f"   Judge Verdict: {result}")

        except Exception as e:
            print(colored(f"[CRASH] {e}", "red"))
        print("-" * 50)

    print(colored(f"\nFINAL SCORE: {score}/{total}", "magenta", attrs=["bold"]))


if __name__ == "__main__":
    os.makedirs(TRACES_DIR, exist_ok=True)
    model_name = os.getenv("OPENAI_MODEL", "unknown").replace("/", "_").replace(":", "_")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    log_filename = os.path.join(TRACES_DIR, f"{model_name}_{TEST_MODE}_{timestamp}.txt")
    sys.stdout = DualLogger(log_filename)
    run_evaluation()
    sys.stdout = sys.stdout.terminal
    print(f"\n[System] Log saved to {log_filename}")
