import os
import json
from typing import List, TypedDict
from langgraph.graph import END, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_chroma import Chroma
from termcolor import colored
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import get_embeddings, get_llm, DB_FOLDER, FILES


retry_logic = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception)
)


def initialize_vector_dbs():
    embeddings = get_embeddings()
    retrievers = {}

    for key in FILES.keys():
        persist_dir = os.path.join(DB_FOLDER, key)

        if os.path.exists(persist_dir):
            vectorstore = Chroma(persist_directory=persist_dir, embedding_function=embeddings)
            retrievers[key] = vectorstore.as_retriever(search_kwargs={"k": 3})
        else:
            print(colored(f"[ERROR] Database for '{key}' not found!", "red"))
            print(colored(f"[WARN] Please run 'python build_rag.py' first.", "yellow"))
            continue

    return retrievers

RETRIEVERS = initialize_vector_dbs()


class AgentState(TypedDict):
    question: str
    documents: str
    generation: str
    search_count: int
    needs_rewrite: str


# ---------------------------------------------------------------------------
# Task B: Intelligent Router + Retrieve
# ---------------------------------------------------------------------------
@retry_logic
def retrieve_node(state: AgentState):
    print(colored("--- RETRIEVING ---", "blue"))
    question = state["question"]
    llm = get_llm()

    options = list(FILES.keys()) + ["both", "none"]
    router_prompt = f"""You are a financial document router.
Classify the user's question into exactly ONE of these categories: {json.dumps(options)}.

Rules:
- If the question mentions only Apple (or iPhone, Mac, iPad, App Store, Services), choose "apple".
- If the question mentions only Tesla (or EV, Elon Musk, Cybertruck, energy storage), choose "tesla".
- If the question compares Apple and Tesla, or asks about both, choose "both".
- If the question is unrelated to either company, choose "none".

Output ONLY valid JSON: {{"datasource": "<category>"}}

User Question: {question}"""

    try:
        response = llm.invoke(router_prompt)
        content = response.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        res_json = json.loads(content)
        target = res_json.get("datasource", "both")
    except Exception as e:
        print(colored(f"[WARN] Router parse error: {e}. Defaulting to 'both'.", "yellow"))
        target = "both"

    print(colored(f"  -> Routing to: {target}", "cyan"))

    docs_content = ""
    targets_to_search = []
    if target == "both":
        targets_to_search = list(FILES.keys())
    elif target in FILES:
        targets_to_search = [target]

    for t in targets_to_search:
        if t in RETRIEVERS:
            docs = RETRIEVERS[t].invoke(question)
            source_name = t.capitalize()
            docs_content += f"\n\n[Source: {source_name}]\n" + "\n".join(
                [d.page_content for d in docs]
            )

    return {"documents": docs_content, "search_count": state["search_count"] + 1}


# ---------------------------------------------------------------------------
# Task C: Relevance Grader
# ---------------------------------------------------------------------------
@retry_logic
def grade_documents_node(state: AgentState):
    print(colored("--- GRADING ---", "yellow"))
    question = state["question"]
    documents = state["documents"]
    llm = get_llm()

    system_prompt = """You are a relevance grader for a financial RAG system.
Given a user question and retrieved document context, determine whether the documents
contain information that can help answer the question.

IMPORTANT:
- Look for specific financial figures, terms, or facts that relate to the question.
- If the documents contain relevant data (even partially), answer 'yes'.
- If the documents are completely unrelated or contain no useful information, answer 'no'.

You MUST answer with ONLY one word: 'yes' or 'no'. No explanation."""

    msg = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Retrieved document context:\n\n{documents}\n\nUser question: {question}"
        ),
    ]

    response = llm.invoke(msg)
    content = response.content.strip().lower()

    grade = "yes" if "yes" in content else "no"
    print(f"  Relevance Grade: {grade}")
    return {"needs_rewrite": grade}


# ---------------------------------------------------------------------------
# Task E: Final Generator
# ---------------------------------------------------------------------------
@retry_logic
def generate_node(state: AgentState):
    print(colored("--- GENERATING ---", "green"))
    question = state["question"]
    documents = state["documents"]
    llm = get_llm()

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a financial analyst assistant. Answer the question based ONLY on the "
         "provided context.\n\n"
         "Rules:\n"
         "1. Answer in English, even if the question is in another language.\n"
         "2. Pay close attention to fiscal years. Distinguish between 2024, 2023, and 2022 "
         "columns carefully. Do NOT mix up figures from different years.\n"
         "3. ALWAYS cite the source in brackets, e.g. [Source: Apple 10-K] or [Source: Tesla 10-K].\n"
         "4. If the context does not contain the exact information needed, honestly state "
         "\"I don't know\" or \"The information is not available in the provided documents.\" "
         "Do NOT guess or hallucinate.\n"
         "5. When providing financial figures, include the exact numbers from the document.\n\n"
         "Context:\n{context}"),
        ("human", "{question}"),
    ])

    chain = prompt | llm
    response = chain.invoke({"context": documents, "question": question})
    return {"generation": response.content}


