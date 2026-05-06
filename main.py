# Copyright (c) Microsoft. All rights reserved.
import asyncio
import os
from typing import Annotated, TypedDict

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage

from azure.ai.agentserver.responses import (
    CreateResponse,
    ResponseContext,
    ResponsesAgentServerHost,
    ResponsesServerOptions,
    TextResponse,
)

from dotenv import load_dotenv
load_dotenv(override=False)

AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_AI_MODEL_DEPLOYMENT_NAME = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "")
MAX_ITERATIONS = 3

_token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default",
)

llm = ChatOpenAI(
    model=AZURE_AI_MODEL_DEPLOYMENT_NAME,
    base_url=f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}/openai/v1",
    api_key=_token_provider,
    use_responses_api=True,
)

class CopyState(TypedDict):
    messages: Annotated[list, add_messages]  # full conversation history
    product: str                             # product name from user
    haiku: str                               # current haiku draft
    suggestions: str                         # Brand Guardian feedback
    iteration: int                           # loop counter
    approved: bool                           # approval flag

def extract_text(response) -> str:
    """Extract plain text from LLM response regardless of content type.
    use_responses_api=True returns content as a list of content blocks."""
    if isinstance(response.content, str):
        return response.content.strip()
    elif isinstance(response.content, list):
        return " ".join(
            block.get("text", "") if isinstance(block, dict) else getattr(block, "text", "")
            for block in response.content
        ).strip()
    return str(response.content).strip()

BRAND_RULES = """
MUST HAVE:
- Warm and human — feels like written by a person, not a corporation
- Conversational tone — reads naturally when spoken aloud
- Positive emotion — evokes joy, curiosity, or comfort
- Accessible language — no jargon, no technical terms

MUST AVOID:
- Superlatives: no "best", "greatest", "unrivalled", "ultimate"
- Corporate speak: no "leverage", "synergy", "solutions", "cutting-edge"
- Hard sell language: no "buy now", "limited offer", "don't miss out"
- Vague filler words: no "innovative", "revolutionary", "game-changing"

HAIKU RULES:
- Must follow strict 5-7-5 syllable structure
- Each line must carry its own meaning — no line wasted
- The product must be recognisable from the haiku alone
"""

def copywriter(state: CopyState) -> CopyState:
    print(f"\n--- Copywriter (Iteration {state['iteration'] + 1}) ---")

    if state["iteration"] == 0:
        # First draft
        prompt = f"""You are a creative copywriter. Write a haiku advertisement for: {state['product']}

A haiku has exactly 3 lines with 5-7-5 syllable structure.
The haiku should feel warm, human, and conversational.
Respond with ONLY the haiku — no title, no explanation, no punctuation outside the lines."""
    else:
        # Revision based on Brand Guardian feedback
        prompt = f"""You are a creative copywriter. Revise your haiku advertisement for: {state['product']}

Your previous haiku was:
{state['haiku']}

The Brand Guardian rejected it with these suggestions:
{state['suggestions']}

Apply this feedback and write an improved haiku.
A haiku has exactly 3 lines with 5-7-5 syllable structure.
Respond with ONLY the haiku — no title, no explanation, no punctuation outside the lines."""

    response = llm.invoke([HumanMessage(content=prompt)])
    haiku = extract_text(response)
    print(f"Draft haiku:\n{haiku}")

    return {
        **state,
        "haiku": haiku,
        "messages": state["messages"] + [AIMessage(content=f"[Copywriter Draft]\n{haiku}")]
    }

def brand_guardian(state: CopyState) -> CopyState:
    print(f"\n--- Brand Guardian (Iteration {state['iteration'] + 1}) ---")

    # Force approval on final iteration to avoid infinite loop
    if state["iteration"] >= MAX_ITERATIONS - 1:
        print("Max iterations reached — approving best version.")
        return {
            **state,
            "approved": True,
            "iteration": state["iteration"] + 1,
            "messages": state["messages"] + [
                AIMessage(content=f"[Brand Guardian] Approved after revisions!\n\n{state['haiku']}")
            ]
        }

    prompt = f"""You are a Brand Guardian reviewing marketing copy for tone of voice compliance.

Review this haiku advertisement for: {state['product']}

{state['haiku']}

Apply these brand rules strictly:
{BRAND_RULES}

Respond in EXACTLY this format — no other text:

DECISION: APPROVED or REJECTED
FEEDBACK: (if APPROVED, write a warm one-sentence sign-off; if REJECTED, write 2-3 specific, actionable suggestions for improvement)"""

    response = llm.invoke([HumanMessage(content=prompt)])
    review = extract_text(response)
    print(f"Review:\n{review}")

    approved = "DECISION: APPROVED" in review

    # Extract feedback section
    feedback = ""
    if "FEEDBACK:" in review:
        feedback = review.split("FEEDBACK:", 1)[1].strip()

    return {
        **state,
        "approved": approved,
        "suggestions": feedback,
        "iteration": state["iteration"] + 1,
        "messages": state["messages"] + [
            AIMessage(content=f"[Brand Guardian] {'✅ APPROVED' if approved else '❌ REJECTED'}\n{feedback}")
        ]
    }

def route_after_guardian(state: CopyState) -> str:
    if state["approved"]:
        return "approved"
    return "rejected"

builder = StateGraph(CopyState)

builder.add_node("copywriter", copywriter)
builder.add_node("brand_guardian", brand_guardian)

builder.add_edge(START, "copywriter")
builder.add_edge("copywriter", "brand_guardian")
builder.add_conditional_edges(
    "brand_guardian",
    route_after_guardian,
    {
        "approved": END,
        "rejected": "copywriter"
    }
)

graph = builder.compile()

def format_final_response(state: CopyState) -> str:
    iterations = state["iteration"]
    haiku = state["haiku"]
    feedback = state["suggestions"]

    iteration_text = "first attempt" if iterations == 1 else f"{iterations} rounds of refinement"

    return (
        f"Your marketing haiku for **{state['product']}** has been approved "
        f"after {iteration_text}!\n\n"
        f"{haiku}\n\n"
        f"_{feedback}_"
    )

app = ResponsesAgentServerHost(
    options=ResponsesServerOptions(default_fetch_history_count=20))

@app.response_handler
async def handle_create(request: CreateResponse, context: ResponseContext, cancellation_signal: asyncio.Event):

    async def run_graph():
        product = await context.get_input_text() or "a product"

        initial_state: CopyState = {
            "messages": [HumanMessage(content=product)],
            "product": product,
            "haiku": "",
            "suggestions": "",
            "iteration": 0,
            "approved": False,
        }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: graph.invoke(initial_state)
        )

        yield format_final_response(result)

    return TextResponse(context, request, text=run_graph())

if __name__ == "__main__":
    if not AZURE_OPENAI_ENDPOINT:
        print("Warning: AZURE_OPENAI_ENDPOINT not set.")
    if not AZURE_AI_MODEL_DEPLOYMENT_NAME:
        print("Warning: AZURE_AI_MODEL_DEPLOYMENT_NAME not set.")
    app.run()