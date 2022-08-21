from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from qcportal.serverinfo import ErrorLogQueryFilters

if TYPE_CHECKING:
    from qcfractal.db_socket import SQLAlchemySocket


def test_serverinfo_socket_save_error(storage_socket: SQLAlchemySocket):

    error_data_1 = {
        "error_text": "This is a test error",
        "user": "admin_user",
        "request_path": "/v1/molecule",
        "request_headers": "fake_headers",
        "request_body": "fake body",
    }

    error_data_2 = {
        "error_text": "This is another test error",
        "user": "read_user",
        "request_path": "/v1/molecule",
        "request_headers": "fake_headers",
        "request_body": "fake body",
    }

    all_errors = [error_data_1, error_data_2]
    id_1 = storage_socket.serverinfo.save_error(error_data_1)
    time_12 = datetime.datetime.utcnow()
    id_2 = storage_socket.serverinfo.save_error(error_data_2)

    meta, errors = storage_socket.serverinfo.query_error_log(ErrorLogQueryFilters())
    assert meta.n_found == 2
    assert len(errors) == 2

    # Returned in chrono order, newest first
    assert errors[0]["id"] == id_2
    assert errors[1]["id"] == id_1
    assert errors[0]["error_date"] > errors[1]["error_date"]

    for in_err, db_err in zip(reversed(all_errors), errors):
        assert in_err["error_text"] == db_err["error_text"]
        assert in_err["user"] == db_err["user"]
        assert in_err["request_path"] == db_err["request_path"]
        assert in_err["request_headers"] == db_err["request_headers"]
        assert in_err["request_body"] == db_err["request_body"]

    # Query by id
    meta, err = storage_socket.serverinfo.query_error_log(ErrorLogQueryFilters(error_id=[id_2]))
    assert meta.n_found == 1
    assert err[0]["error_text"] == error_data_2["error_text"]

    # query by time
    meta, err = storage_socket.serverinfo.query_error_log(ErrorLogQueryFilters(before=time_12))
    assert meta.n_found == 1
    assert err[0]["error_text"] == error_data_1["error_text"]

    meta, err = storage_socket.serverinfo.query_error_log(ErrorLogQueryFilters(after=datetime.datetime.utcnow()))
    assert meta.n_found == 0

    meta, err = storage_socket.serverinfo.query_error_log(
        ErrorLogQueryFilters(before=datetime.datetime.utcnow(), after=time_12)
    )
    assert meta.n_found == 1

    meta, err = storage_socket.serverinfo.query_error_log(
        ErrorLogQueryFilters(after=datetime.datetime.utcnow(), before=time_12)
    )
    assert meta.n_found == 0

    # query by user
    meta, err = storage_socket.serverinfo.query_error_log(ErrorLogQueryFilters(username=["read_user"]))
    assert meta.n_found == 1