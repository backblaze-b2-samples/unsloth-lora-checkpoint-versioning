import { RunCreateForm } from "@/components/runs/run-form";

export default function NewRunPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">New run</h1>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground text-pretty">
          Configure a fine-tuning run. On a CUDA GPU it runs a real Unsloth
          LoRA/QLoRA fine-tune of the selected 4-bit model; with no GPU it runs a
          real (but tiny) transformers + PEFT LoRA fine-tune on CPU. Every
          artifact — config, per-epoch checkpoints, and the final adapter — is
          versioned on Backblaze B2.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2 max-w-3xl">
        <RunCreateForm />
      </div>
    </div>
  );
}
