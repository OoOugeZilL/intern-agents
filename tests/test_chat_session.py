from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from askdata.chat_session import ChatSession


class FakeQueryService:
    def EnsureSchemaIndex(self):
        return SimpleNamespace(
            databases={
                "california_schools": SimpleNamespace(tables=[]),
                "card_games": SimpleNamespace(tables=[]),
            }
        )


def test_start_normalizes_cli_database_id_alias():
    session = ChatSession(queryService=FakeQueryService(), databaseId="california-school")

    session._EnsureSchemaIndex()
    session._NormalizeSelectedDatabase()

    assert session.databaseId == "california_schools"


def test_switch_database_accepts_alias(capsys):
    session = ChatSession(queryService=FakeQueryService())
    session._EnsureSchemaIndex()

    session._SwitchDatabase("california school")

    assert session.databaseId == "california_schools"
    assert "Using database:" in capsys.readouterr().out
