import os

from litsearch import config


def test_save_and_load_user_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.delenv("IEEE_API_KEY", raising=False)
    monkeypatch.delenv("SERPAPI_KEY", raising=False)
    p = config.save_user_keys({"IEEE_API_KEY": " abc ", "SERPAPI_KEY": ""})
    assert p.parent.parent == tmp_path and p.read_text() == "IEEE_API_KEY=abc\n"
    assert os.environ["IEEE_API_KEY"] == "abc"
    config.save_user_keys({"SERPAPI_KEY": "s"})  # other keys are kept
    assert config.read_user_keys() == {"IEEE_API_KEY": "abc", "SERPAPI_KEY": "s"}
    config.save_user_keys({"IEEE_API_KEY": ""})  # blank removes
    assert config.read_user_keys() == {"SERPAPI_KEY": "s"} and "IEEE_API_KEY" not in os.environ


def test_environment_wins_over_files(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("IEEE_API_KEY=from_cwd\n")
    config.user_env_path().parent.mkdir(parents=True)
    config.user_env_path().write_text("IEEE_API_KEY=from_user\nSERPAPI_KEY=user_serp\n")
    monkeypatch.setenv("SERPAPI_KEY", "from_env")
    monkeypatch.delenv("IEEE_API_KEY", raising=False)
    config.load_keys()
    assert os.environ["IEEE_API_KEY"] == "from_cwd" and os.environ["SERPAPI_KEY"] == "from_env"
