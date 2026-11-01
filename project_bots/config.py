"""Setup configuration; API keys are referenced by environment variable only."""
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit

PRESETS = {
    'openai': ('OpenAI', 'https://api.openai.com/v1', 'OPENAI_API_KEY'),
    'anthropic': ('Anthropic', 'https://api.anthropic.com/v1', 'ANTHROPIC_API_KEY'),
    'google': ('Google Gemini', 'https://generativelanguage.googleapis.com/v1beta', 'GOOGLE_API_KEY'),
    'xai': ('xAI', 'https://api.x.ai/v1', 'XAI_API_KEY'),
    'openrouter': ('OpenRouter', 'https://openrouter.ai/api/v1', 'OPENROUTER_API_KEY'),
    'deepseek': ('DeepSeek', 'https://api.deepseek.com', 'DEEPSEEK_API_KEY'),
    'mistral': ('Mistral', 'https://api.mistral.ai/v1', 'MISTRAL_API_KEY'),
    'groq': ('Groq', 'https://api.groq.com/openai/v1', 'GROQ_API_KEY'),
    'together': ('Together AI', 'https://api.together.ai/v1', 'TOGETHER_API_KEY'),
    'fireworks': ('Fireworks AI', 'https://api.fireworks.ai/inference/v1', 'FIREWORKS_API_KEY'),
    'ollama': ('Ollama', 'http://127.0.0.1:11434/v1', ''),
    'lmstudio': ('LM Studio', 'http://127.0.0.1:1234/v1', ''),
    'codex': ('Codex / ChatGPT', '', ''),
    'custom': ('Custom OpenAI-compatible', '', ''),
}


def config_path():
    return Path(os.environ.get('PROJECT_BOTS_CONFIG', Path.home() / '.config/project-bots/config.json'))


def validate_config(data):
    if not isinstance(data, dict) or set(data) - {'provider', 'endpoint', 'model', 'api_key_env'}:
        raise ValueError('Unknown configuration fields')
    provider = data.get('provider')
    if provider not in PRESETS:
        raise ValueError('Unknown provider')
    model = data.get('model', '')
    if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/+-]{0,127}', model):
        raise ValueError('Invalid model identifier')
    endpoint = data.get('endpoint', PRESETS[provider][1])
    if not isinstance(endpoint, str):
        raise ValueError('Invalid endpoint')
    if provider == 'codex':
        if endpoint:
            raise ValueError('Codex uses its own CLI authentication')
    else:
        parts = urlsplit(endpoint)
        if parts.username or parts.password or parts.query or parts.fragment or not parts.hostname or not parts.port in (None, 443, 80, 11434, 1234) and parts.scheme == 'http':
            raise ValueError('Invalid endpoint')
        if parts.scheme != 'https' and not (parts.scheme == 'http' and parts.hostname in ('localhost', '127.0.0.1', '[::1]', '::1')):
            raise ValueError('Endpoint must use HTTPS, except loopback')
    env = data.get('api_key_env', PRESETS[provider][2])
    if not isinstance(env, str) or (env and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', env)):
        raise ValueError('Invalid environment variable name')
    if provider == 'codex' and env:
        raise ValueError('Codex uses its own CLI authentication')
    return {'provider': provider, 'endpoint': endpoint, 'model': model, 'api_key_env': env}


def save_config(data, path=None):
    path = Path(path or config_path())
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.config-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(validate_config(data), f, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load_config(path=None):
    path = Path(path or config_path())
    return validate_config(json.loads(path.read_text())) if path.exists() else None
