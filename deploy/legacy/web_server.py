"""Compatibility entry point for existing Docker Compose commands."""
from runpy import run_module


if __name__ == '__main__':
    run_module('kararecall.web_server', run_name='__main__', alter_sys=True)
