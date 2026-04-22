#!/usr/bin/env python3
"""
PulseEngine Local Installer
============================
Cross-platform installer for the PulseEngine Market Intelligence Platform.

Usage:
    python install.py

Requirements:
    - Python 3.11 – 3.14 (pre-installed by the user)
    - Internet connection (to install packages from PyPI)

This script will:
    1. Check the Python version
    2. Create a virtual environment at .venv/
    3. Install all dependencies from requirements.txt
    4. Verify the installation by importing key packages
    5. Generate a platform-appropriate launch script and print next steps

Constraints:
    - Does NOT require admin/sudo privileges
    - Does NOT install system-level packages
    - Does NOT modify PATH or system environment variables
    - Does NOT write outside the repo directory
"""

import sys
import platform
import subprocess
import textwrap
from pathlib import Path

# Reconfigure stdout/stderr to UTF-8 on Windows so box-drawing characters
# don't crash with UnicodeEncodeError on cp1252 consoles.
if platform.system() == "Windows":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_PYTHON = (3, 11)
MAX_PYTHON = (3, 14)

REPO_ROOT = Path(__file__).resolve().parent
VENV_DIR = REPO_ROOT / ".venv"
REQUIREMENTS = REPO_ROOT / "requirements.txt"
# Key packages to verify after installation
VERIFY_IMPORTS = [
    "streamlit",
    "yfinance",
    "pandas",
    "plotly",
    "feedparser",
    "vaderSentiment",
]

# ANSI colour codes (disabled automatically on Windows without ANSI support)
_USE_COLOUR = sys.stdout.isatty() and platform.system() != "Windows"

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOUR else text

def green(t):  return _c("32", t)
def yellow(t): return _c("33", t)
def red(t):    return _c("31", t)
def bold(t):   return _c("1",  t)
def cyan(t):   return _c("36", t)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _banner() -> None:
    print()
    print(bold(cyan("╔══════════════════════════════════════════════════╗")))
    print(bold(cyan("║      PulseEngine — Local Installer  v0.3         ║")))
    print(bold(cyan("╚══════════════════════════════════════════════════╝")))
    print()


def _step(n: int, total: int, msg: str) -> None:
    print(f"  {bold(f'[{n}/{total}]')} {msg}")


def _ok(msg: str) -> None:
    print(f"        {green('✔')}  {msg}")


def _warn(msg: str) -> None:
    print(f"        {yellow('⚠')}  {msg}")


def _fail(msg: str) -> None:
    print(f"\n  {red('✘  ERROR:')} {msg}\n")


def _abort(msg: str, hint: str = "") -> None:
    _fail(msg)
    if hint:
        print(textwrap.indent(textwrap.dedent(hint).strip(), "     "))
        print()
    sys.exit(1)


# ---------------------------------------------------------------------------
# Step 1 — Python version check
# ---------------------------------------------------------------------------

def check_python_version() -> None:
    _step(1, 5, "Checking Python version …")
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"

    if (v.major, v.minor) < MIN_PYTHON:
        _abort(
            f"Python {version_str} is too old. PulseEngine requires Python "
            f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}–{MAX_PYTHON[0]}.{MAX_PYTHON[1]}.",
            hint="""
            Please install a supported Python version and re-run this installer.

            Download from:  https://www.python.org/downloads/
            Recommended:    Python 3.12 (latest stable)

            After installing, run:
                python3.12 install.py
            """,
        )

    if (v.major, v.minor) > MAX_PYTHON:
        _abort(
            f"Python {version_str} has not been tested with PulseEngine yet. "
            f"Supported range: {MIN_PYTHON[0]}.{MIN_PYTHON[1]}–{MAX_PYTHON[0]}.{MAX_PYTHON[1]}.",
            hint="""
            If you know what you're doing, edit MIN_PYTHON / MAX_PYTHON in install.py
            and re-run. Otherwise, install Python 3.12 and retry.
            """,
        )

    _ok(f"Python {version_str} — supported ✓")


