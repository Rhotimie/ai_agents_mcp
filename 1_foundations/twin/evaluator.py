from pydantic import BaseModel

EVALUATOR_MODEL = "gemini-3.5-flash-lite"

# A stronger evaluator such as "gemini-3.5-flash" judges more sharply, but the Gemini free tier
# only allows 20 requests/day for it - and this pattern makes 2-4 calls per message.


class Evaluation(BaseModel):
    is_acceptable: bool
    feedback: str


EVALUATOR_SYSTEM_PROMPT = """You are a strict quality evaluator for a digital twin chatbot that
represents a professional on their personal website.

Your ONE job is to check that the Assistant's reply stays strictly on work-related matters:
the person's career, background, skills, experience, education, projects, availability for work,
or arranging professional contact.

Mark the reply as NOT acceptable if it engages with anything off-topic - hobbies, food, sport,
politics, relationships, jokes, general knowledge, coding help, or any other subject unrelated
to this person's professional life - even if the reply is otherwise polite and well written.

Politely declining an off-topic question and steering back to professional topics IS acceptable.

Reply with is_acceptable, and with feedback that tells the Assistant exactly what to change.
"""


def evaluate(client, reply, message, history):
    """Ask a second LLM whether the proposed reply is strictly work-related."""
    conversation = "\n".join(f"{h['role']}: {h['content']}" for h in history)
    user_prompt = f"""Here is the conversation so far:
{conversation}

Here is the latest message from the User:
{message}

Here is the Assistant's proposed reply:
{reply}

Evaluate whether this reply is strictly work-related and acceptable."""

    response = client.beta.chat.completions.parse(
        model=EVALUATOR_MODEL,
        messages=[
            {"role": "system", "content": EVALUATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format=Evaluation,
    )
    return response.choices[0].message.parsed


def build_retry_messages(messages, reply, feedback):
    """Hand the rejected reply back to the generator along with the evaluator's feedback."""
    return messages + [
        {"role": "assistant", "content": reply},
        {
            "role": "user",
            "content": (
                "Your previous reply was rejected by a quality evaluator for not being strictly "
                f"work-related. Here is the feedback:\n\n{feedback}\n\n"
                "Please answer the original question again, staying strictly on professional topics. "
                "If the question is not work-related, politely decline and steer the conversation "
                "back to the person's career, skills and experience. Reply with the corrected answer only."
            ),
        },
    ]
