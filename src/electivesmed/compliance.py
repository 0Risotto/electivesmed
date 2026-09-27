"""Outreach compliance rules: required copy, style guardrails, and banned content."""

DEFAULT_LAWFUL_BASIS = "unknown"
LAWFUL_BASIS_VALUES = (
    DEFAULT_LAWFUL_BASIS,
    "consent",
    "legitimate_interest_b2b",
    "contract",
)

OPT_OUT_SENTENCE = (
    "If you'd prefer not to hear from me again, reply 'unsubscribe' "
    "and I'll remove you from my list."
)

ALLOWED_ATTACHMENT_CONTENT_TYPES = (
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)

SPAM_WORDS = (
    "free",
    "guarantee",
    "urgent",
    "act now",
    "limited time",
    "risk-free",
    "no obligation",
    "click here",
    "buy now",
)

# Characters that must never appear in outbound copy (machine-enforced).
BANNED_PUNCTUATION = {
    "\u2014": "em dash",
    "\u2013": "en dash",
    "--": "double hyphen standing in for a dash",
}

# AI-typical single words. Matched with word boundaries and common suffixes.
BANNED_WORDS = (
    "delve",
    "leverage",
    "seamless",
    "robust",
    "elevate",
    "unlock",
    "foster",
    "empower",
    "holistic",
    "synergy",
    "streamline",
    "landscape",
    "realm",
    "tapestry",
    "testament",
    "pivotal",
    "meticulous",
    "intricate",
    "underscore",
    "showcase",
    "boast",
    "nestle",
    "vibrant",
    "paramount",
    "myriad",
    "plethora",
    "embark",
    "bespoke",
    "curate",
    "revolutionize",
    "revolutionary",
    "transformative",
    "groundbreaking",
    "supercharge",
    "harness",
    "spearhead",
    "catalyze",
)

# AI-typical and corporate-filler phrases, matched case-insensitively.
BANNED_PHRASES = (
    "in today's fast-paced world",
    "ever-evolving",
    "at its core",
    "look no further",
    "dive into",
    "delve into",
    "game changer",
    "game-changer",
    "take it to the next level",
    "more than just",
    "it's not just",
    "i hope this email finds you well",
    "i wanted to reach out",
    "i am reaching out",
    "at your earliest convenience",
    "circle back",
    "touch base",
    "move the needle",
    "best-in-class",
    "world-class",
    "cutting-edge",
    "state of the art",
    "state-of-the-art",
    "next-generation",
    "future-proof",
)

AI_TYPICAL_TERMS = BANNED_WORDS + BANNED_PHRASES
