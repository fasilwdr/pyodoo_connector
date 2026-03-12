# -*- coding: utf-8 -*-
#############################################################################
# Author: Fasil
# Email: fasilwdr@hotmail.com
#############################################################################
import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import httpx

from pyodoo_connect import (
    connect_odoo,
    connect_model,
    OdooSession,
    OdooRecord,
    OdooModel,
    Command,
    OdooException,
    OdooConnectionError,
    OdooAuthenticationError,
    OdooRequestError,
    OdooValidationError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json_response(data: dict, status_code: int = 200) -> MagicMock:
    """Build a mock httpx.Response that returns *data* as JSON."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status_code
    mock_resp.json.return_value = data
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def _rpc_ok(result) -> dict:
    """Wrap *result* in a minimal JSON-RPC success envelope."""
    return {"jsonrpc": "2.0", "result": result}


def _rpc_error(message: str) -> dict:
    """Wrap *message* in a minimal JSON-RPC error envelope."""
    return {
        "jsonrpc": "2.0",
        "error": {
            "code": 200,
            "message": "Odoo Server Error",
            "data": {"message": message},
        },
    }


SESSION_COOKIE = "abc123"
BASE_URL = "https://test.odoo.example.com"


# ---------------------------------------------------------------------------
# connect_odoo
# ---------------------------------------------------------------------------

class TestConnectOdoo:
    def test_successful_login(self):
        auth_response = _json_response({"jsonrpc": "2.0", "result": {"uid": 1}})
        auth_response.cookies = {"session_id": SESSION_COOKIE}

        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value = MockClient.return_value
            instance.post.return_value = auth_response

            session_id = connect_odoo(
                url=BASE_URL, db="mydb", username="admin", password="admin"
            )
            assert session_id == SESSION_COOKIE

    def test_missing_parameters(self):
        with pytest.raises(OdooValidationError):
            connect_odoo(url="", db="db", username="user", password="pass")

    def test_authentication_failure(self):
        fail_response = _json_response({"jsonrpc": "2.0", "result": None})
        fail_response.cookies = {}

        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value = MockClient.return_value
            instance.post.return_value = fail_response

            with pytest.raises(OdooAuthenticationError):
                connect_odoo(
                    url=BASE_URL, db="mydb", username="admin", password="wrong"
                )

    def test_connection_error(self):
        with patch("httpx.Client") as MockClient:
            instance = MockClient.return_value.__enter__.return_value = MockClient.return_value
            instance.post.side_effect = httpx.ConnectError("unreachable")

            with pytest.raises(OdooConnectionError):
                connect_odoo(
                    url=BASE_URL, db="mydb", username="admin", password="admin"
                )


# ---------------------------------------------------------------------------
# connect_model
# ---------------------------------------------------------------------------

class TestConnectModel:
    def test_returns_odoo_model(self):
        model = connect_model(SESSION_COOKIE, BASE_URL, "res.partner")
        assert isinstance(model, OdooModel)

    def test_missing_parameters(self):
        with pytest.raises(OdooValidationError):
            connect_model("", BASE_URL, "res.partner")
        with pytest.raises(OdooValidationError):
            connect_model(SESSION_COOKIE, "", "res.partner")
        with pytest.raises(OdooValidationError):
            connect_model(SESSION_COOKIE, BASE_URL, "")

    def test_url_trailing_slash_stripped(self):
        model = connect_model(SESSION_COOKIE, BASE_URL + "/", "res.partner")
        assert not model._url.endswith("/")

    def test_context_parameter(self):
        ctx = {"lang": "fr_FR"}
        model = connect_model(SESSION_COOKIE, BASE_URL, "res.partner", context=ctx)
        assert model._context["lang"] == "fr_FR"


# ---------------------------------------------------------------------------
# OdooSession
# ---------------------------------------------------------------------------

class TestOdooSession:
    def _make_session(self, session_cookie=SESSION_COOKIE):
        auth_response = _json_response({"jsonrpc": "2.0", "result": {"uid": 1}})
        auth_response.cookies = {"session_id": session_cookie}

        with patch("httpx.Client") as MockClient:
            mock_client = MockClient.return_value
            mock_client.post.return_value = auth_response

            session = OdooSession(
                url=BASE_URL, db="mydb", username="admin", password="admin"
            )
            session._client = mock_client  # keep reference for assertions
            return session, mock_client

    def test_authentication(self):
        auth_response = _json_response({"jsonrpc": "2.0", "result": {"uid": 1}})
        auth_response.cookies = {"session_id": SESSION_COOKIE}

        with patch("httpx.Client") as MockClient:
            mock_client = MockClient.return_value
            mock_client.post.return_value = auth_response

            session = OdooSession(
                url=BASE_URL, db="mydb", username="admin", password="admin"
            )
            assert session.session_id == SESSION_COOKIE

    def test_missing_parameters(self):
        with pytest.raises(OdooValidationError):
            OdooSession(url="", db="db", username="user", password="pass")

    def test_construct_with_existing_session_id(self):
        with patch("httpx.Client") as MockClient:
            mock_client = MockClient.return_value
            session = OdooSession(url=BASE_URL, session_id=SESSION_COOKIE)
            assert session.session_id == SESSION_COOKIE
            mock_client.post.assert_not_called()

    def test_session_id_or_credentials_required(self):
        with pytest.raises(OdooValidationError):
            OdooSession(url=BASE_URL)

    def test_env_returns_model(self):
        auth_response = _json_response({"jsonrpc": "2.0", "result": {"uid": 1}})
        auth_response.cookies = {"session_id": SESSION_COOKIE}

        with patch("httpx.Client") as MockClient:
            mock_client = MockClient.return_value
            mock_client.post.return_value = auth_response

            session = OdooSession(
                url=BASE_URL, db="mydb", username="admin", password="admin"
            )
            model = session.env("res.partner")
            assert isinstance(model, OdooModel)
            assert model._model == "res.partner"

    def test_getitem_returns_model(self):
        with patch("httpx.Client") as MockClient:
            session = OdooSession(url=BASE_URL, session_id=SESSION_COOKIE)
            model = session["res.partner"]
            assert isinstance(model, OdooModel)
            assert model._model == "res.partner"

    def test_call_returns_model(self):
        with patch("httpx.Client"):
            session = OdooSession(url=BASE_URL, session_id=SESSION_COOKIE)
            model = session("res.partner")
            assert isinstance(model, OdooModel)
            assert model._model == "res.partner"

    def test_env_uses_default_context(self):
        with patch("httpx.Client"):
            session = OdooSession(
                url=BASE_URL,
                session_id=SESSION_COOKIE,
                context={"lang": "ar_001", "tz": "Asia/Riyadh"},
            )
            model = session["res.partner"]
            assert model._context["lang"] == "ar_001"
            assert model._context["tz"] == "Asia/Riyadh"

    def test_env_empty_model_raises(self):
        auth_response = _json_response({"jsonrpc": "2.0", "result": {"uid": 1}})
        auth_response.cookies = {"session_id": SESSION_COOKIE}

        with patch("httpx.Client") as MockClient:
            mock_client = MockClient.return_value
            mock_client.post.return_value = auth_response

            session = OdooSession(
                url=BASE_URL, db="mydb", username="admin", password="admin"
            )
            with pytest.raises(OdooValidationError):
                session.env("")

    def test_repr(self):
        auth_response = _json_response({"jsonrpc": "2.0", "result": {"uid": 1}})
        auth_response.cookies = {"session_id": SESSION_COOKIE}

        with patch("httpx.Client") as MockClient:
            mock_client = MockClient.return_value
            mock_client.post.return_value = auth_response

            session = OdooSession(
                url=BASE_URL, db="mydb", username="admin", password="admin"
            )
            assert "mydb" in repr(session)
            assert "admin" in repr(session)


# ---------------------------------------------------------------------------
# OdooModel
# ---------------------------------------------------------------------------

class TestOdooModel:
    def _model(self):
        client = MagicMock(spec=httpx.Client)
        return OdooModel(SESSION_COOKIE, BASE_URL, "res.partner", client=client), client

    def _post_ok(self, client, result):
        client.post.return_value = _json_response(_rpc_ok(result))

    # --- create ---

    def test_create_returns_record(self):
        model, client = self._model()
        self._post_ok(client, 42)
        record = model.create({"name": "Alice"})
        assert isinstance(record, OdooRecord)
        assert record.id == 42

    def test_create_raises_on_falsy_result(self):
        model, client = self._model()
        self._post_ok(client, False)
        with pytest.raises(OdooValidationError):
            model.create({"name": "Alice"})

    # --- browse ---

    def test_browse_single(self):
        model, _ = self._model()
        record = model.browse(7)
        assert isinstance(record, OdooRecord)
        assert record.id == 7

    def test_browse_multiple(self):
        model, _ = self._model()
        records = model.browse([1, 2, 3])
        assert len(records) == 3
        assert all(isinstance(r, OdooRecord) for r in records)

    # --- search ---

    def test_search(self):
        model, client = self._model()
        self._post_ok(client, [1, 2, 3])
        ids = model.search([("name", "ilike", "Alice")])
        assert ids == [1, 2, 3]

    def test_search_with_limit_and_order(self):
        model, client = self._model()
        self._post_ok(client, [5])
        ids = model.search([], limit=1, order="id DESC")
        assert ids == [5]
        call_kwargs = client.post.call_args[1]["json"]
        assert call_kwargs["params"]["kwargs"]["limit"] == 1
        assert call_kwargs["params"]["kwargs"]["order"] == "id DESC"

    def test_search_empty_domain(self):
        model, client = self._model()
        self._post_ok(client, [])
        ids = model.search()
        assert ids == []

    # --- search_count ---

    def test_search_count(self):
        model, client = self._model()
        self._post_ok(client, 5)
        count = model.search_count([("active", "=", True)])
        assert count == 5

    # --- search_read ---

    def test_search_read(self):
        model, client = self._model()
        rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        self._post_ok(client, rows)
        results = model.search_read(fields=["name"])
        assert results == rows

    def test_search_read_with_options(self):
        model, client = self._model()
        self._post_ok(client, [])
        model.search_read(domain=[("active", "=", True)], fields=["name"], limit=10,
                          offset=5, order="name ASC")
        call_kwargs = client.post.call_args[1]["json"]
        kw = call_kwargs["params"]["kwargs"]
        assert kw["fields"] == ["name"]
        assert kw["limit"] == 10
        assert kw["offset"] == 5
        assert kw["order"] == "name ASC"

    # --- write ---

    def test_write(self):
        model, client = self._model()
        self._post_ok(client, True)
        result = model.write(1, {"name": "Bob"})
        assert result is True

    def test_write_list_of_ids(self):
        model, client = self._model()
        self._post_ok(client, True)
        model.write([1, 2], {"active": False})
        call_args = client.post.call_args[1]["json"]
        assert call_args["params"]["args"][0] == [1, 2]

    # --- unlink ---

    def test_unlink(self):
        model, client = self._model()
        self._post_ok(client, True)
        result = model.unlink(1)
        assert result is True

    def test_unlink_list(self):
        model, client = self._model()
        self._post_ok(client, True)
        model.unlink([1, 2, 3])
        call_args = client.post.call_args[1]["json"]
        assert call_args["params"]["args"][0] == [1, 2, 3]

    # --- read ---

    def test_read(self):
        model, client = self._model()
        rows = [{"id": 1, "name": "Alice"}]
        self._post_ok(client, rows)
        result = model.read(1, fields=["name"])
        assert result == rows

    # --- with_context ---

    def test_with_context_dict(self):
        model, client = self._model()
        new_model = model.with_context({"lang": "fr_FR"})
        assert new_model._context["lang"] == "fr_FR"
        assert new_model._client is client

    def test_with_context_kwargs(self):
        model, _ = self._model()
        new_model = model.with_context(lang="de_DE")
        assert new_model._context["lang"] == "de_DE"

    def test_with_user(self):
        model, _ = self._model()
        new_model = model.with_user(7)
        assert new_model._context["uid"] == 7

    def test_with_user_allows_zero(self):
        model, _ = self._model()
        new_model = model.with_user(0)
        assert new_model._context["uid"] == 0

    def test_with_user_requires_value(self):
        model, _ = self._model()
        with pytest.raises(OdooValidationError):
            model.with_user(None)

    def test_sudo(self):
        model, _ = self._model()
        sudo_model = model.sudo()
        assert sudo_model._context["sudo"] is True

    def test_sudo_with_user(self):
        model, _ = self._model()
        sudo_model = model.sudo(5)
        assert sudo_model._context["sudo"] is True
        assert sudo_model._context["uid"] == 5

    # --- dynamic methods ---

    def test_dynamic_method(self):
        model, client = self._model()
        self._post_ok(client, "custom_result")
        result = model.some_custom_method("arg1", key="val")
        assert result == "custom_result"

    # --- __repr__ ---

    def test_repr(self):
        model, _ = self._model()
        assert "res.partner" in repr(model)

    # --- error handling ---

    def test_server_error_raises_request_error(self):
        model, client = self._model()
        client.post.return_value = _json_response(_rpc_error("Something went wrong"))
        with pytest.raises(OdooRequestError, match="Something went wrong"):
            model.search([])

    def test_timeout_raises_connection_error(self):
        model, client = self._model()
        client.post.side_effect = httpx.ReadTimeout("timeout")
        with pytest.raises(OdooConnectionError):
            model.search([])

    def test_http_error_raises_connection_error(self):
        model, client = self._model()
        client.post.side_effect = httpx.ConnectError("refused")
        with pytest.raises(OdooConnectionError):
            model.search([])


# ---------------------------------------------------------------------------
# OdooRecord
# ---------------------------------------------------------------------------

class TestOdooRecord:
    def _record(self):
        client = MagicMock(spec=httpx.Client)
        return OdooRecord(SESSION_COOKIE, BASE_URL, "res.partner", 42, client=client), client

    def _post_ok(self, client, result):
        client.post.return_value = _json_response(_rpc_ok(result))

    # --- id property ---

    def test_id_property(self):
        record, _ = self._record()
        assert record.id == 42

    # --- bool ---

    def test_bool_truthy(self):
        record, _ = self._record()
        assert bool(record) is True

    def test_bool_falsy(self):
        record = OdooRecord(SESSION_COOKIE, BASE_URL, "res.partner", 0)
        assert bool(record) is False

    # --- repr / str ---

    def test_repr(self):
        record, _ = self._record()
        assert "res.partner" in repr(record)
        assert "42" in repr(record)

    def test_str(self):
        record, _ = self._record()
        assert "42" in str(record)

    # --- write ---

    def test_write(self):
        record, client = self._record()
        self._post_ok(client, True)
        result = record.write({"name": "Updated"})
        assert result is True
        call_args = client.post.call_args[1]["json"]
        assert call_args["params"]["args"][0] == [42]

    # --- read ---

    def test_read(self):
        record, client = self._record()
        self._post_ok(client, [{"id": 42, "name": "Alice"}])
        result = record.read(["name"])
        assert result == [{"id": 42, "name": "Alice"}]

    # --- with_context ---

    def test_with_context_creates_new_record(self):
        record, client = self._record()
        new_record = record.with_context(lang="es_ES")
        assert new_record._context["lang"] == "es_ES"
        assert new_record.id == record.id
        assert new_record._client is client

    def test_with_context_dict(self):
        record, _ = self._record()
        new_record = record.with_context({"active_test": False})
        assert new_record._context["active_test"] is False

    def test_with_user(self):
        record, _ = self._record()
        new_record = record.with_user(11)
        assert new_record._context["uid"] == 11

    def test_with_user_allows_zero(self):
        record, _ = self._record()
        new_record = record.with_user(0)
        assert new_record._context["uid"] == 0

    def test_sudo(self):
        record, _ = self._record()
        sudo_record = record.sudo()
        assert sudo_record._context["sudo"] is True

    def test_sudo_with_user(self):
        record, _ = self._record()
        sudo_record = record.sudo(3)
        assert sudo_record._context["sudo"] is True
        assert sudo_record._context["uid"] == 3

    # --- dynamic methods ---

    def test_dynamic_method_passes_id(self):
        record, client = self._record()
        self._post_ok(client, True)
        record.action_confirm()
        call_args = client.post.call_args[1]["json"]
        assert call_args["params"]["args"][0] == [42]
        assert call_args["params"]["method"] == "action_confirm"

    def test_dynamic_method_with_args(self):
        record, client = self._record()
        self._post_ok(client, True)
        record.message_post(body="Hello!")
        call_args = client.post.call_args[1]["json"]
        assert call_args["params"]["kwargs"]["body"] == "Hello!"

    # --- error handling ---

    def test_server_error(self):
        record, client = self._record()
        client.post.return_value = _json_response(_rpc_error("Access denied"))
        with pytest.raises(OdooRequestError, match="Access denied"):
            record.write({"name": "X"})

    def test_timeout_raises_connection_error(self):
        record, client = self._record()
        client.post.side_effect = httpx.ReadTimeout("timeout")
        with pytest.raises(OdooConnectionError):
            record.write({"name": "X"})


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class TestCommand:
    def test_create(self):
        cmd = Command.create({"name": "Tag"})
        assert cmd == (0, 0, {"name": "Tag"})

    def test_update(self):
        cmd = Command.update(5, {"name": "Updated"})
        assert cmd == (1, 5, {"name": "Updated"})

    def test_delete(self):
        cmd = Command.delete(3)
        assert cmd == (2, 3, 0)

    def test_unlink(self):
        cmd = Command.unlink(4)
        assert cmd == (3, 4, 0)

    def test_link(self):
        cmd = Command.link(7)
        assert cmd == (4, 7, 0)

    def test_clear(self):
        cmd = Command.clear()
        assert cmd == (5, 0, 0)

    def test_set(self):
        cmd = Command.set([1, 2, 3])
        assert cmd == (6, 0, [1, 2, 3])


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TestExceptions:
    def test_exception_hierarchy(self):
        assert issubclass(OdooConnectionError, OdooException)
        assert issubclass(OdooAuthenticationError, OdooException)
        assert issubclass(OdooRequestError, OdooException)
        assert issubclass(OdooValidationError, OdooException)

    def test_request_error_stores_response(self):
        resp = {"code": 200, "message": "err"}
        exc = OdooRequestError("msg", resp)
        assert exc.response == resp

    def test_all_exceptions_importable(self):
        # Verify public exports
        import pyodoo_connect as pkg
        assert hasattr(pkg, "OdooException")
        assert hasattr(pkg, "OdooConnectionError")
        assert hasattr(pkg, "OdooAuthenticationError")
        assert hasattr(pkg, "OdooRequestError")
        assert hasattr(pkg, "OdooValidationError")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
