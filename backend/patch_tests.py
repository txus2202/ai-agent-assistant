import os
import re

def add_list_models(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # We need to find `class XXX(ILLMProvider):` and insert `list_models` if it's missing
    # Since python indentation matters, we just do a string replacement on `def complete(`
    # to add `list_models` after or before it.

    if "def complete(" in content and "def list_models(" not in content:
        new_content = re.sub(
            r'([ \t]+)def complete\(',
            r'\1def list_models(self) -> list[dict[str, str]]:\n\1    return [{"id": "test", "name": "Test"}]\n\n\1def complete(',
            content
        )
        if new_content != content:
            with open(file_path, 'w') as f:
                f.write(new_content)
            print(f"Patched {file_path}")

for root, _, files in os.walk('tests'):
    for f in files:
        if f.endswith('.py'):
            add_list_models(os.path.join(root, f))
