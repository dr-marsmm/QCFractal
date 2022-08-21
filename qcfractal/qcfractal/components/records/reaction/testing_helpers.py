from __future__ import annotations

from typing import TYPE_CHECKING, Tuple, Optional, Dict, List, Union, Any

import pydantic
from qcelemental.models import Molecule, FailedOperation, ComputeError, AtomicResult, OptimizationResult

from qcfractal.testing_helpers import run_service_simple
from qcarchivetesting.helpers import read_record_data
from qcportal.records import PriorityEnum, RecordStatusEnum
from qcportal.records.reaction import ReactionSpecification, ReactionKeywords
from qcportal.records.singlepoint import SinglepointProtocols, QCSpecification

if TYPE_CHECKING:
    from qcfractal.db_socket import SQLAlchemySocket
    from qcportal.managers import ManagerName

test_specs = [
    ReactionSpecification(
        program="reaction",
        singlepoint_specification=QCSpecification(
            program="prog1",
            driver="energy",
            method="b3lyp",
            basis="6-31G*",
            keywords={"k": "value"},
            protocols=SinglepointProtocols(wavefunction="all"),
        ),
        keywords=ReactionKeywords(),
    ),
    ReactionSpecification(
        program="reaction",
        singlepoint_specification=QCSpecification(
            program="Prog2", driver="energy", method="Hf", basis="def2-TZVP", keywords={"k": "v"}
        ),
        keywords=ReactionKeywords(),
    ),
]


def compare_reaction_specs(
    input_spec: Union[ReactionSpecification, Dict[str, Any]],
    output_spec: Union[ReactionSpecification, Dict[str, Any]],
) -> bool:
    if isinstance(input_spec, dict):
        input_spec = ReactionSpecification(**input_spec)
    if isinstance(output_spec, dict):
        output_spec = ReactionSpecification(**output_spec)

    return input_spec == output_spec


def load_test_data(
    name: str,
) -> Tuple[ReactionSpecification, List[Tuple[float, Molecule]], Dict[str, Union[AtomicResult, OptimizationResult]]]:
    test_data = read_record_data(name)

    return (
        pydantic.parse_obj_as(ReactionSpecification, test_data["specification"]),
        pydantic.parse_obj_as(List[Tuple[float, Molecule]], test_data["molecule"]),
        pydantic.parse_obj_as(Dict[str, Union[AtomicResult, OptimizationResult]], test_data["result"]),
    )


def submit_test_data(
    storage_socket: SQLAlchemySocket,
    name: str,
    tag: Optional[str] = "*",
    priority: PriorityEnum = PriorityEnum.normal,
) -> Tuple[int, Dict[str, Union[AtomicResult, OptimizationResult]]]:

    input_spec, stoich, result = load_test_data(name)
    meta, record_ids = storage_socket.records.reaction.add([stoich], input_spec, tag, priority)
    assert meta.success
    assert len(record_ids) == 1
    assert meta.n_inserted == 1

    return record_ids[0], result


def run_test_data(
    storage_socket: SQLAlchemySocket,
    manager_name: ManagerName,
    name: str,
    tag: Optional[str] = "*",
    priority: PriorityEnum = PriorityEnum.normal,
    end_status: RecordStatusEnum = RecordStatusEnum.complete,
):
    record_id, result = submit_test_data(storage_socket, name, tag, priority)

    record = storage_socket.records.get([record_id])[0]
    assert record["status"] == RecordStatusEnum.waiting

    if end_status == RecordStatusEnum.error:
        failed_op = FailedOperation(
            error=ComputeError(error_type="test_error", error_message="this is just a test error"),
        )
        result = {x: failed_op for x in result}

    finished, n_optimizations = run_service_simple(storage_socket, manager_name, record_id, result, 200)
    assert finished

    record = storage_socket.records.get([record_id], include=["status"])[0]
    assert record["status"] == end_status

    return record_id