# ---------------------------------------------------------------------------
# Task D: Query Rewriter
# ---------------------------------------------------------------------------
@retry_logic
def rewrite_node(state: AgentState):
    print(colored("--- REWRITING QUERY ---", "red"))
    question = state["question"]
    llm = get_llm()

    msg = [
        SystemMessage(
            content="You are a financial query optimizer. Your job is to rewrite vague or "
                    "informal questions into precise financial terminology that will perform "
                    "better in a vector search against SEC 10-K filings and earnings reports."
        ),
        HumanMessage(
            content=f"The following query failed to retrieve relevant financial documents:\n"
                    f"'{question}'\n\n"
                    f"Rewrite it using precise financial terms. Examples:\n"
                    f"- 'how much did they spend on new tech' -> 'Research and Development (R&D) expenses'\n"
                    f"- 'how much money did they make' -> 'Total net sales / Total revenue'\n"
                    f"- 'what they spent on buildings' -> 'Capital Expenditures (CapEx) / Purchases of property and equipment'\n\n"
                    f"Output ONLY the rewritten question, nothing else."
        ),
    ]
    response = llm.invoke(msg)
    new_query = response.content.strip()
    print(f"  Rewritten: {new_query}")
    return {"question": new_query}


# ---------------------------------------------------------------------------
# LangGraph: build state graph
# ---------------------------------------------------------------------------
def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade_documents", grade_documents_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("rewrite", rewrite_node)

    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "grade_documents")

    def decide_to_generate(state):
        if state["needs_rewrite"] == "yes":
            return "generate"
        if state["search_count"] > 2:
            print("  (Max retries reached, generating with available context)")
            return "generate"
        return "rewrite"

    workflow.add_conditional_edges(
        "grade_documents",
        decide_to_generate,
        {"generate": "generate", "rewrite": "rewrite"},
    )

    workflow.add_edge("rewrite", "retrieve")
    workflow.add_edge("generate", END)

    return workflow.compile()


def run_graph_agent(question: str):
    app = build_graph()
    inputs = {
        "question": question,
        "search_count": 0,
        "needs_rewrite": "no",
        "documents": "",
        "generation": "",
    }
    result = app.invoke(inputs)
    return result["generation"]


# ---------------------------------------------------------------------------
# Task A: Legacy ReAct Agent (LangChain baseline)
# ---------------------------------------------------------------------------
def run_legacy_agent(question: str):
    print(colored("--- RUNNING LEGACY AGENT (ReAct) ---", "magenta"))
    from langchain.agents import AgentExecutor, create_react_agent
    from langchain.tools.retriever import create_retriever_tool
    from langchain.tools.render import render_text_description

    tools = []
    for key, retriever in RETRIEVERS.items():
        tools.append(
            create_retriever_tool(
                retriever,
                f"search_{key}_financials",
                f"Searches {key.capitalize()}'s 10-K financial filing data including "
                f"income statements, balance sheets, and cash flow statements.",
            )
        )

    if not tools:
        return "System Error: No tools available."

    llm = get_llm()

    # Task A prompt: ReAct loop with behavioral constraints
    template = """You are a senior financial analyst with access to SEC 10-K filings.
Answer the following questions as best you can using the available tools.

You have access to the following tools:

{tools}

IMPORTANT RULES:
1. Your Final Answer MUST be in English, even if the question is in Chinese or another language.
2. Pay careful attention to fiscal years. Financial tables may have columns for 2024, 2023, and 2022. Make sure you read the correct year's column.
3. If the exact figure for the requested year is NOT found in the tool results, say "I don't know" rather than guessing.
4. When comparing two companies, you MUST search BOTH companies' data before giving a Final Answer.
5. Always include specific numbers from the documents in your Final Answer.

Use the following format:

Question: the input question you must answer
Thought: I should reason about what information I need and which tool to use.
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question (MUST be in English)

Begin!

Question: {input}
Thought: {agent_scratchpad}"""

    prompt = PromptTemplate.from_template(template)
    prompt = prompt.partial(
        tools=render_text_description(tools),
        tool_names=", ".join([t.name for t in tools]),
    )

    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5,
    )

    try:
        result = agent_executor.invoke({"input": question})
        return result["output"]
    except Exception as e:
        return f"Legacy Agent Error: {e}"
