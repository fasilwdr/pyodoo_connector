# -*- coding: utf-8 -*-
#############################################################################
# Author: Fasil
# Email: fasilwdr@hotmail.com
# WhatsApp: https://wa.me/966538952934
# Facebook: https://www.facebook.com/fasilwdr
# Instagram: https://www.instagram.com/fasilwdr
#############################################################################
"""
Mock-based unit tests for pyodoo_connect v0.3.0.
No live Odoo server is required.
"""
import pytest
from unittest.mock import MagicMock, patch, call

from pyodoo_connect import (
    connect_odoo,
    connect_model,
    OdooSession,
    OdooModel,
    OdooRecord,
    Command,
    OdooException,
    OdooConnectionError,
    OdooAuthenticationError,
    OdooRequestError,
    OdooValidationError,
)
import httpx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(result=None, error=None, status_code=200, cookies=None):
    """Build a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if error:
        resp.json.return_value = {"error": error}
    else:
        resp.json.return_value = {"result": result}
    resp.cookies = cookies or {}
    return resp


@pytest.fixture
def mock_http_client():
    """Patch httpx.Client so no real HTTP calls are made."""
    with patch("pyodoo_connect.odoo.httpx.Client") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        yield mock_client


@pytest.fixture
def session(mock_http_client):
    """Return an OdooSession backed by a mock HTTP client."""
    return OdooSession(url="https://test.odoo.com", session_id="test_session_123")


@pytest.fixture
def partner_model(session):
    return session("res.partner")


@pytest.fixture
def partner_record(session):
    return OdooRecord(
        session_id="test_session_123",
        url="https://test.odoo.com",
        model="res.partner",
        record_id=42,
        context={"lang": "en_US", "tz": "UTC"},
        client=session._client,
    )


# ===========================================================================
# connect_odoo
# ===========================================================================

class TestConnectOdoo:

    def test_success(self, mock_http_client):
        cookies = MagicMock()
        cookies.get.return_value = "sid_abc123"
        mock_http_client.post.return_value = _mock_response(
            result={"uid": 1, "name": "Admin"},
            cookies=cookies,
        )
        sid = connect_odoo("https://test.odoo.com", "mydb", "admin", "admin")
        assert sid == "sid_abc123"

    def test_missing_url_raises(self):
        with pytest.raises(OdooValidationError):
            connect_odoo("", "db", "user", "pass")

    def test_missing_db_raises(self):
        with pytest.raises(OdooValidationError):
            connect_odoo("https://test.odoo.com", "", "user", "pass")

    def test_missing_username_raises(self):
        with pytest.raises(OdooValidationError):
            connect_odoo("https://test.odoo.com", "db", "", "pass")

    def test_missing_password_raises(self):
        with pytest.raises(OdooValidationError):
            connect_odoo("https://test.odoo.com", "db", "user", "")

    def test_auth_failure_raises(self, mock_http_client):
        mock_http_client.post.return_value = _mock_response(result=None)
        with pytest.raises(OdooAuthenticationError):
            connect_odoo("https://test.odoo.com", "db", "admin", "wrong")

    def test_no_session_cookie_raises(self, mock_http_client):
        cookies = MagicMock()
        cookies.get.return_value = None
        mock_http_client.post.return_value = _mock_response(
            result={"uid": 1}, cookies=cookies
        )
        with pytest.raises(OdooAuthenticationError):
            connect_odoo("https://test.odoo.com", "db", "admin", "admin")

    def test_http_error_raises_connection_error(self, mock_http_client):
        mock_http_client.post.side_effect = httpx.HTTPError("network fail")
        with pytest.raises(OdooConnectionError):
            connect_odoo("https://test.odoo.com", "db", "admin", "admin")

    def test_trailing_slash_stripped(self, mock_http_client):
        cookies = MagicMock()
        cookies.get.return_value = "sid_xyz"
        mock_http_client.post.return_value = _mock_response(
            result={"uid": 2}, cookies=cookies
        )
        sid = connect_odoo("https://test.odoo.com/", "db", "admin", "admin")
        assert sid == "sid_xyz"
        called_url = mock_http_client.post.call_args[0][0]
        assert called_url == "https://test.odoo.com/web/session/authenticate"


# ===========================================================================
# connect_model (legacy helper)
# ===========================================================================

class TestConnectModel:

    def test_returns_odoo_model(self):
        with pytest.warns(DeprecationWarning):
            model = connect_model("sid123", "https://test.odoo.com", "res.partner")
        assert isinstance(model, OdooModel)
        assert model._model == "res.partner"

    def test_strips_trailing_slash(self):
        with pytest.warns(DeprecationWarning):
            model = connect_model("sid", "https://test.odoo.com/", "res.partner")
        assert model._url == "https://test.odoo.com"

    def test_missing_session_id_raises(self):
        with pytest.warns(DeprecationWarning), pytest.raises(OdooValidationError):
            connect_model("", "https://test.odoo.com", "res.partner")

    def test_missing_url_raises(self):
        with pytest.warns(DeprecationWarning), pytest.raises(OdooValidationError):
            connect_model("sid", "", "res.partner")

    def test_missing_model_raises(self):
        with pytest.warns(DeprecationWarning), pytest.raises(OdooValidationError):
            connect_model("sid", "https://test.odoo.com", "")

    def test_deprecation_warning_message(self):
        with pytest.warns(DeprecationWarning, match="0.4.0"):
            connect_model("sid", "https://test.odoo.com", "res.partner")


# ===========================================================================
# OdooSession
# ===========================================================================

class TestOdooSession:

    def test_creation(self, mock_http_client):
        env = OdooSession(url="https://test.odoo.com", session_id="s123")
        assert env._url == "https://test.odoo.com"
        assert env._session_id == "s123"

    def test_missing_url_raises(self):
        with pytest.raises(OdooValidationError):
            OdooSession(url="", session_id="s123")

    def test_missing_session_id_raises(self):
        with pytest.raises(OdooValidationError):
            OdooSession(url="https://test.odoo.com", session_id="")

    def test_call_returns_model(self, session):
        model = session("res.partner")
        assert isinstance(model, OdooModel)
        assert model._model == "res.partner"

    def test_getitem_returns_model(self, session):
        model = session["res.partner"]
        assert isinstance(model, OdooModel)
        assert model._model == "res.partner"

    def test_call_and_getitem_equivalent(self, session):
        m1 = session("res.partner")
        m2 = session["res.partner"]
        assert m1._model == m2._model
        assert m1._session_id == m2._session_id

    def test_shared_client(self, session):
        m1 = session("res.partner")
        m2 = session("sale.order")
        assert m1._client is session._client
        assert m2._client is session._client

    def test_with_context_dict(self, session):
        env2 = session.with_context({"lang": "fr_FR"})
        assert env2._context["lang"] == "fr_FR"
        assert session._context.get("lang") != "fr_FR"

    def test_with_context_kwargs(self, session):
        env2 = session.with_context(tz="America/New_York")
        assert env2._context["tz"] == "America/New_York"

    def test_empty_model_name_raises(self, session):
        with pytest.raises(OdooValidationError):
            session("")

    def test_default_verify_true(self):
        """OdooSession must pass verify=True to httpx.Client by default."""
        with patch("pyodoo_connect.odoo.httpx.Client") as mock_cls:
            mock_cls.return_value = MagicMock()
            OdooSession(url="https://test.odoo.com", session_id="s123")
            mock_cls.assert_called_once_with(verify=True)

    def test_verify_false_opt_out(self):
        """Callers can explicitly opt out of TLS verification."""
        with patch("pyodoo_connect.odoo.httpx.Client") as mock_cls:
            mock_cls.return_value = MagicMock()
            OdooSession(url="https://test.odoo.com", session_id="s123", verify=False)
            mock_cls.assert_called_once_with(verify=False)

    def test_with_context_reuses_client(self, session):
        """with_context() must return a session that shares the same httpx.Client."""
        env2 = session.with_context(lang="de_DE")
        assert env2._client is session._client


# ===========================================================================
# OdooModel – search
# ===========================================================================

class TestOdooModelSearch:

    def test_search_returns_list_of_records(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[1, 2, 3])
        records = partner_model.search([("is_company", "=", True)])
        assert len(records) == 3
        assert all(isinstance(r, OdooRecord) for r in records)

    def test_search_record_ids(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[7, 8])
        records = partner_model.search([])
        assert records[0].id == 7
        assert records[1].id == 8

    def test_search_empty_result(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[])
        records = partner_model.search([("name", "=", "Nobody")])
        assert records == []

    def test_search_false_result(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=False)
        records = partner_model.search([])
        assert records == []

    def test_search_with_limit(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[1, 2])
        partner_model.search([("is_company", "=", True)], limit=2)
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["kwargs"]["limit"] == 2

    def test_search_with_offset(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[3])
        partner_model.search([], offset=10)
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["kwargs"]["offset"] == 10

    def test_search_with_order(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[1])
        partner_model.search([], order="name ASC")
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["kwargs"]["order"] == "name ASC"

    def test_search_no_limit_key_when_not_passed(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[1])
        partner_model.search([])
        payload = mock_http_client.post.call_args[1]["json"]
        assert "limit" not in payload["params"]["kwargs"]

    def test_search_limit_1_returns_single_record(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[5])
        record = partner_model.search([("name", "=", "John")], limit=1)
        assert isinstance(record, OdooRecord)
        assert record.id == 5
        assert bool(record) is True

    def test_search_limit_1_empty_result_returns_falsy_record(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[])
        record = partner_model.search([("name", "=", "Nobody")], limit=1)
        assert isinstance(record, OdooRecord)
        assert bool(record) is False

    def test_search_limit_1_false_result_returns_falsy_record(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=False)
        record = partner_model.search([("name", "=", "Nobody")], limit=1)
        assert isinstance(record, OdooRecord)
        assert bool(record) is False

    def test_search_limit_gt_1_still_returns_list(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[1, 2])
        records = partner_model.search([], limit=2)
        assert isinstance(records, list)
        assert len(records) == 2


# ===========================================================================
# OdooModel – search_read
# ===========================================================================

class TestOdooModelSearchRead:

    def test_returns_list_of_dicts(self, mock_http_client, partner_model):
        data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        mock_http_client.post.return_value = _mock_response(result=data)
        result = partner_model.search_read([("is_company", "=", True)])
        assert result == data

    def test_with_fields(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[{"id": 1, "name": "X"}])
        partner_model.search_read([], fields=["name", "email"])
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["kwargs"]["fields"] == ["name", "email"]

    def test_empty_result(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[])
        assert partner_model.search_read([]) == []

    def test_false_result_returns_empty_list(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=False)
        assert partner_model.search_read([]) == []


# ===========================================================================
# OdooModel – search_count
# ===========================================================================

class TestOdooModelSearchCount:

    def test_returns_integer(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=42)
        count = partner_model.search_count([("is_company", "=", True)])
        assert count == 42

    def test_zero_count(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=0)
        assert partner_model.search_count([]) == 0

    def test_false_result_returns_zero(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=False)
        assert partner_model.search_count([]) == 0


# ===========================================================================
# OdooModel – create
# ===========================================================================

class TestOdooModelCreate:

    def test_returns_record(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=99)
        record = partner_model.create({"name": "New Partner"})
        assert isinstance(record, OdooRecord)
        assert record.id == 99

    def test_create_validation_error_on_false(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=False)
        with pytest.raises(OdooValidationError):
            partner_model.create({"name": "Bad"})


# ===========================================================================
# OdooModel – write / unlink
# ===========================================================================

class TestOdooModelWrite:

    def test_write_single_id(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=True)
        assert partner_model.write(1, {"name": "Updated"}) is True

    def test_write_multiple_ids(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=True)
        assert partner_model.write([1, 2, 3], {"active": False}) is True
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["args"][0] == [1, 2, 3]

    def test_write_single_int_converted_to_list(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=True)
        partner_model.write(5, {"name": "X"})
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["args"][0] == [5]


class TestOdooModelUnlink:

    def test_unlink_single_id(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=True)
        assert partner_model.unlink(1) is True

    def test_unlink_multiple_ids(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=True)
        partner_model.unlink([1, 2])
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["args"][0] == [1, 2]


# ===========================================================================
# OdooModel – read
# ===========================================================================

class TestOdooModelRead:

    def test_read_single_id(self, mock_http_client, partner_model):
        data = [{"id": 1, "name": "Alice"}]
        mock_http_client.post.return_value = _mock_response(result=data)
        result = partner_model.read(1)
        assert result == data
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["args"][0] == [1]

    def test_read_multiple_ids(self, mock_http_client, partner_model):
        data = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
        mock_http_client.post.return_value = _mock_response(result=data)
        assert partner_model.read([1, 2]) == data

    def test_read_with_fields(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[{"id": 1, "name": "X"}])
        partner_model.read([1], fields=["name"])
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["kwargs"].get("fields") == ["name"]


# ===========================================================================
# OdooModel – browse
# ===========================================================================

class TestOdooModelBrowse:

    def test_browse_single_int(self, partner_model):
        record = partner_model.browse(7)
        assert isinstance(record, OdooRecord)
        assert record.id == 7

    def test_browse_list(self, partner_model):
        records = partner_model.browse([1, 2, 3])
        assert len(records) == 3
        assert [r.id for r in records] == [1, 2, 3]

    def test_browse_shares_client(self, session, partner_model):
        record = partner_model.browse(1)
        assert record._client is session._client


# ===========================================================================
# OdooModel – sudo / with_user / with_context
# ===========================================================================

class TestOdooModelModifiers:

    def test_sudo_returns_new_model(self, partner_model):
        sudoed = partner_model.sudo()
        assert isinstance(sudoed, OdooModel)
        assert sudoed is not partner_model

    def test_sudo_preserves_client(self, partner_model):
        assert partner_model.sudo()._client is partner_model._client

    def test_with_user_returns_new_model(self, partner_model):
        m = partner_model.with_user(2)
        assert isinstance(m, OdooModel)
        assert m is not partner_model

    def test_with_context_dict(self, partner_model):
        m = partner_model.with_context({"lang": "de_DE"})
        assert m._context["lang"] == "de_DE"

    def test_with_context_kwargs(self, partner_model):
        m = partner_model.with_context(active_test=False)
        assert m._context["active_test"] is False

    def test_with_context_does_not_mutate_original(self, partner_model):
        original_lang = partner_model._context.get("lang")
        partner_model.with_context(lang="es_ES")
        assert partner_model._context.get("lang") == original_lang


# ===========================================================================
# OdooModel – dynamic method call
# ===========================================================================

class TestOdooModelDynamic:

    def test_dynamic_method_call(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result="ok")
        result = partner_model.some_custom_method("arg1", key="val")
        assert result == "ok"
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["method"] == "some_custom_method"
        assert payload["params"]["args"] == ["arg1"]


# ===========================================================================
# OdooRecord – identity / dunder
# ===========================================================================

class TestOdooRecordIdentity:

    def test_id_property(self, partner_record):
        assert partner_record.id == 42

    def test_repr(self, partner_record):
        assert repr(partner_record) == "res.partner(42,)"

    def test_bool_true(self, partner_record):
        assert bool(partner_record) is True

    def test_bool_false(self, session):
        record = OdooRecord("sid", "https://test.odoo.com", "res.partner", 0, client=session._client)
        assert bool(record) is False

    def test_equality(self, session):
        r1 = OdooRecord("sid", "https://test.odoo.com", "res.partner", 5, client=session._client)
        r2 = OdooRecord("sid", "https://test.odoo.com", "res.partner", 5, client=session._client)
        assert r1 == r2

    def test_inequality_different_id(self, session):
        r1 = OdooRecord("sid", "https://test.odoo.com", "res.partner", 5, client=session._client)
        r2 = OdooRecord("sid", "https://test.odoo.com", "res.partner", 6, client=session._client)
        assert r1 != r2

    def test_inequality_different_model(self, session):
        r1 = OdooRecord("sid", "https://test.odoo.com", "res.partner", 5, client=session._client)
        r2 = OdooRecord("sid", "https://test.odoo.com", "sale.order", 5, client=session._client)
        assert r1 != r2

    def test_hashable(self, partner_record):
        s = {partner_record}
        assert partner_record in s


# ===========================================================================
# OdooRecord – write / unlink
# ===========================================================================

class TestOdooRecordWrite:

    def test_write_returns_true(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(result=True)
        assert partner_record.write({"name": "Updated"}) is True

    def test_write_sends_record_id(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(result=True)
        partner_record.write({"name": "X"})
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["args"][0] == [42]

    def test_write_clears_cache(self, mock_http_client, partner_record):
        partner_record._cache["name"] = "Old"
        mock_http_client.post.return_value = _mock_response(result=True)
        partner_record.write({"name": "New"})
        assert "name" not in partner_record._cache


class TestOdooRecordUnlink:

    def test_unlink_returns_true(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(result=True)
        assert partner_record.unlink() is True

    def test_unlink_sends_record_id(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(result=True)
        partner_record.unlink()
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["args"][0] == [42]


# ===========================================================================
# OdooRecord – field access via _FieldProxy
# ===========================================================================

class TestOdooRecordFieldAccess:

    def test_field_read(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(
            result=[{"id": 42, "name": "John Doe"}]
        )
        assert str(partner_record.name) == "John Doe"

    def test_field_caching(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(
            result=[{"id": 42, "name": "Cached"}]
        )
        _ = str(partner_record.name)
        _ = str(partner_record.name)
        assert mock_http_client.post.call_count == 1

    def test_refresh_clears_cache(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(
            result=[{"id": 42, "name": "First"}]
        )
        _ = str(partner_record.name)
        partner_record.refresh()
        mock_http_client.post.return_value = _mock_response(
            result=[{"id": 42, "name": "Second"}]
        )
        assert str(partner_record.name) == "Second"

    def test_bool_field(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(
            result=[{"id": 42, "active": True}]
        )
        assert bool(partner_record.active) is True

    def test_false_field_str(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(
            result=[{"id": 42, "phone": False}]
        )
        assert str(partner_record.phone) == ""

    def test_field_eq(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(
            result=[{"id": 42, "name": "Alice"}]
        )
        assert partner_record.name == "Alice"

    def test_field_used_in_format(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(
            result=[{"id": 42, "name": "Bob"}]
        )
        msg = f"Hello {partner_record.name}"
        assert msg == "Hello Bob"


# ===========================================================================
# OdooRecord – dynamic method call via _FieldProxy
# ===========================================================================

class TestOdooRecordDynamicMethod:

    def test_method_call(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(result=True)
        result = partner_record.action_confirm()
        assert result is True
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["method"] == "action_confirm"
        assert payload["params"]["args"][0] == [42]

    def test_method_call_with_args(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(result="posted")
        partner_record.message_post(body="Hello")
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["method"] == "message_post"
        assert payload["params"]["kwargs"].get("body") == "Hello"


# ===========================================================================
# OdooRecord – modifiers
# ===========================================================================

class TestOdooRecordModifiers:

    def test_sudo_returns_new_record(self, partner_record):
        r = partner_record.sudo()
        assert isinstance(r, OdooRecord)
        assert r is not partner_record
        assert r.id == partner_record.id

    def test_sudo_shares_client(self, partner_record):
        assert partner_record.sudo()._client is partner_record._client

    def test_with_user_returns_new_record(self, partner_record):
        r = partner_record.with_user(3)
        assert isinstance(r, OdooRecord)
        assert r.id == partner_record.id

    def test_with_context_dict(self, partner_record):
        r = partner_record.with_context({"lang": "nl_NL"})
        assert r._context["lang"] == "nl_NL"

    def test_with_context_kwargs(self, partner_record):
        r = partner_record.with_context(active_test=False)
        assert r._context["active_test"] is False

    def test_with_context_preserves_id(self, partner_record):
        assert partner_record.with_context(lang="ar_AR").id == 42


# ===========================================================================
# Error handling
# ===========================================================================

class TestErrorHandling:

    def test_odoo_error_in_response(self, mock_http_client, partner_model):
        error = {
            "code": 200,
            "message": "Odoo Server Error",
            "data": {"message": "Record not found"},
        }
        mock_http_client.post.return_value = _mock_response(error=error)
        with pytest.raises(OdooRequestError, match="Record not found"):
            partner_model.search([])

    def test_timeout_raises_connection_error(self, mock_http_client, partner_model):
        mock_http_client.post.side_effect = httpx.ReadTimeout("timed out")
        with pytest.raises(OdooConnectionError, match="timed out"):
            partner_model.search([])

    def test_http_error_raises_connection_error(self, mock_http_client, partner_model):
        mock_http_client.post.side_effect = httpx.HTTPError("bad response")
        with pytest.raises(OdooConnectionError):
            partner_model.search([])

    def test_record_odoo_error(self, mock_http_client, partner_record):
        error = {"data": {"message": "Access denied"}}
        mock_http_client.post.return_value = _mock_response(error=error)
        with pytest.raises(OdooRequestError, match="Access denied"):
            str(partner_record.name)


# ===========================================================================
# Command
# ===========================================================================

class TestCommand:

    def test_create(self):
        assert Command.create({"name": "Tag"}) == (0, 0, {"name": "Tag"})

    def test_update(self):
        assert Command.update(5, {"name": "X"}) == (1, 5, {"name": "X"})

    def test_delete(self):
        assert Command.delete(3) == (2, 3, 0)

    def test_unlink(self):
        assert Command.unlink(4) == (3, 4, 0)

    def test_link(self):
        assert Command.link(7) == (4, 7, 0)

    def test_clear(self):
        assert Command.clear() == (5, 0, 0)

    def test_set(self):
        assert Command.set([1, 2, 3]) == (6, 0, [1, 2, 3])


# ===========================================================================
# Context propagation
# ===========================================================================

class TestContextPropagation:

    def test_session_context_passed_to_model(self, mock_http_client):
        env = OdooSession(
            url="https://test.odoo.com",
            session_id="sid",
            context={"lang": "fr_FR", "tz": "Europe/Paris"},
        )
        model = env("res.partner")
        assert model._context["lang"] == "fr_FR"

    def test_model_context_in_request(self, mock_http_client):
        env = OdooSession(
            url="https://test.odoo.com",
            session_id="sid",
            context={"lang": "fr_FR"},
        )
        model = env("res.partner")
        mock_http_client.post.return_value = _mock_response(result=[])
        model.search([])
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["kwargs"]["context"]["lang"] == "fr_FR"

    def test_with_context_merges_existing(self, session, partner_model):
        m = partner_model.with_context(active_test=False)
        assert m._context.get("lang") == partner_model._context.get("lang")
        assert m._context["active_test"] is False


# ===========================================================================
# OdooSession – environment variables (env.uid / env.user / env.company …)
# ===========================================================================

class TestOdooSessionEnvVars:

    # --- helpers ----------------------------------------------------------

    @staticmethod
    def _session_info_response(**extra):
        base = {
            "uid": 7,
            "company_id": 1,
            "allowed_company_ids": [1, 2],
            "user_context": {"lang": "en_US", "tz": "UTC"},
        }
        base.update(extra)
        return _mock_response(result=base)

    # --- uid --------------------------------------------------------------

    def test_uid_returns_integer(self, mock_http_client, session):
        mock_http_client.post.return_value = self._session_info_response()
        assert session.uid == 7

    def test_uid_zero_when_missing(self, mock_http_client, session):
        mock_http_client.post.return_value = _mock_response(result={})
        assert session.uid == 0

    # --- user -------------------------------------------------------------

    def test_user_returns_odoo_record(self, mock_http_client, session):
        mock_http_client.post.return_value = self._session_info_response()
        user = session.user
        assert isinstance(user, OdooRecord)
        assert user._model == 'res.users'
        assert user.id == 7

    def test_user_shares_client(self, mock_http_client, session):
        mock_http_client.post.return_value = self._session_info_response()
        assert session.user._client is session._client

    def test_user_inherits_context(self, mock_http_client):
        mock_http_client.post.return_value = self._session_info_response(uid=3)
        env = OdooSession(
            url="https://test.odoo.com",
            session_id="sid",
            context={"lang": "fr_FR"},
        )
        assert env.user._context["lang"] == "fr_FR"

    # --- company ----------------------------------------------------------

    def test_company_returns_odoo_record(self, mock_http_client, session):
        mock_http_client.post.return_value = self._session_info_response()
        company = session.company
        assert isinstance(company, OdooRecord)
        assert company._model == 'res.company'
        assert company.id == 1

    def test_company_shares_client(self, mock_http_client, session):
        mock_http_client.post.return_value = self._session_info_response()
        assert session.company._client is session._client

    def test_company_raises_when_no_company_id(self, mock_http_client, session):
        mock_http_client.post.return_value = _mock_response(result={"uid": 1})
        with pytest.raises(OdooRequestError):
            _ = session.company

    # --- companies --------------------------------------------------------

    def test_companies_returns_list_of_records(self, mock_http_client, session):
        mock_http_client.post.return_value = self._session_info_response()
        companies = session.companies
        assert len(companies) == 2
        assert all(isinstance(c, OdooRecord) for c in companies)
        assert all(c._model == 'res.company' for c in companies)
        assert [c.id for c in companies] == [1, 2]

    def test_companies_empty_when_not_present(self, mock_http_client, session):
        mock_http_client.post.return_value = _mock_response(result={"uid": 1, "company_id": 1})
        assert session.companies == []

    def test_companies_handles_list_of_id_name_pairs(self, mock_http_client, session):
        """Some Odoo versions return [[id, name], ...] instead of [id, ...]."""
        mock_http_client.post.return_value = _mock_response(result={
            "uid": 1,
            "company_id": 1,
            "allowed_company_ids": [[1, "Main Company"], [3, "Sub Company"]],
        })
        companies = session.companies
        assert [c.id for c in companies] == [1, 3]

    def test_companies_share_client(self, mock_http_client, session):
        mock_http_client.post.return_value = self._session_info_response()
        for company in session.companies:
            assert company._client is session._client

    # --- lang / context ---------------------------------------------------

    def test_lang_from_context(self, mock_http_client, session):
        assert session.lang == 'en_US'

    def test_lang_custom(self, mock_http_client):
        env = OdooSession(
            url="https://test.odoo.com",
            session_id="sid",
            context={"lang": "ar_SY"},
        )
        assert env.lang == 'ar_SY'

    def test_context_returns_copy(self, mock_http_client, session):
        ctx = session.context
        assert isinstance(ctx, dict)
        ctx['mutated'] = True
        assert 'mutated' not in session.context

    def test_context_contains_lang(self, mock_http_client, session):
        assert 'lang' in session.context

    # --- session info caching ---------------------------------------------

    def test_session_info_fetched_once(self, mock_http_client, session):
        mock_http_client.post.return_value = self._session_info_response()
        _ = session.uid
        _ = session.uid
        _ = session.uid
        assert mock_http_client.post.call_count == 1

    def test_session_info_cached_across_properties(self, mock_http_client, session):
        mock_http_client.post.return_value = self._session_info_response()
        _ = session.uid
        _ = session.user
        _ = session.company
        assert mock_http_client.post.call_count == 1

    def test_session_info_error_propagated(self, mock_http_client, session):
        error = {"data": {"message": "Not logged in"}}
        mock_http_client.post.return_value = _mock_response(error=error)
        with pytest.raises(OdooRequestError, match="Not logged in"):
            _ = session.uid

    def test_session_info_timeout_raises_connection_error(self, mock_http_client, session):
        mock_http_client.post.side_effect = httpx.ReadTimeout("timed out")
        with pytest.raises(OdooConnectionError):
            _ = session.uid

# ===========================================================================
# _FieldProxy – numeric and container proxy methods
# ===========================================================================

class TestFieldProxyNumericContainer:
    """
    Tests for the _FieldProxy dunder methods that let a proxy value behave
    as an int, float, or container transparently.
    """

    def _proxy(self, mock_http_client, partner_record, value, field_name="qty"):
        """Set up mock to return *value* for a field read and return the proxy."""
        mock_http_client.post.return_value = _mock_response(
            result=[{"id": 42, field_name: value}]
        )
        return getattr(partner_record, field_name)

    def test_int_conversion(self, mock_http_client, partner_record):
        proxy = self._proxy(mock_http_client, partner_record, 7)
        assert int(proxy) == 7

    def test_float_conversion(self, mock_http_client, partner_record):
        proxy = self._proxy(mock_http_client, partner_record, 3.14)
        assert float(proxy) == pytest.approx(3.14)

    def test_len_on_list_field(self, mock_http_client, partner_record):
        proxy = self._proxy(mock_http_client, partner_record, [1, 2, 3])
        assert len(proxy) == 3

    def test_iter_on_list_field(self, mock_http_client, partner_record):
        proxy = self._proxy(mock_http_client, partner_record, [10, 20])
        assert list(proxy) == [10, 20]

    def test_contains_on_list_field(self, mock_http_client, partner_record):
        proxy = self._proxy(mock_http_client, partner_record, ["a", "b"])
        assert "a" in proxy
        assert "c" not in proxy

    def test_getitem_on_list_field(self, mock_http_client, partner_record):
        proxy = self._proxy(mock_http_client, partner_record, ["x", "y"])
        assert proxy[0] == "x"

    def test_lt_comparison(self, mock_http_client, partner_record):
        proxy = self._proxy(mock_http_client, partner_record, 5)
        assert proxy < 10
        assert not (proxy < 3)

    def test_le_comparison(self, mock_http_client, partner_record):
        proxy = self._proxy(mock_http_client, partner_record, 5)
        assert proxy <= 5
        assert proxy <= 10

    def test_gt_comparison(self, mock_http_client, partner_record):
        proxy = self._proxy(mock_http_client, partner_record, 5)
        assert proxy > 3
        assert not (proxy > 10)

    def test_ge_comparison(self, mock_http_client, partner_record):
        proxy = self._proxy(mock_http_client, partner_record, 5)
        assert proxy >= 5
        assert proxy >= 3

    def test_add_proxy_and_literal(self, mock_http_client, partner_record):
        proxy = self._proxy(mock_http_client, partner_record, 4)
        assert proxy + 6 == 10

    def test_radd_literal_and_proxy(self, mock_http_client, partner_record):
        proxy = self._proxy(mock_http_client, partner_record, 4)
        assert 6 + proxy == 10

    def test_getattr_delegates_to_value(self, mock_http_client, partner_record):
        """Attribute access on a proxy should delegate to the underlying value."""
        mock_http_client.post.return_value = _mock_response(
            result=[{"id": 42, "name": "hello world"}]
        )
        # str.upper() accessed through the proxy
        assert partner_record.name.upper() == "HELLO WORLD"

    def test_ne_operator(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(
            result=[{"id": 42, "name": "Alice"}]
        )
        assert partner_record.name != "Bob"


# ===========================================================================
# OdooModel – search_read additional kwargs
# ===========================================================================

class TestOdooModelSearchReadExtra:

    def test_search_read_with_limit(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[{"id": 1}])
        partner_model.search_read([], limit=5)
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["kwargs"]["limit"] == 5

    def test_search_read_with_order(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[{"id": 1}])
        partner_model.search_read([], order="name DESC")
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["kwargs"]["order"] == "name DESC"

    def test_search_read_with_offset(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[{"id": 2}])
        partner_model.search_read([], offset=5)
        payload = mock_http_client.post.call_args[1]["json"]
        assert payload["params"]["kwargs"]["offset"] == 5

    def test_search_read_correct_url(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[])
        partner_model.search_read([])
        called_url = mock_http_client.post.call_args[0][0]
        assert "search_read" in called_url


# ===========================================================================
# OdooModel – error propagation for write / create / unlink
# ===========================================================================

class TestOdooModelErrorPropagation:

    def test_create_timeout(self, mock_http_client, partner_model):
        mock_http_client.post.side_effect = httpx.ReadTimeout("timeout")
        with pytest.raises(OdooConnectionError):
            partner_model.create({"name": "X"})

    def test_write_http_error(self, mock_http_client, partner_model):
        mock_http_client.post.side_effect = httpx.HTTPError("bad")
        with pytest.raises(OdooConnectionError):
            partner_model.write(1, {"name": "Y"})

    def test_unlink_odoo_error(self, mock_http_client, partner_model):
        error = {"data": {"message": "Cannot delete"}}
        mock_http_client.post.return_value = _mock_response(error=error)
        with pytest.raises(OdooRequestError, match="Cannot delete"):
            partner_model.unlink(1)

    def test_search_count_timeout(self, mock_http_client, partner_model):
        mock_http_client.post.side_effect = httpx.ReadTimeout("timeout")
        with pytest.raises(OdooConnectionError):
            partner_model.search_count([])


# ===========================================================================
# connect_odoo – additional edge cases
# ===========================================================================

class TestConnectOdooExtra:

    def test_timeout_raises_connection_error(self, mock_http_client):
        mock_http_client.post.side_effect = httpx.ReadTimeout("timeout")
        with pytest.raises(OdooConnectionError):
            connect_odoo("https://test.odoo.com", "db", "admin", "admin")

    def test_connect_timeout_raises_connection_error(self, mock_http_client):
        mock_http_client.post.side_effect = httpx.ConnectTimeout("conn timeout")
        with pytest.raises(OdooConnectionError):
            connect_odoo("https://test.odoo.com", "db", "admin", "admin")

    def test_odoo_error_in_response_raises_auth_error(self, mock_http_client):
        """connect_odoo raises OdooAuthenticationError when the server returns an error payload."""
        error = {"data": {"message": "Invalid database"}}
        mock_http_client.post.return_value = _mock_response(error=error)
        with pytest.raises(OdooAuthenticationError):
            connect_odoo("https://test.odoo.com", "db", "admin", "admin")


# ===========================================================================
# OdooRecord – context merging in _make_request
# ===========================================================================

class TestOdooRecordContextMerge:

    def test_context_merged_with_caller_context(self, mock_http_client, partner_record):
        """When a caller passes context= in kwargs it must be merged with record ctx."""
        mock_http_client.post.return_value = _mock_response(result=True)
        partner_record._make_request("write", [[42], {"name": "X"}], {"context": {"bin_size": True}})
        payload = mock_http_client.post.call_args[1]["json"]
        merged_ctx = payload["params"]["kwargs"]["context"]
        # from record context – read value dynamically from the fixture
        assert merged_ctx.get("lang") == partner_record._context.get("lang")
        assert merged_ctx.get("bin_size") is True   # from caller context

    def test_default_context_in_request(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(result=True)
        partner_record._make_request("write", [[42], {"name": "Y"}])
        payload = mock_http_client.post.call_args[1]["json"]
        assert "context" in payload["params"]["kwargs"]
        assert payload["params"]["kwargs"]["context"] == partner_record._context


# ===========================================================================
# OdooRecord – field absent from server response
# ===========================================================================

class TestOdooRecordFieldAbsent:

    def test_absent_field_returns_false(self, mock_http_client, partner_record):
        """If a field is not in the server response, _get_field returns False."""
        mock_http_client.post.return_value = _mock_response(
            result=[{"id": 42, "other": "value"}]
        )
        value = partner_record._get_field("missing_field")
        assert value is False

    def test_empty_result_returns_false(self, mock_http_client, partner_record):
        mock_http_client.post.return_value = _mock_response(result=[])
        value = partner_record._get_field("name")
        assert value is False


# ===========================================================================
# OdooModel – correct session cookie sent in request headers
# ===========================================================================

class TestRequestHeaders:

    def test_session_cookie_sent(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[])
        partner_model.search([])
        headers = mock_http_client.post.call_args[1]["headers"]
        assert "session_id=test_session_123" in headers.get("Cookie", "")

    def test_content_type_json(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[])
        partner_model.search([])
        headers = mock_http_client.post.call_args[1]["headers"]
        assert headers["Content-Type"] == "application/json"

    def test_correct_endpoint_used(self, mock_http_client, partner_model):
        mock_http_client.post.return_value = _mock_response(result=[])
        partner_model.search([])
        called_url = mock_http_client.post.call_args[0][0]
        assert "/web/dataset/call_kw/res.partner/search" in called_url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])