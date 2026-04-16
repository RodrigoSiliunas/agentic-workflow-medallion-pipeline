"""Testes do allowlist de imports no validator (T1 Phase 4)."""

from __future__ import annotations

import pytest

from observer.validator import _check_forbidden_imports, validate_fix


class TestForbiddenImports:
    @pytest.mark.parametrize(
        "code",
        [
            "import subprocess\n",
            "import socket as s\n",
            "import ctypes\n",
            "import pickle\n",
            "import marshal\n",
            "import shutil\n",
            "from subprocess import run\n",
            "from socket import socket\n",
            "import subprocess.pipes\n",
        ],
    )
    def test_rejects_forbidden_imports(self, code: str):
        errs = _check_forbidden_imports(code, "pipelines/foo.py")
        assert errs, f"esperava rejeição para:\n{code}"
        assert any("proibido" in e for e in errs)

    @pytest.mark.parametrize(
        "code",
        [
            "import os\n",  # os é permitido no geral, só atributos bloqueados
            "import json\n",
            "import pandas as pd\n",
            "from pyspark.sql import functions as F\n",
            "from datetime import datetime\n",
        ],
    )
    def test_accepts_safe_imports(self, code: str):
        errs = _check_forbidden_imports(code, "pipelines/foo.py")
        assert errs == []


class TestForbiddenCalls:
    def test_rejects_os_system(self):
        code = "import os\nos.system('rm -rf /')\n"
        errs = _check_forbidden_imports(code, "pipelines/foo.py")
        assert any("os.system" in e for e in errs)

    @pytest.mark.parametrize(
        "snippet,label",
        [
            ("os.popen('whoami')", "os.popen"),
            ("os.execv('/bin/sh', [])", "os.execv"),
            ("os.remove('/etc/passwd')", "os.remove"),
            ("os.unlink('x')", "os.unlink"),
            ("os._exit(0)", "os._exit"),
        ],
    )
    def test_rejects_os_attr_calls(self, snippet: str, label: str):
        code = f"import os\n{snippet}\n"
        errs = _check_forbidden_imports(code, "pipelines/foo.py")
        assert any(label in e for e in errs), f"{label} não foi detectado"

    @pytest.mark.parametrize(
        "snippet,label",
        [
            ("eval('2+2')", "eval"),
            ("exec('x=1')", "exec"),
            ("__import__('socket')", "__import__"),
        ],
    )
    def test_rejects_builtin_exec(self, snippet: str, label: str):
        errs = _check_forbidden_imports(snippet + "\n", "pipelines/foo.py")
        assert any(label in e for e in errs)


class TestIntegrationWithValidateFix:
    def test_validate_fix_rejects_subprocess(self):
        code = "import subprocess\nsubprocess.run(['ls'])\n"
        result = validate_fix(code, "pipelines/foo.py")
        assert not result.valid
        assert "forbidden_imports" in result.checks_run
        assert any("subprocess" in err for err in result.errors)

    def test_validate_fix_accepts_clean_code(self):
        code = (
            "from pyspark.sql import functions as F\n"
            "def transform(df):\n"
            "    return df.filter(F.col('x').isNotNull())\n"
        )
        result = validate_fix(code, "pipelines/foo.py")
        assert result.valid, result.errors
        assert "forbidden_imports" in result.checks_run

    def test_self_exempt_for_validator(self):
        """Fix ao próprio validator.py pode listar os nomes proibidos."""
        code = (
            "FORBIDDEN_IMPORTS = frozenset({'subprocess', 'socket'})\n"
        )
        result = validate_fix(code, "observer/validator.py")
        assert result.valid, result.errors
