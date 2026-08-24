import litellm

async def judge_response(prompt: str, response: str) -> float:
    """
    LLM-as-a-Judge: Evaluate the quality of the response.
    Returns a score between 0.0 and 1.0.
    """
    eval_prompt = f"""
    Evaluate the following response to the prompt based on relevance, accuracy, and completeness.
    Respond ONLY with a float between 0.0 (terrible) and 1.0 (perfect).

    Prompt: {prompt}
    Response: {response}
    """
    try:
        judge_res = await litellm.acompletion(
            model="gpt-4o",  # Use a strong model for judging
            messages=[{"role": "user", "content": eval_prompt}],
            max_tokens=10,
            temperature=0.0
        )
        score_str = judge_res.choices[0].message.content.strip()
        score = float(score_str)
        return max(0.0, min(1.0, score))
    except Exception as e:
        print(f"Judge Error: {e}")
        # Default to a neutral score if the judge fails
        return 0.5
