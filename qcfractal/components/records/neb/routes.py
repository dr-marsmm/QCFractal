from flask import current_app

from qcfractal.app import main, storage_socket
from qcfractal.app.helpers import prefix_projection
from qcfractal.app.routes import wrap_route
from qcportal.base_models import ProjURLParameters
from qcportal.exceptions import LimitExceededError
from qcportal.records.neb import NEBAddBody, NEBQueryBody
from qcportal.utils import calculate_limit


@main.route("/v1/records/neb/bulkCreate", methods=["POST"])
@wrap_route(NEBAddBody, None, "WRITE")
def add_neb_records_v1(body_data: NEBAddBody):
    limit = current_app.config["QCFRACTAL_CONFIG"].api_limits.add_records
    if len(body_data.initial_chain) > limit:
        raise LimitExceededError(
            f"Cannot add {len(body_data.initial_chain)} neb records - limit is {limit}"
        )

    return storage_socket.records.neb.add(
        initial_chain=body_data.initial_chain,
        td_spec=body_data.specification,
        tag=body_data.tag,
        priority=body_data.priority,
    )


@main.route("/v1/records/neb/<int:record_id>/singlepoints", methods=["GET"])
@wrap_route(None, ProjURLParameters, "READ")
def get_neb_singlepoints_v1(record_id: int, *, url_params: ProjURLParameters):
    # adjust the includes/excludes to refer to the singlepoints
    ch_includes, ch_excludes = prefix_projection(url_params, "singlepoints")
    rec = storage_socket.records.neb.get([record_id], include=ch_includes, exclude=ch_excludes)
    return rec[0]["singlepoints"]


@main.route("/v1/records/neb/<int:record_id>/initial_chain", methods=["GET"])
@wrap_route(None, None, "READ")
def get_neb_initial_chain_v1(record_id: int):
    rec = storage_socket.records.neb.get([record_id], include=["initial_chain"])
    return rec[0]["initial_chain"]


@main.route("/v1/records/neb/query", methods=["POST"])
@wrap_route(NEBQueryBody, None, "READ")
def query_neb_v1(body_data: NEBQueryBody):
    max_limit = current_app.config["QCFRACTAL_CONFIG"].api_limits.get_records
    body_data.limit = calculate_limit(max_limit, body_data.limit)

    return storage_socket.records.neb.query(body_data)