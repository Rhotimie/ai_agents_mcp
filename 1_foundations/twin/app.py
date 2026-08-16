import os
from openai import OpenAI
from context import TWIN_SYSTEM_PROMPT
from tools import tools, handle_tool_calls
from evaluator import evaluate, build_retry_messages
from styles import CSS, JS, EXAMPLES
from dotenv import load_dotenv
import gradio as gr

load_dotenv(override=True)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODEL_NAME = "gemini-3.5-flash-lite"
MAX_ATTEMPTS = 3
google_api_key = os.getenv("GOOGLE_API_KEY")

openai = OpenAI(base_url=GEMINI_BASE_URL, api_key=google_api_key)

system = [{"role": "system", "content": TWIN_SYSTEM_PROMPT}]

FALLBACK_REPLY = (
    "I'm afraid I can only talk about my professional background, skills and experience. "
    "Is there anything about my career I can help you with?"
)


def generate(messages, already_called):
    """The agent loop: call the model, run any tools it asks for, repeat until it's done."""
    response = openai.chat.completions.create(model=MODEL_NAME, messages=messages, tools=tools)
    while response.choices[0].finish_reason == "tool_calls":
        message = response.choices[0].message
        results = handle_tool_calls(message.tool_calls, already_called)
        messages.append(message)
        messages.extend(results)
        response = openai.chat.completions.create(model=MODEL_NAME, messages=messages, tools=tools)
    return response.choices[0].message.content


def chat(message, history):
    """Generate a reply, then have a second LLM check it is strictly work-related.

    If the evaluator rejects it, regenerate with the feedback attached and try again,
    up to MAX_ATTEMPTS. This is the Evaluator-Optimizer pattern acting as an output guardrail.
    """
    history = [{"role": h["role"], "content": h["content"]} for h in history]
    messages = system + history + [{"role": "user", "content": message}]

    # Shared across every attempt for this message, so a retry cannot re-fire a tool
    already_called = set()
    reply = generate(messages, already_called)

    for attempt in range(MAX_ATTEMPTS):
        try:
            evaluation = evaluate(openai, reply, message, history)
        except Exception as error:
            # Never take the whole site down because the evaluator was unavailable.
            print(f"Evaluator failed ({error}) - accepting the reply as-is", flush=True)
            return reply

        if evaluation.is_acceptable:
            print(f"Evaluator passed the reply on attempt {attempt + 1}", flush=True)
            return reply

        print(f"Evaluator rejected attempt {attempt + 1}: {evaluation.feedback}", flush=True)
        reply = generate(build_retry_messages(messages, reply, evaluation.feedback), already_called)

    print("Evaluator never passed - returning the fallback reply", flush=True)
    return FALLBACK_REPLY


if __name__ == "__main__":
    gr.ChatInterface(
        chat,
        examples=EXAMPLES,
        title="Digital Twin",
        description="Talk to my AI twin about my career",
        chatbot=gr.Chatbot(show_label=False),
    ).launch(css=CSS, js=JS, theme=gr.themes.Base())