# ---------------------------------------------------------------------------
# Step 2 — Create virtual environment
# ---------------------------------------------------------------------------

def create_venv() -> None:
    _step(2, 5, f"Creating virtual environment at {VENV_DIR.relative_to(REPO_ROOT)} …")

    if VENV_DIR.exists():
        _warn(".venv/ already exists — skipping creation (will still re-install packages)")
        return

    result = subprocess.run(
        [sys.executable, "-m", "venv", str(VENV_DIR)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        _abort(
            "Failed to create virtual environment.",
            hint=f"""
            Error output:
            {result.stderr.strip()}

            On some systems the 'venv' module needs to be installed separately:
              Ubuntu/Debian:  sudo apt install python3-venv
              Fedora:         sudo dnf install python3-venv
            """,
        )

    _ok(".venv/ created successfully")


# ---------------------------------------------------------------------------
# Step 3 — Install dependencies
# ---------------------------------------------------------------------------

def _venv_python() -> Path:
    """Return the path to the Python executable inside the venv."""
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _venv_pip() -> Path:
    """Return the path to pip inside the venv."""
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "pip.exe"
    return VENV_DIR / "bin" / "pip"


def install_dependencies() -> None:
    _step(3, 5, "Installing dependencies from requirements.txt …")

    if not REQUIREMENTS.exists():
        _abort(
            "requirements.txt not found.",
            hint="Make sure you are running install.py from the root of the cloned repo.",
        )

    pip = _venv_pip()
    if not pip.exists():
        _abort(
            "pip not found inside .venv/. The virtual environment may be corrupted.",
            hint="Delete .venv/ and re-run install.py.",
        )

    # Upgrade pip silently first to avoid noisy warnings
    subprocess.run(
        [str(pip), "install", "--quiet", "--upgrade", "pip"],
        capture_output=True,
    )

    print("        Installing packages … (this may take a minute)", flush=True)

    result = subprocess.run(
        [str(pip), "install", "-r", str(REQUIREMENTS)],
        capture_output=False,   # stream output so user can see progress
    )

    if result.returncode != 0:
        _abort(
            "Dependency installation failed.",
            hint="""
            Common causes:
              • No internet connection
              • Corporate firewall or proxy blocking PyPI
              • Disk space exhausted

            Try running manually:
                .venv/Scripts/pip install -r requirements.txt    (Windows)
                .venv/bin/pip install -r requirements.txt        (macOS/Linux)
            """,
        )

    _ok("All packages installed")


# ---------------------------------------------------------------------------
# Step 4 — Verify installation
# ---------------------------------------------------------------------------

def verify_install() -> None:
    _step(4, 5, "Verifying installation …")

    python = _venv_python()
    if not python.exists():
        _abort(
            "Python executable not found inside .venv/. The virtual environment may be corrupted.",
            hint="Delete .venv/ and re-run install.py.",
        )

    all_ok = True

    for pkg in VERIFY_IMPORTS:
        result = subprocess.run(
            [str(python), "-c", f"import {pkg}"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            _ok(f"{pkg}")
        else:
            _warn(f"{pkg} — import FAILED")
            all_ok = False

    if not all_ok:
        _abort(
            "One or more packages failed to import. The installation is incomplete.",
            hint="""
            Try deleting .venv/ and running install.py again.
            If the problem persists, check the GitHub Issues page:
            https://github.com/The-Pulse-Engine/Pulse-Engine_Market_Intelligence_Platform/issues
            """,
        )


# ---------------------------------------------------------------------------
# Step 5 — Generate launch script
# ---------------------------------------------------------------------------

def generate_launch_script() -> Path:
    _step(5, 5, "Generating launch script …")

    system = platform.system()

    if system == "Windows":
        launch_path = REPO_ROOT / "launch.bat"
        content = textwrap.dedent("""\
            @echo off
            REM PulseEngine Launch Script (Windows)
            REM Generated by install.py - do not edit manually

            cd /d "%~dp0"

            if not exist ".venv\\Scripts\\streamlit.exe" (
                echo [ERROR] Virtual environment not found. Please run: python install.py
                pause
                exit /b 1
            )

            echo Starting PulseEngine dashboard...
            echo Dashboard will open at: http://localhost:8501
            echo Press Ctrl+C to stop.
            echo.

            ".venv\\Scripts\\streamlit.exe" run "dashboard\\main.py"
            pause
        """)
        launch_path.write_text(content, encoding="utf-8")
        _ok("launch.bat created")

        # Also create a PowerShell version
        ps_path = REPO_ROOT / "launch.ps1"
        ps_content = textwrap.dedent("""\
            # PulseEngine Launch Script (PowerShell)
            # Generated by install.py — do not edit manually

            Set-Location $PSScriptRoot

            if (-not (Test-Path ".venv\\Scripts\\streamlit.exe")) {
                Write-Host "[ERROR] Virtual environment not found. Please run: python install.py" -ForegroundColor Red
                exit 1
            }

            Write-Host "Starting PulseEngine dashboard..." -ForegroundColor Cyan
            Write-Host "Dashboard will open at: http://localhost:8501" -ForegroundColor Green
            Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow
            Write-Host ""

            & ".venv\\Scripts\\streamlit.exe" run "dashboard\\main.py"
        """)
        ps_path.write_text(ps_content, encoding="utf-8")
        _ok("launch.ps1 created")
        return launch_path

    else:
        # macOS and Linux
        launch_path = REPO_ROOT / "launch.sh"
        content = textwrap.dedent("""\
            #!/usr/bin/env bash
            # PulseEngine Launch Script (macOS/Linux)
            # Generated by install.py — do not edit manually

            set -e
            cd "$(dirname "$0")"

            if [ ! -f ".venv/bin/streamlit" ]; then
                echo "[ERROR] Virtual environment not found. Please run: python install.py"
                exit 1
            fi

            echo "Starting PulseEngine dashboard..."
            echo "Dashboard will open at: http://localhost:8501"
            echo "Press Ctrl+C to stop."
            echo ""

            ".venv/bin/streamlit" run "pulseengine/local/dashboard.py"
        """)
        launch_path.write_text(content, encoding="utf-8")
        launch_path.chmod(0o755)  # make executable
        _ok("launch.sh created (executable bit set)")
        return launch_path


# ---------------------------------------------------------------------------
# Success message
# ---------------------------------------------------------------------------

def print_success(launch_path: Path) -> None:
    system = platform.system()
    launch_name = launch_path.name

    print()
    print(bold(green("╔══════════════════════════════════════════════════╗")))
    print(bold(green("║        Installation complete!  🎉                ║")))
    print(bold(green("╚══════════════════════════════════════════════════╝")))
    print()
    print(bold("  Next steps:"))
    print()

    if system == "Windows":
        print(f"  {cyan('Option A')} — Double-click  {bold(launch_name)}")
        print(f"  {cyan('Option B')} — Run from terminal:")
        print(f"             {bold('launch.bat')}")
        print(f"  {cyan('Option C')} — PowerShell:")
        print(f"             {bold('.\\launch.ps1')}")
    else:
        print(f"  {cyan('Option A')} — Run from terminal:")
        print(f"             {bold('./launch.sh')}")
        print(f"  {cyan('Option B')} — Manually activate the venv and run:")
        print(f"             {bold('source .venv/bin/activate')}")
        print(f"             {bold('streamlit run pulseengine/local/dashboard.py')}")

    print()
    print(f"  The dashboard will open at:  {bold(cyan('http://localhost:8501'))}")
    print()
    print(f"  {yellow('Note:')} This tool is for informational purposes only.")
    print("         It does not constitute financial advice. See Docs/DISCLAIMER.md")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _banner()

    check_python_version()
    create_venv()
    install_dependencies()
    verify_install()
    launch_path = generate_launch_script()

    print_success(launch_path)


if __name__ == "__main__":
    main()
