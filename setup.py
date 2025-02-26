#!/usr/bin/env python3
import sys
import subprocess
import platform
import os
import time
import logging
import threading

VENV_DIR = ".venv"
REQUIREMENTS_FILE = "requirements.txt"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

def in_virtualenv():
    return sys.prefix != sys.base_prefix

def create_virtualenv():
    logger.info(f"Creating virtual environment using uv in '{VENV_DIR}'...")
    try:
        subprocess.check_call(["uv", "venv"])
        logger.info("Virtual environment created using uv.")
    except Exception as e:
        sys.exit("Failed to create virtual environment using uv: " + str(e))

def get_venv_python():
    if platform.system() == "Windows":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        return os.path.join(VENV_DIR, "bin", "python")

def bootstrap_setuptools(python_exe):
    logger.info("Bootstrapping setuptools in the virtual environment...")
    try:
        subprocess.check_call([python_exe, "-m", "ensurepip"])
    except Exception as e:
        logger.warning("ensurepip failed: " + str(e))
    try:
        subprocess.check_call([python_exe, "-m", "pip", "install", "--upgrade", "pip", "setuptools"])
        logger.info("setuptools bootstrapped successfully.")
    except Exception as e:
        sys.exit("Failed to bootstrap setuptools: " + str(e))

def install_requirements(python_exe):
    if not os.path.exists(REQUIREMENTS_FILE):
        sys.exit("requirements.txt not found!")
    logger.info(f"Installing requirements from {REQUIREMENTS_FILE} using {python_exe}...")
    try:
        subprocess.check_call([python_exe, "-m", "pip", "install", "-r", REQUIREMENTS_FILE])
        logger.info("Requirements installed successfully.")
    except Exception as e:
        sys.exit("Failed to install requirements: " + str(e))

def install_uv(python_exe):
    try:
        subprocess.check_call([python_exe, "-m", "uv", "--version"])
        logger.info("uv is already installed.")
    except Exception:
        logger.info("Installing uv via pip...")
        try:
            subprocess.check_call([python_exe, "-m", "pip", "install", "uv"])
            subprocess.check_call([python_exe, "-m", "uv", "self", "update"])
            logger.info("uv installed and updated successfully.")
        except Exception as e:
            sys.exit("Failed to install uv: " + str(e))

def relaunch_in_venv(method):
    os.environ["ALREADY_IN_VENV"] = "1"
    os.environ["INSTALL_METHOD"] = method
    venv_python = get_venv_python()
    logger.info(f"Re-launching setup script using venv interpreter: {venv_python}")
    subprocess.check_call([venv_python] + sys.argv)
    sys.exit(0)

try:
    from setuptools import setup, find_packages
except ImportError:
    if in_virtualenv():
        bootstrap_setuptools(sys.executable)
        from setuptools import setup, find_packages
    else:
        sys.exit("setuptools not found. Please install setuptools and try again.")

def run_setup():
    setup(
        name="Max Agentic AI Builder", 
        version="0.1.0",
        description="An automated, agentic workflow for intelligent data crawling, processing, and semantic content generation.",
        author="Dev Rahman",
        author_email="dev@devrahman.com",
        packages=find_packages(),
        install_requires=[],
        entry_points={
            "console_scripts": [
                "max-agentic=src.main:main",
            ],
        },
        classifiers=[
            "Programming Language :: Python :: 3",
            "Operating System :: POSIX :: Linux",
        ],
    )

def main():
    already_in_venv = os.environ.get("ALREADY_IN_VENV") == "1"
    install_method = os.environ.get("INSTALL_METHOD")  # "1", "2", or "3"
    if not already_in_venv:
        print("Select installation method:")
        print("  [1] System pip (no virtual environment)")
        print("  [2] pip in a virtual environment (venv)")
        print("  [3] uv (requires virtual environment)")
        choice = input("Enter your choice (1, 2, or 3): ").strip()
        if choice not in {"1", "2", "3"}:
            sys.exit("Invalid choice. Exiting.")
    else:
        choice = install_method if install_method else "3"

    if choice == "1":
        logger.info("Installing requirements using system pip...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_FILE])
        except Exception as e:
            sys.exit("Failed to install requirements: " + str(e))
        run_setup()
    elif choice == "2":
        if not in_virtualenv():
            if not os.path.exists(VENV_DIR):
                subprocess.check_call([sys.executable, "-m", "venv", VENV_DIR])
            relaunch_in_venv("2")
        else:
            bootstrap_setuptools(sys.executable)
            install_requirements(sys.executable)
            run_setup()
    elif choice == "3":
        if not in_virtualenv():
            if not os.path.exists(VENV_DIR):
                logger.info("Creating virtual environment using uv...")
                try:
                    subprocess.check_call(["uv", "venv"])
                    logger.info("Virtual environment created using uv.")
                except Exception as e:
                    sys.exit("Failed to create virtual environment using uv: " + str(e))
            try:
                subprocess.check_call(["uv", "pip", "install", "setuptools"])
                logger.info("setuptools installed successfully using uv pip.")
            except Exception as e:
                sys.exit("Failed to install setuptools using uv pip: " + str(e))
            relaunch_in_venv("3")
        else:
            bootstrap_setuptools(sys.executable)
            try:
                logger.info("Installing requirements using uv pip...")
                subprocess.check_call(["uv", "pip", "install", "-r", REQUIREMENTS_FILE])
                logger.info("Requirements installed successfully with uv pip.")
            except Exception as e:
                sys.exit("Failed to install requirements using uv pip: " + str(e))
            try:
                subprocess.check_call(["uv", "self", "update"])
                logger.info("uv self update completed successfully.")
            except Exception as e:
                logger.warning("uv self update failed: " + str(e))
            run_setup()

if __name__ == "__main__":
    main()
