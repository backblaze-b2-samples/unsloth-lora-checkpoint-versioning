"""LoRA/QLoRA fine-tuning engine.

ALL heavy ML imports (torch, transformers, peft, unsloth) are contained in this
module — the external-SDK containment invariant. They are imported lazily inside
the functions that need them, so importing this module (for structural/contract
tests and OpenAPI export) never pulls in torch. `unsloth` is imported lazily and
ONLY inside the CUDA branch.

Device selection is auto-detected at runtime: the first available of CUDA -> CPU
(default CPU). There is no unconditional `.cuda()` and no assert/raise on a
missing GPU. Apple MPS is deliberately not selected: Unsloth (Triton /
bitsandbytes) has no Apple-MPS path, so on Apple Silicon this sample falls back
to the portable CPU path.

  - CUDA present -> a real Unsloth `FastLanguageModel` LoRA/QLoRA fine-tune of
    the selected 4-bit base model (the vendor's own engine).
  - No CUDA -> a real but minimal transformers + PEFT LoRA fine-tune of a tiny
    CPU-friendly causal LM. This produces genuine LoRA adapter safetensors, a
    real loss curve, and real per-epoch checkpoints — not a mock — so the full
    B2 versioning loop is real and verifiable on a GPU-less host.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field

# The ungated, tiny CPU-friendly model used by the portable (no-CUDA) path.
CPU_DEMO_MODEL = "hf-internal-testing/tiny-random-LlamaForCausalLM"
_TOKENIZER_FALLBACK = "hf-internal-testing/llama-tokenizer"
_MAX_SEQ_LEN = 128

# Callbacks injected by the service so this module never touches boto3.
#   save_checkpoint(epoch, files) -> checkpoint key prefix on B2
#   report_epoch(epoch, avg_loss, checkpoint_key)
#   report_progress(current_epoch, latest_loss, message)
CheckpointSaver = Callable[[int, dict[str, bytes]], str]
EpochReporter = Callable[[int, float, str | None], None]
ProgressReporter = Callable[[int, "float | None", str], None]


@dataclass
class TrainResult:
    resolved_model: str
    device: str
    final_adapter_files: dict[str, bytes]
    epoch_losses: list[float] = field(default_factory=list)
    method_note: str = ""


def select_device(override: str = "") -> str:
    """First available of CUDA -> CPU. `override` (e.g. "cpu") wins if set."""
    if override:
        return override.lower()
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _dump_adapter(model) -> dict[str, bytes]:
    """Serialize the current LoRA adapter to bytes (safetensors + config)."""
    with tempfile.TemporaryDirectory() as d:
        model.save_pretrained(d)
        files: dict[str, bytes] = {}
        for root, _, names in os.walk(d):
            for name in names:
                path = os.path.join(root, name)
                rel = os.path.relpath(path, d).replace(os.sep, "/")
                with open(path, "rb") as fh:
                    files[rel] = fh.read()
        return files


def _run_loop(
    *,
    model,
    tokenizer,
    epochs: int,
    learning_rate: float,
    examples: list[str],
    device: str,
    max_steps_per_epoch: int,
    vocab_size: int,
    save_checkpoint: CheckpointSaver,
    report_epoch: EpochReporter,
    report_progress: ProgressReporter,
) -> list[float]:
    """Shared manual training loop for both the CPU and CUDA paths.

    A plain torch optimizer loop (no HF Trainer / accelerate) so per-epoch loss
    and checkpointing are explicit and dependency-light.
    """
    import torch

    model.to(device)
    model.train()
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=learning_rate)

    epoch_losses: list[float] = []
    for epoch in range(1, epochs + 1):
        report_progress(epoch, None, f"Training epoch {epoch}/{epochs}")
        step_losses: list[float] = []
        for i, text in enumerate(examples):
            if i >= max_steps_per_epoch:
                break
            enc = tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=_MAX_SEQ_LEN,
            )
            # Guard against a fallback tokenizer whose vocab exceeds the model's
            # embedding table (avoids an index error on a size mismatch).
            input_ids = enc["input_ids"].clamp(max=vocab_size - 1).to(device)
            attn = enc.get("attention_mask")
            kwargs = {"input_ids": input_ids, "labels": input_ids}
            if attn is not None:
                kwargs["attention_mask"] = attn.to(device)
            out = model(**kwargs)
            loss = out.loss
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            step_losses.append(float(loss.item()))
            report_progress(epoch, step_losses[-1], f"Epoch {epoch}/{epochs} step {i + 1}")

        avg = sum(step_losses) / len(step_losses) if step_losses else 0.0
        epoch_losses.append(avg)
        checkpoint_key = save_checkpoint(epoch, _dump_adapter(model))
        report_epoch(epoch, avg, checkpoint_key)

    return epoch_losses


def _train_cpu_peft(
    *,
    epochs: int,
    learning_rate: float,
    lora_rank: int,
    examples: list[str],
    hf_token: str,
    max_steps_per_epoch: int,
    save_checkpoint: CheckpointSaver,
    report_epoch: EpochReporter,
    report_progress: ProgressReporter,
    requested_model: str,
    method: str,
) -> TrainResult:
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    report_progress(0, None, "Loading CPU-demo base model")
    base = AutoModelForCausalLM.from_pretrained(CPU_DEMO_MODEL, token=hf_token or None)
    try:
        tokenizer = AutoTokenizer.from_pretrained(CPU_DEMO_MODEL, token=hf_token or None)
    except Exception:
        tokenizer = AutoTokenizer.from_pretrained(_TOKENIZER_FALLBACK)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token or tokenizer.unk_token

    lconf = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_rank * 2,
        target_modules="all-linear",
        lora_dropout=0.0,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(base, lconf)

    note = (
        "Ran on CPU: portable transformers + PEFT LoRA fine-tune of a tiny "
        f"causal LM ({CPU_DEMO_MODEL}). The requested base model "
        f"'{requested_model}' and 4-bit QLoRA quantization require a CUDA GPU "
        "(Unsloth has no Apple-MPS path)."
    )
    losses = _run_loop(
        model=model,
        tokenizer=tokenizer,
        epochs=epochs,
        learning_rate=learning_rate,
        examples=examples,
        device="cpu",
        max_steps_per_epoch=max_steps_per_epoch,
        vocab_size=int(base.config.vocab_size),
        save_checkpoint=save_checkpoint,
        report_epoch=report_epoch,
        report_progress=report_progress,
    )
    return TrainResult(
        resolved_model=CPU_DEMO_MODEL,
        device="cpu",
        final_adapter_files=_dump_adapter(model),
        epoch_losses=losses,
        method_note=note,
    )


def _train_unsloth(
    *,
    base_model: str,
    method: str,
    epochs: int,
    learning_rate: float,
    lora_rank: int,
    examples: list[str],
    hf_token: str,
    max_steps_per_epoch: int,
    save_checkpoint: CheckpointSaver,
    report_epoch: EpochReporter,
    report_progress: ProgressReporter,
) -> TrainResult:
    # Imported lazily and ONLY on the CUDA branch — unsloth/bitsandbytes/triton
    # do not install on non-CUDA hosts and must never load there.
    from unsloth import FastLanguageModel

    report_progress(0, None, f"Loading {base_model} (Unsloth 4-bit)")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base_model,
        max_seq_length=_MAX_SEQ_LEN,
        dtype=None,
        load_in_4bit=True,  # QLoRA and LoRA both start from the 4-bit base here
        token=hf_token or None,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_rank,
        lora_alpha=lora_rank * 2,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        use_gradient_checkpointing="unsloth",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    losses = _run_loop(
        model=model,
        tokenizer=tokenizer,
        epochs=epochs,
        learning_rate=learning_rate,
        examples=examples,
        device="cuda",
        max_steps_per_epoch=max_steps_per_epoch,
        vocab_size=int(model.config.vocab_size),
        save_checkpoint=save_checkpoint,
        report_epoch=report_epoch,
        report_progress=report_progress,
    )
    return TrainResult(
        resolved_model=base_model,
        device="cuda",
        final_adapter_files=_dump_adapter(model),
        epoch_losses=losses,
        method_note=f"Ran real Unsloth {method} fine-tune on CUDA.",
    )


def train(
    *,
    base_model: str,
    method: str,
    epochs: int,
    learning_rate: float,
    lora_rank: int,
    examples: list[str],
    device: str,
    hf_token: str,
    max_steps_per_epoch: int,
    save_checkpoint: CheckpointSaver,
    report_epoch: EpochReporter,
    report_progress: ProgressReporter,
) -> TrainResult:
    """Dispatch to the CUDA (Unsloth) or CPU (PEFT) path based on `device`."""
    common = {
        "epochs": epochs,
        "learning_rate": learning_rate,
        "lora_rank": lora_rank,
        "examples": examples,
        "hf_token": hf_token,
        "max_steps_per_epoch": max_steps_per_epoch,
        "save_checkpoint": save_checkpoint,
        "report_epoch": report_epoch,
        "report_progress": report_progress,
    }
    if device == "cuda":
        return _train_unsloth(base_model=base_model, method=method, **common)
    return _train_cpu_peft(requested_model=base_model, method=method, **common)
