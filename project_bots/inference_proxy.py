"""Compatibility entry point for the llama.cpp-only broker."""
from .llama_proxy import make_handler, main

if __name__ == "__main__":
    main()

