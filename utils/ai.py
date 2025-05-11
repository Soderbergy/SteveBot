import os
import logging
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger("S.T.E.V.E")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_nicknames(theme: str, count: int):
    prompt = (
        f"Generate {count} creative and funny nicknames based on the theme: '{theme}'. "
        "The names should be short, unique, and not include offensive content. "
        "Return ONLY the nicknames as a comma-separated list."
    )

    try:
        response = client.chat.completions.create(model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=150)

        raw_output = response.choices[0].message.content
        nicknames = [
            name.strip().lstrip("0123456789.- ") for name in raw_output.split(",")
            if name.strip()
        ]

        logger.info(f"Generated {len(nicknames)} nicknames with theme '{theme}'")
        return nicknames[:count]

    except Exception as e:
        logger.error(f"AI nickname generation failed: {e}")
        fallback = [f"{theme.title()}Clown_{i+1}" for i in range(count)]
        return fallback