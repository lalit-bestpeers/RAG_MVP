import logging
import threading
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

from app.core.config import settings

logger = logging.getLogger("rag.local_llm")


class LocalLLMService:
    def __init__(self) -> None:
        self._pipe = None
        self._load_started = False
        self._load_lock = threading.Lock()
        self._load_error: Exception | None = None

    def load(self, wait: bool = True) -> None:
        """Start model loading. If wait=True, blocks until loaded; otherwise loads in
        a background thread so the app can start responding while the model downloads."""
        with self._load_lock:
            if self._pipe is not None or self._load_started:
                if wait:
                    self._wait_for_load()
                return
            self._load_started = True
            self._load_error = None

        def _do_load() -> None:
            try:
                self._pipe = self._build_pipeline()
                logger.info("Model '%s' loaded successfully.", settings.llm_model)
            except Exception as exc:  # noqa: BLE001
                self._load_error = exc
                logger.exception("Failed to load model '%s'", settings.llm_model)

        if wait:
            _do_load()
        else:
            threading.Thread(target=_do_load, daemon=True, name="local-llm-loader").start()

    def _wait_for_load(self) -> None:
        deadline_logged = False
        while self._pipe is None:
            if self._load_error is not None:
                raise self._load_error
            if not deadline_logged:
                logger.info(
                    "Model '%s' is still loading (first run downloads from HuggingFace). "
                    "Waiting...",
                    settings.llm_model,
                )
                deadline_logged = True
            import time

            time.sleep(1)

    def _build_pipeline(self):
        model_name = settings.llm_model
        cache_dir = settings.llm_cache_dir
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        logger.info("Loading model '%s' (first run downloads from HuggingFace)...", model_name)

        tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            cache_dir=cache_dir,
            torch_dtype=_resolve_dtype(settings.llm_torch_dtype),
            device_map=_resolve_device(settings.llm_device),
            low_cpu_mem_usage=True,
        )
        model.eval()

        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
        )
        return pipe

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.load(wait=True)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        pipe = self._pipe
        tokenizer = pipe.tokenizer

        if tokenizer.chat_template is not None:
            input_text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            input_text = f"<|system|>\n{system_prompt}\n<|user|>\n{user_prompt}\n<|assistant|>\n"

        gen_kwargs = {
            "max_new_tokens": settings.llm_max_new_tokens,
            "do_sample": settings.llm_temperature > 0,
            "temperature": settings.llm_temperature,
            "eos_token_id": tokenizer.eos_token_id,
        }
        if settings.llm_temperature <= 0:
            gen_kwargs["num_beams"] = 1

        outputs = pipe(
            input_text,
            return_full_text=False,
            pad_token_id=tokenizer.eos_token_id,
            **gen_kwargs,
        )
        generated = outputs[0]["generated_text"]
        return generated.strip()


def _resolve_device(device_str: str) -> str:
    if device_str == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device_str


def _resolve_dtype(dtype_str: str):
    default = torch.float16 if torch.cuda.is_available() else torch.float32
    return {
        "auto": default,
        "float16": torch.float16,
        "float32": torch.float32,
        "bfloat16": torch.bfloat16,
    }.get(dtype_str, default)


llm_service = LocalLLMService()
