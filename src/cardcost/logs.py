import json
import logging
import re
import uuid
from contextvars import ContextVar

run_id_var: ContextVar[str] = ContextVar("run_id", default="-")

_PATTERNS = [
    (re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}(?: ?[A-Z0-9]{1,3})?\b"), "[IBAN]"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[EMAIL]"),
    (re.compile(r"(?:\+|\b0)\d[\d /-]{5,}\d"), "[PHONE]"),
]
_STD = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message"}


def redact(text: str) -> str:
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


def new_run_id() -> str:
    run_id = uuid.uuid4().hex[:12]
    run_id_var.set(run_id)
    return run_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "level": record.levelname,
            "logger": record.name,
            "run_id": run_id_var.get(),
            "msg": record.getMessage(),
        }
        data |= {k: v for k, v in vars(record).items() if k not in _STD}
        return redact(json.dumps(data, default=str, ensure_ascii=False))


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
