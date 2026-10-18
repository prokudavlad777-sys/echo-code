"""Model backends for Echo Code.

* demo  - tiny built-in backend, no dependencies (default, works anywhere)
* transformers - real ~1.5B-parameter model via Hugging Face (needs torch + transformers)

Select with environment variables:
    ECHO_BACKEND=transformers
    ECHO_MODEL=Qwen/Qwen2.5-Coder-1.5B-Instruct   (any ~1.5B chat/code model)
"""
import os
import re

SYSTEM_PROMPT = (
    "You are Echo Code, a concise and helpful coding assistant. "
    "Answer with working code in fenced blocks and brief explanations."
)

DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"  # ~1.5B parameters


def count_tokens(text):
    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))


class DemoBackend:
    name = "echo-demo"

    SNIPPETS = {
        "python": "```python\nprint('Hello from Echo Code')\n```",
        "rust": "```rust\nfn main() {\n    println!(\"Hello from Echo Code\");\n}\n```",
        "java": "```java\npublic class Main {\n    public static void main(String[] a) {\n        System.out.println(\"Hello from Echo Code\");\n    }\n}\n```",
        "c++": "```cpp\n#include <iostream>\nint main() { std::cout << \"Hello from Echo Code\\n\"; }\n```",
        "sql": "```sql\nSELECT * FROM chats ORDER BY id DESC LIMIT 10;\n```",
        "javascript": "```javascript\nconsole.log('Hello from Echo Code');\n```",
    }

    def generate(self, messages, max_new_tokens=512):
        last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        low = last.lower()
        for lang, code in self.SNIPPETS.items():
            if lang in low:
                return f"Demo mode: a starter snippet for {lang}.\n\n{code}\n\nEnable a real model with ECHO_BACKEND=transformers."
        return (
            "Demo mode is active, so I can only echo: " + last[:300] +
            "\n\nSet ECHO_BACKEND=transformers to use the 1.5B model."
        )


class TransformersBackend:
    def __init__(self, model_id):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.name = model_id
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(model_id)
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        self.model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=dtype, device_map="auto")

    def generate(self, messages, max_new_tokens=512):
        prompt = self.tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.tok(prompt, return_tensors="pt").to(self.model.device)
        with self.torch.no_grad():
            out = self.model.generate(
                **inputs, max_new_tokens=max_new_tokens, do_sample=True,
                temperature=0.4, top_p=0.9, pad_token_id=self.tok.eos_token_id,
            )
        return self.tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def load_backend():
    if os.environ.get("ECHO_BACKEND", "demo") == "transformers":
        try:
            return TransformersBackend(os.environ.get("ECHO_MODEL", DEFAULT_MODEL))
        except Exception as exc:  # missing deps, no weights, not enough RAM
            print(f"[echo-code] could not load model ({exc}); falling back to demo backend")
    return DemoBackend()
